"""
gateway/security.py

Self-built JWT + password hashing per docs/PRESENCE/03_ARCHITECTURE/
SECURITY_ARCHITECTURE.md ("Auth: Self-built JWT + OAuth (not Clerk)").
This file is the only place that mints/verifies PRESENCE's own user-login
tokens — distinct from platform-connection OAuth (GBP/Meta/WhatsApp), which
lives on PlatformConnection instead.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.config import get_settings
from gateway.db import get_db
from shared.models.core import User, UserRole

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_TOKEN_TYPE_ACCESS = "access"
_TOKEN_TYPE_REFRESH = "refresh"


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def _mint_token(user_id: uuid.UUID, token_type: str, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        # jti: without it, two tokens of the same type minted for the same
        # user within the same second (iat has 1s resolution) would be
        # byte-identical -> same hash -> unique constraint violation on
        # refresh_tokens.token_hash (hit in practice: signup immediately
        # followed by login).
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    return _mint_token(
        user_id, _TOKEN_TYPE_ACCESS, timedelta(minutes=settings.jwt_access_expire_minutes)
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    return _mint_token(
        user_id, _TOKEN_TYPE_REFRESH, timedelta(days=settings.jwt_refresh_expire_days)
    )


class TokenError(Exception):
    pass


def decode_token(token: str, expected_type: str) -> uuid.UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    if payload.get("type") != expected_type:
        raise TokenError(f"expected a {expected_type} token")

    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise TokenError("malformed subject claim") from exc


async def get_current_user(
    token: str | None = Depends(_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_error

    try:
        user_id = decode_token(token, _TOKEN_TYPE_ACCESS)
    except TokenError as exc:
        raise credentials_error from exc

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_error
    return user


def assert_valid_invite_code(invite_code: str | None) -> None:
    """Gate for the otherwise-unauthenticated Business/Agency create
    endpoints (both must exist before a user can sign up referencing
    them). settings.signup_invite_code empty means the check is skipped
    -- set it in production so the public API can't spin up arbitrary
    shells."""
    settings = get_settings()
    if not settings.signup_invite_code:
        return
    if invite_code != settings.signup_invite_code:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid invite code")


def require_role(*allowed_roles: UserRole):
    """FastAPI dependency factory for RBAC per SECURITY_ARCHITECTURE.md's
    v1 role set (SMB Owner, Agency Admin, Agency Viewer)."""

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {user.role.value} is not permitted to perform this action",
            )
        return user

    return _checker
