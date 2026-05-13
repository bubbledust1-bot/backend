"""系统健康检查。"""

from __future__ import annotations

from fastapi import APIRouter

from config import settings

router = APIRouter()


@router.get("/health", tags=["系统"])
def health_check():
    """供前端、ESP32 或运维探活。"""
    return {
        "status": "ok",
        "message": "服务运行正常",
        "debug": settings.DEBUG,
    }
