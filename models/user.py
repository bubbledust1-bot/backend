"""
用户表 ORM 模型。
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from database.session import Base


class User(Base):
    """users 表 ORM。"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    username = Column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
        comment="登录用户名（唯一）",
    )

    email = Column(
        String(256),
        nullable=True,
        unique=True,
        index=True,
        comment="邮箱（可选，预留字段）",
    )

    hashed_password = Column(String(256), nullable=False, comment="bcrypt 哈希密码")

    nickname = Column(String(128), nullable=True, comment="显示昵称")

    role = Column(
        String(32),
        nullable=False,
        index=True,
        default="user",
        comment="角色：superadmin/admin/user",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="账户是否启用",
    )

    must_change_password = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否需要强制修改密码",
    )

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        comment="创建者用户ID",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )

    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后登录时间",
    )

    # 自引用关系：创建者
    creator = relationship("User", remote_side=[id])
