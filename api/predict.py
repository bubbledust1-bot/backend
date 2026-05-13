"""
预测接口：接收任意 JSON 对象（dict），原样交给 algorithm，不落业务校验。

请求体不使用固定 7 字段模型，避免与 algorithm 的别名/校验逻辑重复。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from models.user import User
from services.prediction_service import run_predict_and_persist

router = APIRouter()


@router.post(
    "/predict",
    summary="材料参数预测抗压强度",
)
def predict(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
    # 整段 JSON 解析为 dict，不做字段级 Pydantic 强校验
    payload: dict[str, Any] = Body(
        ...,
        openapi_examples={
            "示例": {
                "summary": "标准字段示例",
                "value": {
                    "Day": 28,
                    "L/S Ratio": 0.09,
                    "Aggregate Ratio": 0.83,
                    "Active Ratio": 0.17,
                    "Activation Index": 0.01,
                    "Si-Al Ratio": 0.5,
                    "Ca Ratio": 0.5,
                },
            }
        },
    ),
) -> dict[str, Any]:
    """
    流程：
    1. 将 payload 原样交给 predict_strength；
    2. 将前端原始请求体深拷贝写入 raw_input_json；
    3. 无论 algorithm.success 是否为 true，均 HTTP 200 返回（第一阶段约定），并附带 record_id。

    若数据库写入失败，返回 500 与中文说明（此时无 record_id）。
    """
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="请求体必须是 JSON 对象（{}），不能是数组或纯字符串。",
        )
    try:
        return run_predict_and_persist(db, payload)
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"保存预测记录失败，请稍后重试。数据库错误：{type(e).__name__}: {e}",
        ) from e
