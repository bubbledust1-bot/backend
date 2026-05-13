from __future__ import annotations

from datetime import datetime
from typing import Any

_MODEL_VERSIONS: list[dict[str, Any]] = []
_ACTIVE_MODEL_BY_PROJECT: dict[str, str] = {}


def _now() -> str:
    return datetime.utcnow().isoformat()


def register_model_version(payload: dict[str, Any]) -> dict[str, Any]:
    row = {
        "model_version_id": payload["model_version_id"],
        "project_id": payload["project_id"],
        "dataset_id": payload.get("dataset_id"),
        "task_name": payload.get("task_name") or payload.get("model_name") or payload["model_version_id"],
        "model_name": payload.get("model_name") or "UnknownModel",
        "target_column": payload.get("target_column") or "",
        "feature_columns": payload.get("feature_columns") or [],
        "metrics": payload.get("metrics") or {},
        "best_params": payload.get("best_params") or {},
        "created_at": payload.get("created_at") or _now(),
        "artifact_path": payload.get("artifact_path") or "",
        "is_saved": True,
        "is_active_for_prediction": False,
    }
    _MODEL_VERSIONS.append(row)
    return row


def list_model_versions(project_id: str) -> list[dict[str, Any]]:
    rows = [x.copy() for x in _MODEL_VERSIONS if x.get("project_id") == project_id]
    active_id = _ACTIVE_MODEL_BY_PROJECT.get(project_id)
    for x in rows:
        x["is_active_for_prediction"] = x.get("model_version_id") == active_id
    return sorted(rows, key=lambda x: x.get("created_at", ""), reverse=True)


def get_model_version_detail(model_version_id: str) -> dict[str, Any] | None:
    for x in _MODEL_VERSIONS:
        if x.get("model_version_id") == model_version_id:
            active_id = _ACTIVE_MODEL_BY_PROJECT.get(x.get("project_id", ""))
            out = x.copy()
            out["is_active_for_prediction"] = out.get("model_version_id") == active_id
            return out
    return None


def delete_model_version(project_id: str, model_version_id: str) -> bool:
    idx = next((i for i, m in enumerate(_MODEL_VERSIONS) if m.get("project_id") == project_id and m.get("model_version_id") == model_version_id), -1)
    if idx < 0:
        return False
    _MODEL_VERSIONS.pop(idx)
    if _ACTIVE_MODEL_BY_PROJECT.get(project_id) == model_version_id:
        _ACTIVE_MODEL_BY_PROJECT.pop(project_id, None)
    return True


def activate_model_for_project(project_id: str, model_version_id: str) -> None:
    _ACTIVE_MODEL_BY_PROJECT[project_id] = model_version_id


def get_active_model_for_project(project_id: str) -> dict[str, Any] | None:
    mid = _ACTIVE_MODEL_BY_PROJECT.get(project_id)
    if not mid:
        return None
    return get_model_version_detail(mid)


def resolve_model_for_predict(project_id: str, model_version_id: str | None = None) -> dict[str, Any] | None:
    if model_version_id:
        m = get_model_version_detail(model_version_id)
        if m and m.get("project_id") == project_id:
            return m
    return get_active_model_for_project(project_id)


if not _MODEL_VERSIONS:
    _MODEL_VERSIONS.append(
        {
            "model_version_id": "mv_demo_v1",
            "project_id": "demo-project",
            "dataset_id": "demo-dataset",
            "task_name": "演示模型",
            "model_name": "XGBoost",
            "target_column": "target_1",
            "feature_columns": ["feature_1", "feature_2"],
            "metrics": {"r2": 0.91, "mae": 1.23, "mse": 3.10, "rmse": 1.76},
            "best_params": {"max_depth": 6},
            "created_at": _now(),
            "artifact_path": "artifacts/models/mv_demo_v1.pkl",
            "is_saved": True,
            "is_active_for_prediction": False,
        }
    )
