"""
数据库表初始化：根据 ORM 模型创建缺失的表。

通常在应用启动时调用一次 create_all。
不会在每次启动时删除数据；若需迁移请后续引入 Alembic。
"""

from __future__ import annotations

from pathlib import Path
from sqlalchemy.orm import Session

from config import settings
from database.session import Base, engine, SessionLocal
from models.user import User
from utils.security import get_password_hash


def init_db() -> None:
    """
    创建所有已注册到 Base.metadata 的表。

    注意：必须先 import 各模型模块，使表类注册到 Base.metadata。
    """
    _ensure_data_dir_exists()

    from models import prediction_record  # noqa: F401
    from models import sensor_record  # noqa: F401
    from models import device_task  # noqa: F401
    from models import user  # noqa: F401

    Base.metadata.create_all(bind=engine)

    if settings.DEBUG:
        _create_default_superadmin()


def _ensure_data_dir_exists() -> None:
    """确保 SQLite 数据库目录存在，避免 'unable to open database file' 错误。"""
    db_path = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
    data_dir = db_path.parent
    if data_dir and not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created data directory: {data_dir}")


def _create_default_superadmin() -> None:
    """创建默认 superadmin 账户（仅开发环境）。"""
    db: Session = SessionLocal()
    try:
        # 检查是否已存在 superadmin
        existing = db.query(User).filter(User.role == "superadmin").first()
        if not existing:
            # 创建默认 superadmin
            superadmin = User(
                username="superadmin",
                email=None,
                nickname="超级管理员",
                role="superadmin",
                hashed_password=get_password_hash("superadmin123"),
                is_active=True,
                must_change_password=True,
                created_by=None,
            )
            db.add(superadmin)
            db.commit()
            print("默认 superadmin 已创建: superadmin / superadmin123")
    except Exception as e:
        db.rollback()
        print(f"创建默认 superadmin 失败: {e}")
    finally:
        db.close()
