"""
预测业务：调用 algorithm.predict_strength，落库 prediction_records，组装 API 响应。

注意：
- 不做任何与 algorithm 重复的业务校验；
- raw_input_json 必须为「前端原始请求体」的深拷贝，不在本层改写后再存。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from algorithm.predictor import predict_strength

from models.prediction_record import PredictionRecord


def run_predict_and_persist(db: Session, raw_request_body: dict[str, Any]) -> dict[str, Any]:
    """
    执行预测并写入数据库。

    参数：
        raw_request_body：已通过 FastAPI 解析的 JSON 对象（dict）。
        本函数首先 deepcopy 再保存到 raw_input_json，避免后续任何环节误改「原始留痕」。

    返回：
        供 HTTP 200 直接 JSON 序列化的 dict：
        - 包含 algorithm 返回的主要字段（原样透传）；
        - 额外包含 record_id；
        - success 为 false 时仍有 record_id（只要落库成功）。
    """
    # 与前端请求体内容一致，供复盘
    raw_snapshot: dict[str, Any] = deepcopy(raw_request_body)

    # 调用算法（入参与前端 JSON 一致；不在 backend 改写 dict）
    algo_result = predict_strength(raw_request_body)

    # 从 algorithm 契约读取字段（不假设多余键）
    success = bool(algo_result.get("success"))
    warnings = algo_result.get("warnings")
    if warnings is None:
        warnings = algo_result.get("warning")

    row = PredictionRecord(
        raw_input_json=raw_snapshot,
        normalized_input_json=algo_result.get("normalized_input"),
        input_for_model_json=algo_result.get("input_for_model"),
        prediction_mpa=algo_result.get("prediction_mpa"),
        success=success,
        warning_json=warnings,
        error_message=algo_result.get("error"),
        model_version=algo_result.get("model_version"),
        explain_json=algo_result.get("explain"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # API 响应：algorithm 全量透传 + record_id（不修改 algorithm 内部结构）
    response: dict[str, Any] = dict(algo_result)
    response["record_id"] = row.id
    return response
