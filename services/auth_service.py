"""
认证服务业务逻辑。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user import User
from schemas.auth import ChangePasswordRequest, UpdateProfileRequest
from utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """验证用户名和密码，返回用户对象或 None。"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )
    return user


def create_auth_tokens(user: User) -> dict[str, str]:
    """为用户创建 access token 和 refresh token。"""
    token_data = {"sub": user.username, "user_id": user.id}
    return {
        "access_token": create_access_token(data=token_data),
        "refresh_token": create_refresh_token(data=token_data),
        "token_type": "bearer",
    }


def update_last_login(db: Session, user: User) -> None:
    """更新用户最后登录时间。"""
    user.last_login_at = datetime.utcnow()
    db.commit()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """根据 ID 获取用户。"""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """根据用户名获取用户。"""
    return db.query(User).filter(User.username == username).first()


def update_user_profile(
    db: Session,
    user: User,
    request: UpdateProfileRequest,
) -> User:
    """更新用户个人资料。"""
    if request.nickname is not None:
        user.nickname = request.nickname
    if request.email is not None:
        # 检查邮箱是否已被其他用户使用
        existing = db.query(User).filter(User.email == request.email, User.id != user.id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已被使用",
            )
        user.email = request.email
    db.commit()
    db.refresh(user)
    return user


def change_user_password(
    db: Session,
    user: User,
    request: ChangePasswordRequest,
) -> None:
    """修改用户密码。"""
    if not verify_password(request.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码错误",
        )
    user.hashed_password = get_password_hash(request.new_password)
    user.must_change_password = False
    db.commit()


def refresh_access_token(db: Session, refresh_token: str) -> dict[str, str]:
    """使用 refresh token 刷新 access token。"""
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username: Optional[str] = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 token 数据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_user_by_username(db, username)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = {"sub": user.username, "user_id": user.id}
    return {
        "access_token": create_access_token(data=token_data),
        "token_type": "bearer",
    }
