"""
WebSocket 连接管理：传感器新数据在「数据库 commit 成功之后」再广播。

说明：
- 广播函数为 async，由 FastAPI BackgroundTasks 在响应发送后调度执行；
- 若需改为「响应前广播」，可在路由里 await（需将上传接口改为 async 并自行处理线程池中的 DB）。
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket


class SensorConnectionManager:
    """维护当前所有已连接的 /ws/sensor 客户端。"""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast_json(self, payload: dict[str, Any]) -> None:
        """
        向所有连接推送一条 JSON 文本消息。

        发送失败的连接会被移除，避免僵尸连接占满列表。
        """
        text = json.dumps(payload, ensure_ascii=False, default=str)
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# 进程内单例，供 sensor 上传与 WebSocket 路由共用
sensor_ws_manager = SensorConnectionManager()
