"""
账户管理相关的 Pydantic 模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserListResponse(BaseModel):
    """用户列表项。"""
    id: int
    username: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None


class CreateUserRequest(BaseModel):
    """创建用户请求。"""
    username: str = Field(..., description="用户名", min_length=3, max_length=128)
    password: str = Field(..., description="密码", min_length=6)
    email: Optional[str] = Field(None, description="邮箱")
    nickname: Optional[str] = Field(None, description="昵称")
    role: str = Field(default="user", description="角色：superadmin/admin/user")
    must_change_password: bool = Field(default=True, description="是否需要强制修改密码")


class UpdateUserRequest(BaseModel):
    """更新用户请求。"""
    email: Optional[str] = Field(None, description="邮箱")
    nickname: Optional[str] = Field(None, description="昵称")
    role: Optional[str] = Field(None, description="角色：superadmin/admin/user")


class ResetPasswordRequest(BaseModel):
    """重置密码请求。"""
    new_password: str = Field(..., description="新密码", min_length=6)
