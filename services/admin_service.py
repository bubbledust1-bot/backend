"""
账户管理服务业务逻辑。
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user import User
from schemas.admin import CreateUserRequest, UpdateUserRequest
from utils.security import get_password_hash


def is_last_superadmin(db: Session, user_id: int) -> bool:
    """检查指定用户是否是最后一个 superadmin。"""
    superadmins = db.query(User).filter(User.role == "superadmin", User.is_active == True).all()
    if len(superadmins) > 1:
        return False
    if len(superadmins) == 1 and superadmins[0].id == user_id:
        return True
    return False


def get_all_users(db: Session) -> List[User]:
    """获取所有用户列表。"""
    return db.query(User).order_by(User.created_at.desc()).all()


def get_user_by_id_admin(db: Session, user_id: int) -> Optional[User]:
    """根据 ID 获取用户（管理员用）。"""
    return db.query(User).filter(User.id == user_id).first()


def create_user(
    db: Session,
    request: CreateUserRequest,
    created_by: User,
) -> User:
    """创建新用户。"""
    # 检查用户名是否已存在
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )
    # 检查邮箱是否已存在（如果提供了）
    if request.email:
        existing_email = db.query(User).filter(User.email == request.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已被使用",
            )
    # 验证角色
    valid_roles = ["superadmin", "admin", "user"]
    if request.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效角色，可选值：{', '.join(valid_roles)}",
        )
    # 创建用户
    user = User(
        username=request.username,
        email=request.email,
        nickname=request.nickname,
        role=request.role,
        hashed_password=get_password_hash(request.password),
        is_active=True,
        must_change_password=request.must_change_password,
        created_by=created_by.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user_id: int,
    request: UpdateUserRequest,
    current_user: User,
) -> User:
    """更新用户信息。"""
    user = get_user_by_id_admin(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    # 检查是否尝试降级/禁用最后一个 superadmin
    if user.role == "superadmin":
        if is_last_superadmin(db, user_id):
            if request.role and request.role != "superadmin":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="不能降级最后一个超级管理员",
                )
    # 更新字段
    if request.nickname is not None:
        user.nickname = request.nickname
    if request.email is not None:
        # 检查邮箱是否已被其他用户使用
        if request.email:
            existing = db.query(User).filter(User.email == request.email, User.id != user_id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="该邮箱已被使用",
                )
        user.email = request.email
    if request.role is not None:
        # 验证角色
        valid_roles = ["superadmin", "admin", "user"]
        if request.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效角色，可选值：{', '.join(valid_roles)}",
            )
        user.role = request.role
    db.commit()
    db.refresh(user)
    return user


def reset_user_password(
    db: Session,
    user_id: int,
    new_password: str,
) -> User:
    """重置用户密码，设置 must_change_password=True。"""
    user = get_user_by_id_admin(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    user.hashed_password = get_password_hash(new_password)
    user.must_change_password = True
    db.commit()
    db.refresh(user)
    return user


def toggle_user_active(
    db: Session,
    user_id: int,
    current_user: User,
) -> User:
    """启用/禁用用户。"""
    user = get_user_by_id_admin(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    # 检查是否禁用最后一个 superadmin
    if user.role == "superadmin" and user.is_active:
        if is_last_superadmin(db, user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能禁用最后一个超级管理员",
            )
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user


def delete_user(
    db: Session,
    user_id: int,
    current_user: User,
) -> None:
    """删除用户。"""
    user = get_user_by_id_admin(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    # 不能删除自己
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己",
        )
    # 检查是否删除最后一个 superadmin
    if user.role == "superadmin" and is_last_superadmin(db, user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除最后一个超级管理员",
        )
    db.delete(user)
    db.commit()
