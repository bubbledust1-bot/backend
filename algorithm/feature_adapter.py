"""
将平台传入的字典转换为模型使用的标准键名与数值类型。

职责：
- 键名：别名映射、禁止未知键、检测重复（同一标准键来自多个原始键）。
- 数值：Day 转 int；比例类在 (1, 100] 时按百分数÷100，并记录 warning。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from .input_schema import (
    MODEL_FEATURE_ORDER,
    MODEL_KEY_SET,
    PERCENT_LIKE_KEYS,
    canonical_key,
)


def adapt_platform_input(raw: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    将平台原始输入转为标准模型键 -> 值。

    返回：
        (normalized_dict, adapter_warnings)

    抛出：
        ValueError：未知字段、重复字段、缺少字段、类型无法转换等（带清晰中文说明）。
    """
    if not isinstance(raw, dict):
        raise ValueError("输入必须是 JSON 对象/ Python 字典，不能是列表或单个数字。")

    # 原始键 -> 标准键 的多对一检测
    canonical_sources: Dict[str, List[str]] = {}
    normalized: Dict[str, Any] = {}
    warnings: List[str] = []

    for raw_key, value in raw.items():
        if not isinstance(raw_key, str):
            raise ValueError(f"字段名必须是字符串，当前得到：{type(raw_key).__name__}")
        std_key = canonical_key(raw_key)
        if std_key not in MODEL_KEY_SET:
            raise ValueError(
                f"存在未知字段「{raw_key}」。仅允许以下字段（或其别名）：{', '.join(MODEL_FEATURE_ORDER)}。"
            )
        canonical_sources.setdefault(std_key, []).append(raw_key)
        if std_key in normalized:
            # 同一标准键出现两次
            raise ValueError(
                f"字段重复：「{raw_key}」与「{canonical_sources[std_key][0]}」都对应「{std_key}」，请只保留一个。"
            )
        normalized[std_key] = value

    missing = [k for k in MODEL_FEATURE_ORDER if k not in normalized]
    if missing:
        raise ValueError(
            "缺少必填字段："
            + "、".join(missing)
            + "。\n请提供全部 7 个特征；可使用中文或英文别名，见 algorithm_readme.txt。"
        )

    # 类型与 Day、百分数转换
    out: Dict[str, Any] = {}
    for key in MODEL_FEATURE_ORDER:
        val = normalized[key]
        if key == "Day":
            out[key], w = _coerce_day(val)
        else:
            out[key], w = _coerce_ratio(key, val)
        warnings.extend(w)

    return out, warnings


def _coerce_day(val: Any) -> Tuple[int, List[str]]:
    warnings: List[str] = []
    if val is None:
        raise ValueError("字段「Day」不能为空。")
    if isinstance(val, bool):
        raise ValueError("字段「Day」不能是布尔值，请填整数天数。")
    if isinstance(val, int):
        day = val
    elif isinstance(val, float):
        if not math.isfinite(val):
            raise ValueError("字段「Day」必须是有限数字。")
        if not val.is_integer():
            raise ValueError(
                f"字段「Day」必须为整数天，当前为小数：{val}。若需四舍五入请在前端或后端先处理好。"
            )
        day = int(val)
        warnings.append("已将 Day 从浮点数转换为整数；建议平台直接传整数。")
    else:
        raise ValueError(
            f"字段「Day」类型错误：需要整数，当前为 {type(val).__name__}。"
        )
    if day < 1:
        raise ValueError(f"字段「Day」必须 ≥ 1，当前为 {day}。")
    return day, warnings


def _coerce_ratio(key: str, val: Any) -> Tuple[float, List[str]]:
    warnings: List[str] = []
    if val is None:
        raise ValueError(f"字段「{key}」不能为空。")
    if isinstance(val, bool):
        raise ValueError(f"字段「{key}」不能是布尔值，请填数字。")
    if isinstance(val, int):
        num = float(val)
    elif isinstance(val, float):
        num = val
    else:
        raise ValueError(
            f"字段「{key}」类型错误：需要数字，当前为 {type(val).__name__}。"
        )
    if not math.isfinite(num):
        raise ValueError(f"字段「{key}」必须是有限数字，不能为无穷或非数字。")

    if key in PERCENT_LIKE_KEYS:
        # 典型误用：用户填 30 表示 30%
        if 1.0 < num <= 100.0:
            warnings.append(
                f"「{key}」的值为 {num}，已按「百分数」自动除以 100（→ {num/100.0}）。"
                f"若您本意已是小数，请直接传 0~1 之间的小数，避免歧义。"
            )
            num = num / 100.0
        elif num > 100.0:
            raise ValueError(
                f"字段「{key}」数值过大（{num}）。"
                "若表示百分数不应超过 100；若已是小数，请检查是否多乘了 100。"
            )

    return num, warnings


def build_feature_vector(model_dict: Dict[str, Any]) -> List[float]:
    """按 MODEL_FEATURE_ORDER 生成一维列表，供日志与返回体 input_for_model。"""
    vec: List[float] = []
    for k in MODEL_FEATURE_ORDER:
        v = model_dict[k]
        if k == "Day":
            vec.append(float(int(v)))
        else:
            vec.append(float(v))
    return vec
