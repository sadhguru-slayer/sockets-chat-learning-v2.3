from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db import SessionLocal
from dependencies import db_session
from models import User

from .schemas import RegisterRequest, LoginRequest, TokenResponse
from .service import hash_password, verify_password
from .jwt_auth import create_access_token, create_refresh_token, verify_refresh_token


router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
async def register(data: RegisterRequest, db:db_session):

    result = await db.execute(
        select(User).where(User.username == data.username)
    )
    if result.scalar():
        raise HTTPException(400, "User already exists")
    print(data.username,"_____USERNAME_____")
    print(data.password,"_____PASSWORD_____")
    user = User(
        username=data.username,
        password=hash_password(data.password)
    )
    db.add(user)
    await db.commit()
    return {"message": "registered"}
    

@router.post("/refresh")
async def refresh_token(refresh_token: str):
    payload = verify_refresh_token(refresh_token)

    if not payload:
        raise HTTPException(401, "Invalid refresh token")

    new_access = create_access_token({
        "sub": payload["sub"]
    })

    return {
        "access_token": new_access
    }

from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated

@router.post("/login", response_model=TokenResponse)
async def login(data: Annotated[OAuth2PasswordRequestForm,Depends()],db:db_session):
    result = await db.execute(
        select(User).where(User.username == data.username)
    )
    user = result.scalar()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(401, "Invalid credentials")
    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=access,
        refresh_token=refresh
    )

