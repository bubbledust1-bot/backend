"""
传感器记录表：ESP32 通过 HTTP POST 上传，供列表查询与 WebSocket 推送。

数值字段允许为空，便于分阶段接入不同传感器。
"""

from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, Float, Index, Integer, String, Text, func

from database.session import Base


class SensorRecord(Base):
    """sensor_records 表 ORM。"""

    __tablename__ = "sensor_records"

    id = Column(Integer, primary_key=True, autoincrement=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="服务端收到数据的时间",
    )

    device_id = Column(String(128), nullable=False, index=True, comment="设备标识，如 ESP32 MAC 或自定义 ID")

    # 环境温湿度（保持原有语义不变）
    temperature = Column(Float, nullable=True, comment="环境温度，单位由业务约定（如 ℃）")
    humidity = Column(Float, nullable=True, comment="环境湿度")

    # 材料温度（新增字段）
    material_temperature = Column(Float, nullable=True, comment="材料内部温度")

    # 其他字段
    pressure = Column(Float, nullable=True, comment="压力")
    strain = Column(Float, nullable=True, comment="应变")
    curing_status = Column(String(64), nullable=True, comment="养护状态简短描述")

    # 原始请求体，便于以后扩展字段而不改表结构
    raw_payload_json = Column(JSON, nullable=True, comment="上传时的完整 JSON")

    __table_args__ = (Index("ix_sensor_records_device_created", "device_id", "created_at"),)


# 注：device_id 上已有 index=True；复合索引用于按设备按时间查询历史（第二轮 API 使用）。
