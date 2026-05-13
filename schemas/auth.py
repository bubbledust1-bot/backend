"""
认证相关的 Pydantic 模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求。"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """Token 响应。"""
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field(default="bearer", description="Token 类型")


class RefreshTokenRequest(BaseModel):
    """刷新 token 请求。"""
    refresh_token: str = Field(..., description="Refresh token")


class UserResponse(BaseModel):
    """用户信息响应（用于 /api/auth/me）。"""
    id: int
    username: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    role: str
    is_active: bool
    must_change_password: bool
    last_login_at: Optional[datetime] = None


class UpdateProfileRequest(BaseModel):
    """更新个人资料请求。"""
    nickname: Optional[str] = Field(None, description="昵称")
    email: Optional[str] = Field(None, description="邮箱")


class ChangePasswordRequest(BaseModel):
    """修改密码请求。"""
    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., description="新密码", min_length=6)
