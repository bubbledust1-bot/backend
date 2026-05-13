"""
传感器 REST：上传、最新一条、历史列表。

WebSocket 广播在路由层于「数据库提交成功后」通过 BackgroundTasks 触发。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.deps import get_db
from schemas.device_task import (
    DeviceTaskActionResponse,
    DeviceTaskCreateBody,
    DeviceTaskListResponse,
    DeviceTaskRecordsResponse,
)
from schemas.sensor import SensorUploadBody, SensorUploadResponse
from services.device_task_service import (
    create_device_task,
    delete_device_task,
    device_task_to_dict,
    finish_device_task,
    get_task_records,
    list_active_tasks,
    list_device_tasks,
)
from services.sensor_service import (
    calculate_temperature_status,
    create_sensor_record,
    get_device_summaries,
    get_latest_sensor,
    get_sensor_history,
    sensor_record_to_dict,
)
from services.ws_manager import sensor_ws_manager

router = APIRouter(prefix="/sensor", tags=["传感器"])

# 查询默认条数与上限（防止一次拉取过大）
_DEFAULT_LIMIT = 50
_DEFAULT_DEVICE_SUMMARY_LIMIT = 200
_DEFAULT_TASK_LIST_LIMIT = 5
_MAX_LIMIT = 500


@router.post("/upload", response_model=SensorUploadResponse)
def upload_sensor(
    background_tasks: BackgroundTasks,
    body: SensorUploadBody,
    db: Session = Depends(get_db),
) -> SensorUploadResponse:
    """
    ESP32 / 前端上传传感器数据。

    字段语义（保持向后兼容）：
    - temperature：环境温度（保持原有语义不变）
    - humidity：环境湿度（保持原有语义不变）
    - material_temperature：材料内部温度（新增字段）
    - strain：应变（已存在）

    兼容字段：
    - env_temperature：环境温度（若 temperature 为 None 则用这个）
    - env_humidity：环境湿度（若 humidity 为 None 则用这个）

    - device_id 必填；其余字段可省略；
    - 成功 commit 后，将同一条记录广播给所有 WebSocket 连接（BackgroundTasks，保证在落库之后调度）；
    - 返回 temperature_status（基于 material_temperature 判断）。
    """
    full_payload: dict[str, Any] = body.model_dump(mode="python")
    
    # 打印接收到的 payload（用于调试）
    print("[backend /upload] 接收到 payload:", full_payload)

    did = body.device_id.strip()
    if not did:
        raise HTTPException(status_code=400, detail="device_id 不能为空字符串。")

    # 兼容处理：优先用 env_temperature 和 env_humidity
    temp_val = body.temperature
    humid_val = body.humidity
    
    # 如果 temperature 为 None 但有 env_temperature，用 env_temperature
    if temp_val is None and "env_temperature" in full_payload:
        temp_val = full_payload["env_temperature"]
        print("[backend /upload] 使用 env_temperature:", temp_val)
    
    # 如果 humidity 为 None 但有 env_humidity，用 env_humidity
    if humid_val is None and "env_humidity" in full_payload:
        humid_val = full_payload["env_humidity"]
        print("[backend /upload] 使用 env_humidity:", humid_val)

    try:
        record = create_sensor_record(
            db,
            device_id=did,
            # 环境温湿度（保持原有语义不变）
            temperature=temp_val,
            humidity=humid_val,
            # 材料温度（新增字段）
            material_temperature=body.material_temperature,
            # 其他字段
            pressure=body.pressure,
            strain=body.strain,
            curing_status=body.curing_status,
            raw_payload=full_payload,
        )
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"保存传感器数据失败：{type(e).__name__}: {e}",
        ) from e

    # 计算 temperature_status（基于 material_temperature）
    temperature_status = calculate_temperature_status(body.material_temperature)
    
    # 获取服务器当前时间
    server_time = datetime.now().isoformat()

    # 仅在成功落库后广播（BackgroundTasks 在响应发送后执行，此时事务已提交）
    payload_for_ws = sensor_record_to_dict(record)
    background_tasks.add_task(sensor_ws_manager.broadcast_json, payload_for_ws)

    return SensorUploadResponse(
        success=True,
        id=record.id,
        message="传感器数据已保存",
        temperature_status=temperature_status,
        server_time=server_time,
    )


@router.get("/latest")
def sensor_latest(
    db: Session = Depends(get_db),
    device_id: Optional[str] = Query(None, description="可选；不传则返回全局最新一条"),
) -> dict[str, Any]:
    """返回最新一条传感器记录；若无数据返回 {\"item\": null}。"""
    row = get_latest_sensor(db, device_id=device_id)
    if row is None:
        return {"item": None, "message": "暂无传感器数据"}
    return {"item": sensor_record_to_dict(row)}


@router.get("/history")
def sensor_history(
    db: Session = Depends(get_db),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT, description="返回条数上限"),
    device_id: Optional[str] = Query(None, description="可选；不传则返回全局历史"),
) -> dict[str, Any]:
    """按时间倒序返回最近 limit 条。"""
    rows = get_sensor_history(db, limit=limit, device_id=device_id)
    items = [sensor_record_to_dict(r) for r in rows]
    return {"items": items, "count": len(items)}


