"""
FastAPI 依赖：数据库 Session 和认证。

每个请求使用独立 Session，结束时关闭，避免连接泄漏。
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database.session import SessionLocal
from models.user import User
from services.auth_service import get_user_by_id
from utils.security import decode_token

# HTTP Bearer token 认证方案
security = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """为路由注入 SQLAlchemy Session（同步）。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_token_from_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """从 Authorization header 中提取 token。"""
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return None


def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(get_token_from_header),
) -> User:
    """获取当前登录用户，未认证则抛出 401。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise credentials_exception
    user_id: Optional[int] = payload.get("user_id")
    if not user_id:
        raise credentials_exception
    user = get_user_by_id(db, user_id)
    if not user:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )
    return user


def get_current_superadmin(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前登录用户，必须是 superadmin，否则抛出 403。"""
    if current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：需要超级管理员",
        )
    return current_user

