"""
设备任务服务层（第一版最小实现）。

关键约束：
- 同设备同一时刻仅允许一个 active；
- 状态流转：active -> finished -> deleted；
- active 不允许直接删除。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.device_task import DeviceTask
from models.sensor_record import SensorRecord
from services.sensor_service import sensor_record_to_dict


def _task_to_dict(row: DeviceTask) -> dict[str, Any]:
    return {
        "id": row.id,
        "device_id": row.device_id,
        "task_name": row.task_name,
        "temp_min": row.temp_min,
        "temp_max": row.temp_max,
        "status": row.status,
        "start_record_id": row.start_record_id,
        "end_record_id": row.end_record_id,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def create_device_task(
    db: Session,
    *,
    device_id: str,
    task_name: str,
    temp_min: Optional[float] = None,
    temp_max: Optional[float] = None,
) -> DeviceTask:
    """
    创建任务（原子约束）：
    - 通过 BEGIN IMMEDIATE 获取写锁，避免并发下同设备双 active。
    """
    did = (device_id or "").strip()
    if not did:
        raise ValueError("device_id 不能为空")

    tname = (task_name or "").strip()
    if not tname:
        raise ValueError("task_name 不能为空")

    if temp_min is not None and temp_max is not None and temp_min > temp_max:
        raise ValueError("任务温区下限不能大于上限")

    # SQLite 第一版最小并发保护：先显式拿写锁，再查 active + 创建。
    db.execute(text("BEGIN IMMEDIATE"))

    exists = (
        db.query(DeviceTask)
        .filter(DeviceTask.device_id == did, DeviceTask.status == "active")
        .first()
    )
    if exists is not None:
        raise ValueError(f"设备 {did} 已有进行中任务，请先结束")

    # 记录“该设备创建任务时”的最新记录ID，作为任务窗口下边界。
    latest_row = (
        db.query(SensorRecord)
        .filter(SensorRecord.device_id == did)
        .order_by(SensorRecord.id.desc())
        .first()
    )
    start_record_id = latest_row.id if latest_row is not None else 0

    row = DeviceTask(
        device_id=did,
        task_name=tname,
        temp_min=temp_min,
        temp_max=temp_max,
        status="active",
        start_record_id=start_record_id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"创建任务失败：{e}") from e

    db.refresh(row)
    return row


def finish_device_task(db: Session, *, task_id: int) -> DeviceTask:
    row = db.query(DeviceTask).filter(DeviceTask.id == task_id).first()
    if row is None or row.status == "deleted":
        raise ValueError("任务不存在")
    if row.status != "active":
        raise ValueError("仅进行中任务可结束")

    # 记录“该设备结束任务时”的最新记录ID，作为任务窗口上边界。
    latest_row = (
        db.query(SensorRecord)
        .filter(SensorRecord.device_id == row.device_id)
        .order_by(SensorRecord.id.desc())
        .first()
    )
    row.end_record_id = latest_row.id if latest_row is not None else row.start_record_id

    row.status = "finished"
    row.ended_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_device_task(db: Session, *, task_id: int) -> DeviceTask:
    """第一版约束：仅允许删除 finished 任务。"""
    row = db.query(DeviceTask).filter(DeviceTask.id == task_id).first()
    if row is None:
        raise ValueError("任务不存在")
    if row.status == "deleted":
        return row
    if row.status != "finished":
        raise ValueError("仅已结束任务可删除，请先结束任务")

    row.status = "deleted"
    row.deleted_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_device_tasks(
    db: Session,
    *,
    device_id: Optional[str] = None,
    include_deleted: bool = False,
    limit: int = 5,
) -> list[DeviceTask]:
    q = db.query(DeviceTask)
    if device_id:
        q = q.filter(DeviceTask.device_id == device_id)
    if not include_deleted:
        q = q.filter(DeviceTask.status != "deleted")
    return q.order_by(DeviceTask.started_at.desc(), DeviceTask.id.desc()).limit(limit).all()


def list_active_tasks(db: Session, *, device_id: Optional[str] = None) -> list[DeviceTask]:
    q = db.query(DeviceTask).filter(DeviceTask.status == "active")
    if device_id:
        q = q.filter(DeviceTask.device_id == device_id)
    return q.order_by(DeviceTask.started_at.desc(), DeviceTask.id.desc()).all()


def get_task_by_id(db: Session, *, task_id: int) -> Optional[DeviceTask]:
    return db.query(DeviceTask).filter(DeviceTask.id == task_id).first()


def get_task_records(
    db: Session,
    *,
    task_id: int,
    limit: int = 500,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    按任务窗口读取传感器记录（边界 ID 方案）：
    - device_id = 任务设备
    - id > start_record_id
    - 若任务已结束（或存在 end_record_id），则 id <= end_record_id

    说明：
    - started_at/ended_at 仍保留用于展示；
    - 曲线归属精确性以 ID 边界为准，避免时区解析误差。
    """
    task = get_task_by_id(db, task_id=task_id)
    if task is None or task.status == "deleted":
        raise ValueError("任务不存在")

    q = db.query(SensorRecord).filter(
        SensorRecord.device_id == task.device_id,
        SensorRecord.id > int(task.start_record_id or 0),
    )

    # active 任务无上界；finished 任务以 end_record_id 封口。
    end_id = task.end_record_id
    if end_id is not None:
        q = q.filter(SensorRecord.id <= int(end_id))

    rows = q.order_by(SensorRecord.id.asc()).limit(limit).all()

    return _task_to_dict(task), [sensor_record_to_dict(r) for r in rows]


def device_task_to_dict(row: DeviceTask) -> dict[str, Any]:
    return _task_to_dict(row)
