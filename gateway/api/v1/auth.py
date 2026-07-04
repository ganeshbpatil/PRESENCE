"""
gateway/api/v1/auth.py

PRESENCE's own user-login auth (JWT bearer, RBAC roles) — see
gateway/security.py for the token/hash mechanics this route delegates to.
Distinct from platform-connection OAuth (GBP/Meta/WhatsApp connect flows),
which is scoped under businesses.py's /connections endpoints instead.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.config import get_settings
from gateway.db import get_db
from gateway.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from shared.models.core import RefreshToken, User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: UserRole
    business_id: uuid.UUID | None = None
    agency_id: uuid.UUID | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    business_id: uuid.UUID | None
    agency_id: uuid.UUID | None

    model_config = {"from_attributes": True}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _issue_tokens(user: User, db: AsyncSession) -> TokenResponse:
    settings = get_settings()
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(refresh),
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.jwt_refresh_expire_days),
        )
    )
    await db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = (
        await db.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    if body.role == UserRole.smb_owner and body.business_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "smb_owner requires business_id")
    if body.role in (UserRole.agency_admin, UserRole.agency_viewer) and body.agency_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "agency roles require agency_id"
        )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        business_id=body.business_id,
        agency_id=body.agency_id,
    )
    db.add(user)
    await db.flush()
    return await _issue_tokens(user, db)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = (
        await db.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return await _issue_tokens(user, db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
    try:
        user_id = decode_token(body.refresh_token, "refresh")
    except TokenError as exc:
        raise invalid from exc

    token_hash = _hash_token(body.refresh_token)
    stored = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if (
        stored is None
        or stored.revoked_at is not None
        or stored.expires_at < datetime.now(UTC)
    ):
        raise invalid

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise invalid

    # Rotate: revoke the used refresh token, issue a fresh pair.
    stored.revoked_at = datetime.now(UTC)
    return await _issue_tokens(user, db)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
