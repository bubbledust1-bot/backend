"""设备任务相关 schema（第一版最小实现）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DeviceTaskCreateBody(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=128)
    task_name: str = Field(..., min_length=1, max_length=128)
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None


class DeviceTaskItem(BaseModel):
    id: int
    device_id: str
    task_name: str
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    status: str
    start_record_id: int = 0
    end_record_id: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DeviceTaskActionResponse(BaseModel):
    success: bool
    message: str
    item: Optional[dict[str, Any]] = None


class DeviceTaskListResponse(BaseModel):
    success: bool
    items: list[dict[str, Any]]
    total: int


class DeviceTaskRecordsResponse(BaseModel):
    success: bool
    task: dict[str, Any]
    items: list[dict[str, Any]]
    total: int
