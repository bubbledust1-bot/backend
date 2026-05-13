"""
统一预测入口：供后端 import 后直接调用。

主函数：predict_strength(input_dict)
别名：predict（与部分文档表述一致）
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from . import config
from .domain_guard import collect_warnings, validate_normalized_types
from .feature_adapter import adapt_platform_input, build_feature_vector
from .input_schema import MODEL_FEATURE_ORDER, describe_fields
from .load_model import get_model_and_feature_order


def _empty_result(
    success: bool,
    error: Optional[str] = None,
    adapter_warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """失败时返回统一结构，字段齐全便于前端判断。"""
    aw = list(adapter_warnings or [])
    return {
        "success": success,
        "prediction_mpa": None,
        "predicted_strength": None,
        "unit": "MPa",
        "warning": aw,
        "warnings": aw,
        "input_for_model": None,
        "normalized_input": None,
        "model_version": config.MODEL_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "explain": None,
        "error": error,
    }


def predict_strength(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据平台输入预测抗压强度（MPa）。

    参数：
        input_dict：平台传入的字典，键可为标准英文名或别名（见 input_schema）。

    返回：
        成功时 success=True，prediction_mpa 与 predicted_strength 相同；
        warning / warnings 均为列表（内容相同，兼容不同调用方）；
        input_for_model 为按模型顺序排列的 7 个 float；
        explain 含简要摘要便于前端展示。

        失败时 success=False，error 为可读中文说明，prediction_mpa 为 None。
    """
    adapter_warnings: List[str] = []

    try:
        normalized, adapter_warnings = adapt_platform_input(input_dict)
        validate_normalized_types(normalized)
        domain_warnings = collect_warnings(normalized)
        all_warnings = list(adapter_warnings) + list(domain_warnings)

        feature_vector = build_feature_vector(normalized)
        model, feature_order = get_model_and_feature_order()

        # 使用带列名的 DataFrame，避免 sklearn「无特征名」告警（模型在训练时使用了列名）
        X = pd.DataFrame([feature_vector], columns=feature_order)
        raw_pred = model.predict(X)
        if raw_pred is None or len(raw_pred) == 0:
            raise RuntimeError("模型返回空预测结果，请检查模型文件是否损坏。")
        mpa = float(raw_pred[0])
        if not (mpa == mpa):  # NaN
            raise RuntimeError("模型输出为非数字（NaN），请检查输入特征是否异常。")

        explain = {
            "feature_order": list(MODEL_FEATURE_ORDER),
            "input_summary": {k: normalized[k] for k in MODEL_FEATURE_ORDER},
            "field_descriptions": {k: d for k, d in describe_fields()},
            "note": "上表为送入模型的最终数值；可与表单或实验记录人工核对。",
        }

        return {
            "success": True,
            "prediction_mpa": mpa,
            "predicted_strength": mpa,
            "unit": "MPa",
            "warning": all_warnings,
            "warnings": all_warnings,
            "input_for_model": feature_vector,
            "normalized_input": {k: normalized[k] for k in MODEL_FEATURE_ORDER},
            "model_version": config.MODEL_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "explain": explain,
            "error": None,
        }
    except ValueError as e:
        return _empty_result(False, error=str(e), adapter_warnings=adapter_warnings)
    except FileNotFoundError as e:
        return _empty_result(False, error=str(e), adapter_warnings=adapter_warnings)
    except RuntimeError as e:
        return _empty_result(False, error=str(e), adapter_warnings=adapter_warnings)
    except Exception as e:
        return _empty_result(
            False,
            error=f"预测过程发生未预期错误：{type(e).__name__}: {e}",
            adapter_warnings=adapter_warnings,
        )


def predict(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    """与 predict_strength 相同，便于文档中简称 predict。"""
    return predict_strength(input_dict)
