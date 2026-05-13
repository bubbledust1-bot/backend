from __future__ import annotations

from collections import Counter
from math import isnan
from typing import Any


def _is_number(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        if isinstance(v, float) and isnan(v):
            return False
        return True
    return False


def analyze_dataframe_rows(rows: list[dict[str, Any]], target_column: str | None = None) -> dict[str, Any]:
    if not rows:
        return {
            "dataset_name": "temporary",
            "sample_count": 0,
            "feature_count": 0,
            "target_column": target_column or "",
            "duplicate_rows": 0,
            "missing_rate": 0,
            "updated_at": "",
            "numeric_columns": [],
            "non_numeric_columns": [],
            "missing_by_column": {},
            "heatmap": {"columns": [], "matrix": []},
            "histograms": {},
            "top_related_to_target": [],
        }

    keys = list(rows[0].keys())
    if not target_column or target_column not in keys:
        target_column = keys[-1]

    sample_count = len(rows)

    duplicate_rows = sample_count - len({str(sorted(r.items())) for r in rows})

    missing_by_column: dict[str, float] = {}
    numeric_columns: list[str] = []
    non_numeric_columns: list[str] = []

    for col in keys:
        col_values = [r.get(col) for r in rows]
        missing = sum(v is None or v == "" for v in col_values)
        missing_by_column[col] = round(missing / sample_count, 6)

        valid = [v for v in col_values if v is not None and v != ""]
        if valid and all(_is_number(v) for v in valid):
            numeric_columns.append(col)
        else:
            non_numeric_columns.append(col)

    total_missing = sum(missing_by_column.values()) / max(1, len(missing_by_column))

    # Phase 1: 先提供可渲染骨架数据，热图先返回单位矩阵占位
    heat_cols = [c for c in numeric_columns if c != target_column] + ([target_column] if target_column in numeric_columns else [])
    matrix = []
    for i, _ in enumerate(heat_cols):
        row = []
        for j, _ in enumerate(heat_cols):
            row.append(1.0 if i == j else 0.0)
        matrix.append(row)

    histograms: dict[str, Any] = {}
    for col in numeric_columns:
        vals = [float(r[col]) for r in rows if _is_number(r.get(col))]
        if not vals:
            continue
        mn, mx = min(vals), max(vals)
        bins = 8
        step = (mx - mn) / bins if mx > mn else 1
        counts = [0] * bins
        for v in vals:
            idx = int((v - mn) / step) if step > 0 else 0
            if idx >= bins:
                idx = bins - 1
            counts[idx] += 1
        histograms[col] = {
            "min": mn,
            "max": mx,
            "bins": bins,
            "counts": counts,
        }

    # Phase 1: top related 用占位（真实相关系数在 Phase 2/3 细化）
    top_related = [
        {"column": c, "score": 0.0}
        for c in numeric_columns
        if c != target_column
    ][:5]

    return {
        "dataset_name": "temporary",
        "sample_count": sample_count,
        "feature_count": max(0, len(keys) - 1),
        "target_column": target_column,
        "duplicate_rows": duplicate_rows,
        "missing_rate": round(total_missing, 6),
        "updated_at": "",
        "numeric_columns": numeric_columns,
        "non_numeric_columns": non_numeric_columns,
        "missing_by_column": missing_by_column,
        "heatmap": {
            "columns": heat_cols,
            "matrix": matrix,
        },
        "histograms": histograms,
        "top_related_to_target": top_related,
    }
