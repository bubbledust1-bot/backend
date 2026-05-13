"""
账户管理 API 路由（superadmin 专用）。
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.deps import get_current_superadmin, get_current_user, get_db
from models.user import User
from schemas.admin import (
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    UserListResponse,
)
from services.admin_service import (
    create_user,
    delete_user,
    get_all_users,
    reset_user_password,
    toggle_user_active,
    update_user,
)

router = APIRouter(prefix="/admin", tags=["账户管理"])


@router.get("/users", response_model=List[UserListResponse])
def list_users(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_superadmin),
):
    """获取所有用户列表（仅 superadmin）。"""
    users = get_all_users(db)
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "nickname": u.nickname,
            "role": u.role,
            "is_active": u.is_active,
            "must_change_password": u.must_change_password,
            "created_at": u.created_at,
            "last_login_at": u.last_login_at,
        }
        for u in users
    ]


@router.post("/users", response_model=UserListResponse, status_code=status.HTTP_201_CREATED)
def create_new_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """创建新用户（仅 superadmin）。"""
    user = create_user(db, request, current_user)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "nickname": user.nickname,
        "role": user.role,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


@router.put("/users/{user_id}", response_model=UserListResponse)
def update_user_info(
    user_id: int,
    request: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """更新用户信息（仅 superadmin）。"""
    user = update_user(db, user_id, request, current_user)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "nickname": user.nickname,
        "role": user.role,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


@router.post("/users/{user_id}/reset-password", response_model=UserListResponse)
def reset_password(
    user_id: int,
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_superadmin),
):
    """重置用户密码（仅 superadmin），设置 must_change_password=True。"""
    user = reset_user_password(db, user_id, request.new_password)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "nickname": user.nickname,
        "role": user.role,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


@router.post("/users/{user_id}/toggle-active", response_model=UserListResponse)
def toggle_active(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """启用/禁用用户（仅 superadmin）。"""
    user = toggle_user_active(db, user_id, current_user)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "nickname": user.nickname,
        "role": user.role,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin),
):
    """删除用户（仅 superadmin）。"""
    delete_user(db, user_id, current_user)
