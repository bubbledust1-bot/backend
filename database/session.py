"""
SQLAlchemy 引擎与会话工厂。

说明：
- 使用同步 Session，与当前阶段 FastAPI 路由（同步调用 algorithm）简单配合。
- 若 DATABASE_URL 为 SQLite，需 check_same_thread=False 供多线程/多请求使用。
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

# SQLite 需要关闭「同线程检查」，否则 FastAPI 线程池下会报错
_connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 所有 ORM 模型应继承此 Base
Base = declarative_base()
