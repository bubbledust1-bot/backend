"""
DeepSight SynCore — algorithm 包

后端接入示例：
    from algorithm.predictor import predict_strength
    result = predict_strength(payload_dict)
"""

from .predictor import predict, predict_strength

__all__ = ["predict_strength", "predict"]
