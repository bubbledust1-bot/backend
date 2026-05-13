"""
DeepSight SynCore — FastAPI 应用入口。

职责：
- 加载配置、初始化数据库表
- 配置 CORS，供前端开发联调
- 配置 API 文档访问控制
- 认证和账户管理路由

启动方式（在项目根目录「项目开发」下执行）：
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

说明：
- 必须能从项目根 import algorithm 与 backend，请勿在 backend 目录内单独作为包根运行，
  除非已正确设置 PYTHONPATH。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.health import router as health_router
from api.predict import router as predict_router
from api.sensor import router as sensor_router
from api.training import router as training_router
from api.ws_sensor import router as ws_sensor_router
from api.auth import router as auth_router
from api.admin import router as admin_router
from config import settings
from database.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期：启动时建表，关闭时暂无清理逻辑。
    """
    init_db()
    yield


# 根据配置决定是否启用标准 docs
app_kwargs = {}
if not settings.ENABLE_STANDARD_DOCS:
    app_kwargs["docs_url"] = None
    app_kwargs["redoc_url"] = None
    app_kwargs["openapi_url"] = None

app = FastAPI(
    title="DeepSight SynCore API",
    description="深眸智链 — AI 工作台后端 API",
    version="0.2.0",
    lifespan=lifespan,
    debug=settings.DEBUG,
    **app_kwargs,
)

# ---------- CORS：前端与局域网设备访问 ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- REST 与 WebSocket 路由 ----------
# 公开接口（无需认证）
app.include_router(health_router, prefix="/api")

# 认证路由
app.include_router(auth_router, prefix="/api")

# 账户管理路由（仅 superadmin）
app.include_router(admin_router, prefix="/api")

# 业务 API（Phase A+ 需要认证）
# 注意：训练、预测等接口现在需要认证
app.include_router(training_router, prefix="/api")
app.include_router(predict_router, prefix="/api")

# 传感器上报接口（暂不纳入用户认证，后续单独设计）
app.include_router(sensor_router, prefix="/api")

# WebSocket 路径为 /ws/sensor，不加 /api 前缀
app.include_router(ws_sensor_router)
