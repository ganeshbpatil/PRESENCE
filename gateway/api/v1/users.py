"""
gateway/api/v1/users.py

User management console for agency/business admins -- list users scoped
to a business or agency, edit role/reassign business_id or agency_id,
deactivate (is_active=False). Kept separate from auth.py: auth.py owns
identity (signup/login/tokens), this owns *administration* of other
users' accounts, a distinct RBAC surface with its own escalation guards.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db import get_db
from gateway.security import get_current_user
from gateway.tenancy import (
    require_agency_access,
    require_business_access,
    require_business_write_access,
)
from shared.models.core import User, UserRole

router = APIRouter(tags=["users"])


class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    business_id: uuid.UUID | None
    agency_id: uuid.UUID | None
    is_active: bool

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    # All optional -- PATCH semantics, only set fields are touched.
    role: UserRole | None = None
    business_id: uuid.UUID | None = None
    agency_id: uuid.UUID | None = None
    is_active: bool | None = None


async def _get_user_or_404(user_id: uuid.UUID, db: AsyncSession) -> User:
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return target


@router.get("/businesses/{business_id}/users", response_model=list[UserSummary])
async def list_business_users(
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[User]:
    await require_business_access(business_id, user, db)  # read -- viewer allowed
    result = await db.execute(select(User).where(User.business_id == business_id))
    return list(result.scalars().all())


@router.get("/agencies/{agency_id}/users", response_model=list[UserSummary])
async def list_agency_users(
    agency_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[User]:
    await require_agency_access(agency_id, user, db)  # read -- viewer allowed
    result = await db.execute(select(User).where(User.agency_id == agency_id))
    return list(result.scalars().all())


@router.patch("/users/{user_id}", response_model=UserSummary)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> User:
    target = await _get_user_or_404(user_id, db)

    # 1. Caller must have WRITE access to the target's CURRENT scope.
    if target.business_id is not None:
        await require_business_write_access(target.business_id, caller, db)
    elif target.agency_id is not None:
        await require_agency_access(target.agency_id, caller, db, write=True)
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot edit an unscoped user")

    # 2. Only an agency_admin may ever grant an agency-scoped role at all
    #    -- otherwise an smb_owner who legitimately passed check 1 (editing
    #    a peer in their own business) could promote that peer straight to
    #    agency_admin.
    if (
        body.role in (UserRole.agency_admin, UserRole.agency_viewer)
        and caller.role != UserRole.agency_admin
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only an agency_admin may assign agency roles"
        )

    # 3. No self-role-escalation or self-deactivation via this endpoint,
    #    ever, regardless of caller's current role -- simplest safe rule,
    #    avoids "can I promote/lock out myself" edge cases entirely.
    if target.id == caller.id and (body.role is not None or body.is_active is not None):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Cannot change your own role or active status"
        )

    # 4. If reassigning business_id/agency_id, caller must ALSO have write
    #    access to the NEW scope -- prevents moving a user into a foreign
    #    agency/business the caller doesn't control.
    if body.business_id is not None:
        await require_business_write_access(body.business_id, caller, db)
    if body.agency_id is not None:
        await require_agency_access(body.agency_id, caller, db, write=True)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(target, field, value)
    await db.commit()
    await db.refresh(target)
    return target
