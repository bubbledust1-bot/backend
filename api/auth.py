"""
认证相关 API 路由。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from models.user import User
from schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from services.auth_service import (
    authenticate_user,
    change_user_password,
    create_auth_tokens,
    refresh_access_token,
    update_last_login,
    update_user_profile,
)

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """用户登录，返回 access token 和 refresh token。"""
    user = authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    update_last_login(db, user)
    return create_auth_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """使用 refresh token 刷新 access token。"""
    return refresh_access_token(db, request.refresh_token)


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """获取当前登录用户信息。"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "nickname": current_user.nickname,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "must_change_password": current_user.must_change_password,
        "last_login_at": current_user.last_login_at,
    }


@router.put("/me", response_model=UserResponse)
def update_me(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新当前用户个人资料。"""
    updated_user = update_user_profile(db, current_user, request)
    return {
        "id": updated_user.id,
        "username": updated_user.username,
        "email": updated_user.email,
        "nickname": updated_user.nickname,
        "role": updated_user.role,
        "is_active": updated_user.is_active,
        "must_change_password": updated_user.must_change_password,
        "last_login_at": updated_user.last_login_at,
    }


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改当前用户密码。"""
    change_user_password(db, current_user, request)
