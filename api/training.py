from __future__ import annotations

import json
import os
import pickle
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.deps import get_current_user
from models.user import User
from services.model_registry_service import (
    activate_model_for_project,
    delete_model_version,
    get_model_version_detail,
    list_model_versions,
    resolve_model_for_predict,
)
from services.training_analysis_service import analyze_dataframe_rows
from services.training_job_service import (
    create_training_job,
    get_training_job_detail,
    get_training_job_logs,
    get_training_job_metrics,
    get_training_job_progress,
)

router = APIRouter(prefix="/training", tags=["training"])


class AnalyzeDatasetRequest(BaseModel):
    project_id: str
    dataset_id: str
    target_column: str | None = None


class AnalyzeUploadResponse(BaseModel):
    upload_session_id: str
    analysis: dict[str, Any]


class CreateTrainingJobRequest(BaseModel):
    project_id: str
    dataset_id: str | None = None
    upload_session_id: str | None = None
    task_name: str = Field(min_length=1, max_length=128)
    target_column: str
    feature_columns: list[str]
    selected_algorithms: list[str]
    split_config: dict[str, float]
    cv_folds: Literal[3, 5, 10] = 5
    random_state: int = 42
    tuning_enabled: bool = True
    quality_mode_used: Literal["strict", "standard"] = "standard"
    training_rows: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/analyze/dataset")
def analyze_dataset(
    payload: AnalyzeDatasetRequest,
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    # Phase 1 骨架：先返回结构，Phase 2/3 接真实 DB+Data Hub
    sample_rows = [
        {"feature_1": 25.1, "feature_2": 60.2, "target_1": 35.2},
        {"feature_1": 27.4, "feature_2": 58.8, "target_1": 36.1},
        {"feature_1": 24.8, "feature_2": 62.9, "target_1": 34.4},
    ]
    return {
        "success": True,
        "project_id": payload.project_id,
        "dataset_id": payload.dataset_id,
        "analysis": analyze_dataframe_rows(sample_rows, payload.target_column),
    }


@router.post("/analyze/upload", response_model=AnalyzeUploadResponse)
async def analyze_upload(
    project_id: str = Body(...),
    target_column: str | None = Body(default=None),
    file: UploadFile = File(...),
    _current_user: User = Depends(get_current_user),
) -> AnalyzeUploadResponse:
    ext = (file.filename or "").lower().split(".")[-1]
    if ext not in {"csv", "xlsx"}:
        raise HTTPException(status_code=400, detail="Only csv/xlsx is supported")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (>10MB)")

    upload_session_id = f"up_{uuid4().hex}"
    # Phase 1 骨架：不落真实文件，返回模拟分析
    sample_rows = [
        {"col_a": 1.1, "col_b": 2.2, "target": 10.0},
        {"col_a": 1.3, "col_b": 2.5, "target": 10.4},
    ]
    return AnalyzeUploadResponse(
        upload_session_id=upload_session_id,
        analysis=analyze_dataframe_rows(sample_rows, target_column),
    )


@router.post("/jobs")
def create_job(
    payload: CreateTrainingJobRequest,
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return create_training_job(payload.model_dump())


@router.get("/jobs/{job_id}")
def job_detail(
    job_id: str,
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return get_training_job_detail(job_id)


@router.get("/jobs/{job_id}/progress")
def job_progress(
    job_id: str,
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return get_training_job_progress(job_id)


@router.get("/jobs/{job_id}/logs")
def job_logs(
    job_id: str,
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {"success": True, "items": get_training_job_logs(job_id)}


@router.get("/jobs/{job_id}/metrics")
def job_metrics(
    job_id: str,
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {"success": True, "items": get_training_job_metrics(job_id)}


@router.get("/models")
def models(
    project_id: str,
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {"success": True, "items": list_model_versions(project_id)}


@router.get("/models/{model_version_id}")
def model_detail(
    model_version_id: str,
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    row = get_model_version_detail(model_version_id)
    if not row:
        raise HTTPException(status_code=404, detail="model version not found")
    return {"success": True, "item": row}


@router.post("/models/{model_version_id}/activate-for-prediction")
def activate_model(
    model_version_id: str,
    project_id: str = Body(...),
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    activate_model_for_project(project_id, model_version_id)
    return {"success": True, "project_id": project_id, "active_model_version_id": model_version_id}


@router.delete("/models/{model_version_id}")
def remove_model(
    model_version_id: str,
    project_id: str,
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    ok = delete_model_version(project_id, model_version_id)
    if not ok:
        raise HTTPException(status_code=404, detail="model version not found")
    return {"success": True, "deleted_model_version_id": model_version_id}


class UserModelPredictRequest(BaseModel):
    project_id: str
    model_version_id: str | None = None
    inputs: dict[str, Any]


@router.post("/predict")
def predict_with_user_model(
    payload: UserModelPredictRequest,
    _current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    model = resolve_model_for_predict(payload.project_id, payload.model_version_id)
    if not model:
        return {
            "success": False,
            "error": "当前项目没有可用用户模型，请先在模型训练页完成训练并选择一个版本",
        }

    artifact_path = str(model.get("artifact_path") or "")
    if not artifact_path or not os.path.exists(artifact_path):
        return {
            "success": False,
            "error": "用户模型文件不存在，请重新训练该版本",
            "model_version_id": model.get("model_version_id"),
        }

    feature_json_path = artifact_path.replace(".pkl", ".feature_columns.json")
    if os.path.exists(feature_json_path):
        with open(feature_json_path, "r", encoding="utf-8") as f:
            feature_columns = json.load(f)
    else:
        feature_columns = model.get("feature_columns") or []

    if not feature_columns:
        return {
            "success": False,
            "error": "模型缺少特征列信息，无法预测",
            "model_version_id": model.get("model_version_id"),
        }

    with open(artifact_path, "rb") as f:
        estimator = pickle.load(f)

    row = []
    missing = []
    for c in feature_columns:
        if c not in payload.inputs:
            missing.append(c)
            row.append(0.0)
            continue
        try:
            row.append(float(payload.inputs[c]))
        except Exception:
            row.append(0.0)

    pred = float(estimator.predict([row])[0])

    return {
        "success": True,
        "prediction_mpa": round(pred, 6),
        "model_version_id": model["model_version_id"],
        "model_name": model.get("model_name", "user-model"),
        "task_name": model.get("task_name", ""),
        "used_feature_columns": feature_columns,
        "missing_input_columns": missing,
        "record_id": f"user_{uuid4().hex[:10]}",
    }
