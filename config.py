"""
backend 全局配置：从环境变量与 .env 文件读取，便于本地开发与云端切换。

使用方式：
    from config import settings

云端部署时通常只需修改：
    - DATABASE_URL（例如 PostgreSQL）
    - CORS_ORIGINS（前端公网域名）
    - APP_HOST / APP_PORT（或由反向代理处理，仅进程监听）
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 始终优先读取 backend 目录下的 .env，避免「从项目根启动时找不到配置」
_BACKEND_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """
    所有可配置项集中在此，避免在业务代码里写死字符串。

    优先级：环境变量 > backend/.env > 下方默认值。
    """

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 监听地址：本地开发常用 0.0.0.0 以便局域网内手机/ESP32 访问
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # SQLite：路径相对于「启动进程当前工作目录」。
    DATABASE_URL: str = "sqlite:///data/deepsight.db"

    # 逗号分隔的前端来源，用于 CORS；本地 Vite 默认 5173
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:3000,http://127.0.0.1:3000"
    )

    DEBUG: bool = False

    # JWT 密钥（生产环境必须通过环境变量设置强密钥）
    SECRET_KEY: str = "deepsight-syncore-dev-secret-key-please-change-in-production"

    # API 文档控制
    # 开发环境：默认启用标准 docs / redoc / openapi.json
    # 生产环境：默认完全关闭，可选启用受保护的自定义 docs
    ENABLE_STANDARD_DOCS: bool = True  # 控制 /docs, /redoc, /openapi.json
    ENABLE_PROTECTED_DOCS: bool = False  # 控制自定义受保护 docs
    PROTECTED_DOCS_PATH: str = "/protected-docs"  # 自定义受保护 docs 路径

    @field_validator("APP_PORT")
    @classmethod
    def port_in_range(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("APP_PORT 必须在 1~65535 之间")
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """将 CORS_ORIGINS 解析为列表，供 CORSMiddleware 使用。"""
        return [x.strip() for x in self.CORS_ORIGINS.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    """进程内单例，避免重复解析 .env。"""
    return Settings()


# 供各模块直接导入的默认实例
settings = get_settings()
