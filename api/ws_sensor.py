"""
WebSocket：/ws/sensor

前端连接后，在每次 POST /api/sensor/upload 成功落库并 commit 后，
由 BackgroundTasks 调用 broadcast_json 推送与 GET /api/sensor/latest 结构一致的 item。
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.ws_manager import sensor_ws_manager

router = APIRouter()


@router.websocket("/ws/sensor")
async def websocket_sensor(websocket: WebSocket) -> None:
    """
    建立长连接；当前阶段不要求客户端发送心跳。

    服务端在有新传感器记录时主动 push JSON 文本（与 item 字典序列化一致）。
    """
    await sensor_ws_manager.connect(websocket)
    try:
        while True:
            # 读取客户端消息，防止部分代理空闲断开；收到内容可忽略
            await websocket.receive_text()
    except WebSocketDisconnect:
        sensor_ws_manager.disconnect(websocket)
    except Exception:
        sensor_ws_manager.disconnect(websocket)
