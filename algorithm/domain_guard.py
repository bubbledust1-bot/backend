"""
适用范围校验（domain guard）：

- 硬错误：违反必填、类型、明显非法值（在 adapter 之后仍应一致）。
- 软提醒 warning：超出训练数据经验范围、超出工程上常用的建议区间等。

注意：模型没有内置置信度；warning 仅表示「与训练分布差异大」，不保证外推误差。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import config
from .input_schema import MODEL_FEATURE_ORDER

# 养护天数：工程上常见的实验室/比赛观察区间（与训练最大 365 天不同，仅作提示）
DAY_SUGGESTED_MIN = 1
DAY_SUGGESTED_MAX = 90

# 比例类字段：训练数据中均为非负；>1 可能合法但少见，给 warning
RATIO_SOFT_UPPER = 1.0
RATIO_HARD_UPPER = 1.5  # 超过则认为明显异常，给 warning（仍允许预测，除非您改为 error）


def _load_training_ranges() -> Dict[str, Dict[str, float]]:
    path: Path = config.TRAINING_RANGES_PATH
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    out: Dict[str, Dict[str, float]] = {}
    for k in MODEL_FEATURE_ORDER:
        if k not in data or not isinstance(data[k], dict):
            continue
        lo = data[k].get("min")
        hi = data[k].get("max")
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
            out[k] = {"min": float(lo), "max": float(hi)}
    return out


_TRAINING_RANGES = _load_training_ranges()


def collect_warnings(normalized: Dict[str, Any]) -> List[str]:
    """
    根据训练包络与经验规则收集 warning（不抛异常）。
    """
    warnings: List[str] = []

    day = int(normalized["Day"])
    if day < DAY_SUGGESTED_MIN or day > DAY_SUGGESTED_MAX:
        warnings.append(
            f"提示：养护天数 Day={day} 超出常见建议范围 [{DAY_SUGGESTED_MIN}, {DAY_SUGGESTED_MAX}] 天。"
            f"模型训练数据中最大约 {_TRAINING_RANGES.get('Day', {}).get('max', 365)} 天，仍可预测，但外推风险更高。"
        )

    for key in MODEL_FEATURE_ORDER:
        if key == "Day":
            continue
        v = float(normalized[key])
        if v < 0:
            warnings.append(f"提示：「{key}」为负数（{v}），请确认物理意义是否正确。")

        if v > RATIO_SOFT_UPPER:
            if v <= RATIO_HARD_UPPER:
                warnings.append(
                    f"提示：「{key}」={v} 大于 1，若该比例在业务上应为 0~1 的小数，请检查是否误填百分数或单位。"
                )
            else:
                warnings.append(
                    f"提示：「{key}」={v} 明显偏大（>{RATIO_HARD_UPPER}），预测可能不可靠，请核对输入。"
                )

        env = _TRAINING_RANGES.get(key)
        if env:
            lo, hi = env["min"], env["max"]
            eps = 1e-9
            if v < lo - eps or v > hi + eps:
                warnings.append(
                    f"提示：「{key}」={v} 超出训练数据常见范围 [{lo:.6g}, {hi:.6g}]，"
                    "属于外推区域，预测值仅供参考。"
                )

    return warnings


def validate_normalized_types(normalized: Dict[str, Any]) -> None:
    """adapter 之后再次确认类型（双保险，错误信息给后端/测试）。"""
    for k in MODEL_FEATURE_ORDER:
        if k not in normalized:
            raise ValueError(f"内部错误：缺少键「{k}」。")
    if not isinstance(normalized["Day"], int):
        raise ValueError("内部错误：Day 应为 int。")
    for k in MODEL_FEATURE_ORDER:
        if k == "Day":
            continue
        v = normalized[k]
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise ValueError(f"内部错误：「{k}」应为数字。")
        if not math.isfinite(float(v)):
            raise ValueError(f"内部错误：「{k}」不是有限数字。")