@router.get("/devices")
def sensor_devices(
    db: Session = Depends(get_db),
    with_latest: bool = Query(True, description="是否包含每个设备 latest 详情"),
    limit: int = Query(
        _DEFAULT_DEVICE_SUMMARY_LIMIT,
        ge=1,
        le=_MAX_LIMIT,
        description="设备摘要返回上限（防误传过大）",
    ),
) -> dict[str, Any]:
    """
    多设备摘要：返回设备列表与每设备最新一条状态（可选）。

    - 只读新增，不影响已有 /latest /history /upload /ws。
    - 无数据时返回 success:true + items:[]。
    """
    items = get_device_summaries(db, with_latest=with_latest, limit=limit)
    return {
        "success": True,
        "items": items,
        "total": len(items),
    }


@router.post("/tasks", response_model=DeviceTaskActionResponse)
def create_task(
    body: DeviceTaskCreateBody,
    db: Session = Depends(get_db),
) -> DeviceTaskActionResponse:
    """创建设备任务：同设备同一时刻仅允许一个 active。"""
    try:
        row = create_device_task(
            db,
            device_id=body.device_id,
            task_name=body.task_name,
            temp_min=body.temp_min,
            temp_max=body.temp_max,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"创建任务失败：{e}") from e

    return DeviceTaskActionResponse(success=True, message="任务已创建", item=device_task_to_dict(row))


@router.post("/tasks/{task_id}/finish", response_model=DeviceTaskActionResponse)
def finish_task(task_id: int, db: Session = Depends(get_db)) -> DeviceTaskActionResponse:
    """结束任务：active -> finished。"""
    try:
        row = finish_device_task(db, task_id=task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"结束任务失败：{e}") from e

    return DeviceTaskActionResponse(success=True, message="任务已结束", item=device_task_to_dict(row))


@router.delete("/tasks/{task_id}", response_model=DeviceTaskActionResponse)
def remove_task(task_id: int, db: Session = Depends(get_db)) -> DeviceTaskActionResponse:
    """删除任务（逻辑删除）：第一版仅允许删除 finished。"""
    try:
        row = delete_device_task(db, task_id=task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"删除任务失败：{e}") from e

    return DeviceTaskActionResponse(success=True, message="任务已删除", item=device_task_to_dict(row))


@router.get("/tasks", response_model=DeviceTaskListResponse)
def get_tasks(
    db: Session = Depends(get_db),
    device_id: Optional[str] = Query(None, description="可选：按设备筛选"),
    limit: int = Query(_DEFAULT_TASK_LIST_LIMIT, ge=1, le=50, description="返回条数（默认最近5条）"),
) -> DeviceTaskListResponse:
    """任务列表（默认不含 deleted）。"""
    rows = list_device_tasks(db, device_id=device_id, include_deleted=False, limit=limit)
    items = [device_task_to_dict(r) for r in rows]
    return DeviceTaskListResponse(success=True, items=items, total=len(items))


@router.get("/tasks/active", response_model=DeviceTaskListResponse)
def get_active(
    db: Session = Depends(get_db),
    device_id: Optional[str] = Query(None, description="可选：按设备筛选"),
) -> DeviceTaskListResponse:
    rows = list_active_tasks(db, device_id=device_id)
    items = [device_task_to_dict(r) for r in rows]
    return DeviceTaskListResponse(success=True, items=items, total=len(items))


@router.get("/tasks/{task_id}/records", response_model=DeviceTaskRecordsResponse)
def task_records(
    task_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(_MAX_LIMIT, ge=1, le=2000, description="任务记录返回上限"),
) -> DeviceTaskRecordsResponse:
    """按任务窗口查询曲线数据，用于刷新恢复和历史任务查看。"""
    try:
        task, items = get_task_records(db, task_id=task_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"读取任务记录失败：{e}") from e

    return DeviceTaskRecordsResponse(success=True, task=task, items=items, total=len(items))
