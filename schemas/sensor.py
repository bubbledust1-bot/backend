"""
传感器 HTTP 请求体：仅校验 device_id 必填，其余可选；允许额外字段写入 raw_payload。

不引入多余抽象，满足「最小可运行」。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SensorUploadBody(BaseModel):
    """POST /api/sensor/upload 请求体。"""

    model_config = ConfigDict(extra="allow")

    device_id: str = Field(..., min_length=1, description="设备唯一标识，必填")
    
    # 环境温湿度（保持原有语义不变）
    temperature: Optional[float] = Field(None, description="环境温度，可选")
    humidity: Optional[float] = Field(None, description="环境湿度，可选")
    
    # 材料温度（新增字段）
    material_temperature: Optional[float] = Field(None, description="材料内部温度，可选")
    
    # 其他字段
    pressure: Optional[float] = Field(None, description="压力，可选")
    strain: Optional[float] = Field(None, description="应变，可选")
    curing_status: Optional[str] = Field(None, description="养护状态，可选")


class SensorUploadResponse(BaseModel):
    """上传成功后的响应，包含 temperature_status。"""

    success: bool = True
    id: int
    message: str = "传感器数据已保存"
    temperature_status: Optional[str] = Field(None, description="温度状态：normal/alert/unknown")
    server_time: Optional[str] = Field(None, description="服务器当前时间，ISO 格式")
