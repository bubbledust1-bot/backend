"""
传感器业务：写入 sensor_records；查询最新/历史；序列化为 API 字典。

WebSocket 广播不在此函数内执行，由路由在 commit 成功后通过 BackgroundTasks 调用，
确保「先落库、再推送」。
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from models.sensor_record import SensorRecord


# ========== 配置常量：材料温度正常范围 ==========
MATERIAL_TEMP_NORMAL_MIN = 10.0  # 正常范围最小值（可调整）
MATERIAL_TEMP_NORMAL_MAX = 45.0  # 正常范围最大值（可调整）


def calculate_temperature_status(material_temperature: Optional[float]) -> Optional[str]:
    """
    计算 temperature_status：
    - 优先根据 material_temperature 判断
    - 在正常范围内 → "normal"
    - 超出范围 → "alert"
    - 没有 material_temperature → "unknown"
    """
    if material_temperature is None:
        return "unknown"
    
    if MATERIAL_TEMP_NORMAL_MIN <= material_temperature <= MATERIAL_TEMP_NORMAL_MAX:
        return "normal"
    else:
        return "alert"


def sensor_record_to_dict(row: SensorRecord) -> dict[str, Any]:
    """
    将 ORM 行转为可 JSON 序列化的 dict（时间转 ISO 字符串），
    新增 material_temperature 字段。
    """
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "device_id": row.device_id,
        # 环境温湿度（保持原有语义不变）
        "temperature": row.temperature,
        "humidity": row.humidity,
        # 材料温度（新增字段）
        "material_temperature": getattr(row, "material_temperature", None),
        # 其他字段
        "pressure": row.pressure,
        "strain": row.strain,
        "curing_status": row.curing_status,
        "raw_payload_json": row.raw_payload_json,
        # temperature_status（动态计算）
        "temperature_status": calculate_temperature_status(getattr(row, "material_temperature", None)),
    }


def create_sensor_record(
    db: Session,
    *,
    device_id: str,
    # 环境温湿度（保持原有语义不变）
    temperature: Optional[float] = None,
    humidity: Optional[float] = None,
    # 材料温度（新增字段）
    material_temperature: Optional[float] = None,
    # 其他字段
    pressure: Optional[float] = None,
    strain: Optional[float] = None,
    curing_status: Optional[str] = None,
    raw_payload: Optional[dict[str, Any]] = None,
) -> SensorRecord:
    """
    创建并持久化一条传感器记录（内部 commit + refresh），
    新增 material_temperature 支持。

    返回：
        已写入数据库的 SensorRecord（含 id）。
    """
    row = SensorRecord(
        device_id=device_id,
        # 环境温湿度（保持原有语义不变）
        temperature=temperature,
        humidity=humidity,
        # 材料温度（新增字段）
        material_temperature=material_temperature,
        # 其他字段
        pressure=pressure,
        strain=strain,
        curing_status=curing_status,
        raw_payload_json=raw_payload,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_latest_sensor(db: Session, device_id: Optional[str] = None) -> Optional[SensorRecord]:
    """最新一条；device_id 为空则全局最新。"""
    q = db.query(SensorRecord)
    if device_id is not None and device_id != "":
        q = q.filter(SensorRecord.device_id == device_id)
    return q.order_by(SensorRecord.created_at.desc()).first()


def get_sensor_history(
    db: Session,
    *,
    limit: int = 50,
    device_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> list[SensorRecord]:
    """
    最近若干条，按时间倒序。
    limit 会在路由层限制上限，避免一次拉取过大。
    新增 start_time 和 end_time 支持时间范围查询。
    """
    q = db.query(SensorRecord)
    if device_id is not None and device_id != "":
        q = q.filter(SensorRecord.device_id == device_id)
    if start_time:
        q = q.filter(SensorRecord.created_at >= start_time)
    if end_time:
        q = q.filter(SensorRecord.created_at <= end_time)
    return q.order_by(SensorRecord.created_at.desc(), SensorRecord.id.desc()).limit(limit).all()


def get_device_summaries(
    db: Session,
    *,
    with_latest: bool = True,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    返回多设备摘要：每个 device_id 一条最新记录（created_at 相同用 id 兜底）。

    说明：
    - 忽略空 device_id（NULL/空字符串/纯空白）；
    - with_latest=False 时仅返回 device_id + last_seen_at；
    - latest 结构复用 sensor_record_to_dict，保持前端字段风格一致。
    """
    base = db.query(SensorRecord).filter(
        SensorRecord.device_id.isnot(None),
        func.trim(SensorRecord.device_id) != "",
    )

    # 先取每个设备最新时间
    latest_time_sq = (
        base.with_entities(
            SensorRecord.device_id.label("device_id"),
            func.max(SensorRecord.created_at).label("max_created_at"),
        )
        .group_by(SensorRecord.device_id)
        .subquery()
    )

    # 若同一设备同一 created_at 有多条，取 id 最大的一条作为稳定兜底
    tie_break_sq = (
        db.query(
            SensorRecord.device_id.label("device_id"),
            SensorRecord.created_at.label("created_at"),
            func.max(SensorRecord.id).label("max_id"),
        )
        .join(
            latest_time_sq,
            and_(
                SensorRecord.device_id == latest_time_sq.c.device_id,
                SensorRecord.created_at == latest_time_sq.c.max_created_at,
            ),
        )
        .group_by(SensorRecord.device_id, SensorRecord.created_at)
        .subquery()
    )

    latest_rows = (
        db.query(SensorRecord)
        .join(
            tie_break_sq,
            and_(
                SensorRecord.device_id == tie_break_sq.c.device_id,
                SensorRecord.created_at == tie_break_sq.c.created_at,
                SensorRecord.id == tie_break_sq.c.max_id,
            ),
        )
        .order_by(SensorRecord.created_at.desc(), SensorRecord.id.desc())
        .limit(limit)
        .all()
    )

    out: list[dict[str, Any]] = []
    for row in latest_rows:
        item: dict[str, Any] = {
            "device_id": row.device_id,
            "latest_created_at": row.created_at.isoformat() if row.created_at else None,
            "latest_temperature": row.temperature,  # 环境温度
            "latest_humidity": row.humidity,
            "latest_material_temperature": getattr(row, "material_temperature", None),
            "latest_strain": row.strain,
            "latest_temperature_status": calculate_temperature_status(getattr(row, "material_temperature", None)),
        }
        if with_latest:
            item["latest"] = sensor_record_to_dict(row)
        out.append(item)

    return out
