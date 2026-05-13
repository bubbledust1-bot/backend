"""
输入约定：模型需要的特征名、顺序，以及平台侧可能使用的别名。

本模块只做“数据定义”，不做数值转换；转换在 feature_adapter 中完成。
"""

from typing import Dict, List, Tuple

# 模型 predict 时必须使用的特征名及顺序（与训练、feature_columns.json 一致）
MODEL_FEATURE_ORDER: List[str] = [
    "Day",
    "L/S Ratio",
    "Aggregate Ratio",
    "Active Ratio",
    "Activation Index",
    "Si-Al Ratio",
    "Ca Ratio",
]

# 平台传入的键名（大小写不敏感） -> 规范模型键名
# 后端/前端可使用左侧别名，最终会映射到右侧标准名。
PLATFORM_KEY_ALIASES: Dict[str, str] = {
    # Day
    "day": "Day",
    "curing_day": "Day",
    "curing_days": "Day",
    "养护天数": "Day",
    # L/S Ratio
    "ls_ratio": "L/S Ratio",
    "l_s_ratio": "L/S Ratio",
    "liquid_solid_ratio": "L/S Ratio",
    "液固比": "L/S Ratio",
    # Aggregate Ratio
    "aggregate_ratio": "Aggregate Ratio",
    "骨料比例": "Aggregate Ratio",
    # Active Ratio
    "active_ratio": "Active Ratio",
    "活性比例": "Active Ratio",
    # Activation Index
    "activation_index": "Activation Index",
    "活化指数": "Activation Index",
    # Si-Al Ratio
    "si_al_ratio": "Si-Al Ratio",
    "sial_ratio": "Si-Al Ratio",
    "硅铝比": "Si-Al Ratio",
    # Ca Ratio
    "ca_ratio": "Ca Ratio",
    "钙比例": "Ca Ratio",
}

# 标准模型键名集合（用于快速判断）
MODEL_KEY_SET = set(MODEL_FEATURE_ORDER)

# 参与“百分数自动转小数”的字段：若在 (1, 100] 区间内，视为 30 表示 30%
PERCENT_LIKE_KEYS = set(MODEL_FEATURE_ORDER) - {"Day"}


def canonical_key(raw_key: str) -> str:
    """
    将单个原始键名转为规范模型键名。
    - 已是标准名（大小写完全一致）则直接返回标准名。
    - 否则先转小写再查别名表；找不到则返回 stripped 后的原字符串（供上层报“未知字段”）。
    """
    if raw_key in MODEL_FEATURE_ORDER:
        return raw_key
    k = raw_key.strip()
    if k in MODEL_FEATURE_ORDER:
        return k
    lower = k.lower()
    return PLATFORM_KEY_ALIASES.get(lower, k)


def describe_fields() -> List[Tuple[str, str]]:
    """供文档与 explain 使用： (字段名, 中文说明)"""
    return [
        ("Day", "养护天数，整数，单位：天"),
        ("L/S Ratio", "液固比，小数（若填 1~100 且无小数含义，将按百分数÷100 处理）"),
        ("Aggregate Ratio", "骨料比例，小数"),
        ("Active Ratio", "活性比例，小数"),
        ("Activation Index", "活化指数，小数"),
        ("Si-Al Ratio", "硅铝比，小数"),
        ("Ca Ratio", "钙比例，小数"),
    ]
