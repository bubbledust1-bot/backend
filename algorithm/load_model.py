"""
加载并校验 ExtraTreesRegressor（或任意带 predict 的 sklearn 估计器）pkl。

假设说明：
- pkl 内仅为“模型本体”，不包含 StandardScaler 等预处理对象。
- 若您的文件实际为 Pipeline，只要最外层有 predict 且输入为 7 维特征，同样可用。
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Optional, Tuple

from . import config

# 进程内单例，避免重复反序列化大文件
_model_cache: Optional[Any] = None
_verified_feature_order: Optional[list] = None


def _validate_estimator(model: Any) -> None:
    """确认对象具备 predict；错误信息面向业务人员可读。"""
    if model is None:
        raise ValueError("模型文件内容为空：pickle 加载结果为 None。")
    if not hasattr(model, "predict"):
        raise TypeError(
            "加载的对象不是可用的预测模型：缺少 predict 方法。"
            "请确认 best_strength_model.pkl 是否为训练脚本保存的回归模型。"
        )


def load_model_from_path(model_path: Path) -> Any:
    """
    从指定路径加载 pkl。

    抛出：
        FileNotFoundError：文件不存在
        Exception：pickle 损坏或版本不兼容时，保留原始异常信息并附带说明
    """
    if not model_path.is_file():
        raise FileNotFoundError(
            f"找不到模型文件：{model_path}\n"
            f"请将 best_strength_model.pkl 放在 algorithm 目录下，或设置环境变量 DEEPSIGHT_MODEL_PATH。"
        )
    try:
        with open(model_path, "rb") as f:
            model = pickle.load(f)
    except Exception as e:
        raise RuntimeError(
            f"读取或反序列化模型失败（文件可能损坏或与当前 Python/sklearn 版本不兼容）：{model_path}\n"
            f"原始错误：{type(e).__name__}: {e}"
        ) from e
    _validate_estimator(model)
    return model


def get_model(force_reload: bool = False) -> Any:
    """
    返回已加载的模型实例（带缓存）。

    参数：
        force_reload：为 True 时丢弃缓存重新读盘（便于热替换模型文件调试）。
    """
    global _model_cache, _verified_feature_order
    if force_reload:
        _verified_feature_order = None
    if _model_cache is not None and not force_reload:
        return _model_cache
    _model_cache = load_model_from_path(config.MODEL_PATH)
    return _model_cache


def load_feature_order_from_json() -> list:
    """
    从 feature_columns.json 读取特征顺序，与 input_schema.MODEL_FEATURE_ORDER 交叉校验。
    若不一致以 input_schema 为准并视为配置错误（避免静默错位）。
    """
    import json

    path = config.FEATURE_COLUMNS_PATH
    if not path.is_file():
        raise FileNotFoundError(
            f"找不到特征列配置文件：{path}\n"
            "请从训练目录复制 feature_columns.json 到 algorithm 目录。"
        )
    with open(path, "r", encoding="utf-8") as f:
        cols = json.load(f)
    if not isinstance(cols, list) or not all(isinstance(c, str) for c in cols):
        raise ValueError("feature_columns.json 格式错误：应为字符串列表。")
    return cols


def get_model_and_feature_order(
    force_reload: bool = False,
) -> Tuple[Any, list]:
    """一次获取模型与 JSON 中的特征顺序（并校验与代码内顺序一致）。"""
    global _verified_feature_order
    from .input_schema import MODEL_FEATURE_ORDER

    model = get_model(force_reload=force_reload)
    if _verified_feature_order is not None and not force_reload:
        return model, _verified_feature_order

    json_order = load_feature_order_from_json()
    if json_order != MODEL_FEATURE_ORDER:
        raise ValueError(
            "feature_columns.json 中的列顺序与 input_schema.MODEL_FEATURE_ORDER 不一致，"
            "请保持训练产出与部署代码同步，否则预测会错位。\n"
            f"JSON: {json_order}\n代码: {MODEL_FEATURE_ORDER}"
        )
    _verified_feature_order = MODEL_FEATURE_ORDER
    return model, MODEL_FEATURE_ORDER
