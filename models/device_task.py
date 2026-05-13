"""
设备任务表：
- 用于将持续上传的传感器数据按“任务窗口”组织展示；
- 第一版状态流转：active -> finished -> deleted；
- 仅保存任务元数据，不复制传感器原始数据。
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, func

from database.session import Base


class DeviceTask(Base):
    """device_tasks 表 ORM。"""

    __tablename__ = "device_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    device_id = Column(String(128), nullable=False, index=True, comment="设备标识")
    task_name = Column(String(128), nullable=False, comment="任务名称")

    temp_min = Column(Float, nullable=True, comment="任务温区下限")
    temp_max = Column(Float, nullable=True, comment="任务温区上限")

    # active | finished | deleted
    status = Column(String(16), nullable=False, default="active", comment="任务状态")

    # 曲线归属边界（精确归属依赖 id 窗口，不依赖时间解析）
    start_record_id = Column(Integer, nullable=False, default=0, comment="任务创建时该设备最新记录ID")
    end_record_id = Column(Integer, nullable=True, comment="任务结束时该设备最新记录ID")

    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="任务开始时间")
    ended_at = Column(DateTime(timezone=True), nullable=True, comment="任务结束时间")
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment="任务删除时间（逻辑删除）")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_device_tasks_device_status", "device_id", "status"),
        Index("ix_device_tasks_device_started", "device_id", "started_at"),
    )
