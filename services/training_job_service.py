from __future__ import annotations

from datetime import datetime
from threading import Thread
from time import sleep
from typing import Any
from uuid import uuid4

from services.model_registry_service import register_model_version
from services.training_engine import run_training

_JOBS: dict[str, dict[str, Any]] = {}
_JOB_LOGS: dict[str, list[dict[str, Any]]] = {}
_JOB_METRICS: dict[str, list[dict[str, Any]]] = {}

_STAGES = [
    "数据检查",
    "数据分析",
    "数据划分",
    "基础模型筛选",
    "超参数微调",
    "交叉验证",
    "测试集评估",
    "模型保存",
    "版本登记",
]


def _now() -> str:
    return datetime.utcnow().isoformat()


def _append_log(job_id: str, stage: str, message: str, level: str = "info") -> None:
    _JOB_LOGS.setdefault(job_id, []).append(
        {
            "at": _now(),
            "stage": stage,
            "level": level,
            "message": message,
        }
    )


def _simulate_training(job_id: str) -> None:
    job = _JOBS[job_id]
    cfg = job["config"]
    job["status"] = "running"
    job["started_at"] = _now()

    try:
        job["current_stage"] = "数据检查"
        job["progress_pct"] = 5
        rows = cfg.get("training_rows") or []
        rows_count = len(rows) if isinstance(rows, list) else 0
        all_columns = list(rows[0].keys()) if rows_count and isinstance(rows[0], dict) else []
        _append_log(job_id, "数据检查", f"任务名称: {job.get('task_name', '')}")
        _append_log(job_id, "数据检查", f"数据源: {cfg.get('dataset_id') or cfg.get('upload_session_id') or 'unknown'}")
        _append_log(job_id, "数据检查", f"rows_count: {rows_count}")
        _append_log(job_id, "数据检查", f"all_columns: {all_columns}")
        _append_log(job_id, "数据检查", f"样本数: {cfg.get('sample_count', 0)}")
        _append_log(job_id, "数据检查", f"目标列: {cfg.get('target_column', '')}")
        _append_log(job_id, "数据检查", f"特征列: {cfg.get('feature_columns', [])}")
        _append_log(job_id, "数据检查", f"算法勾选: {cfg.get('selected_algorithms', [])}")
        _append_log(job_id, "数据检查", f"切分配置: {cfg.get('split_config', {})}")
        _append_log(job_id, "数据检查", f"K-fold: {cfg.get('cv_folds', 5)}")
        _append_log(job_id, "数据检查", f"随机种子: {cfg.get('random_state', 42)}")
        _append_log(job_id, "数据检查", f"是否调参: {cfg.get('tuning_enabled', True)}")
        sleep(0.2)

        job["current_stage"] = "数据分析"
        job["progress_pct"] = 15
        _append_log(job_id, "数据分析", "完成基础数据统计")
        sleep(0.2)

        job["current_stage"] = "数据划分"
        job["progress_pct"] = 25
        _append_log(job_id, "数据划分", "按 split_config 执行 train/val/test 划分")
        sleep(0.2)

        job["current_stage"] = "基础模型筛选"
        job["progress_pct"] = 45
        if rows_count == 0:
            raise ValueError("训练数据未进入后端：training_rows 为空")

        cfg["_model_version_id"] = f"mv_{uuid4().hex[:12]}"
        result = run_training(cfg)
        diag = result.diagnostics or {}
        _append_log(job_id, "基础模型筛选", f"phase1 实际参与模型: {[x['model_name'] for x in result.candidates]}")
        _append_log(job_id, "基础模型筛选", f"数据行数(清洗后): {diag.get('rows_count')}")
        _append_log(job_id, "基础模型筛选", f"数据列: {diag.get('all_columns')}")
        _append_log(job_id, "基础模型筛选", f"切分行数: {diag.get('split_counts')}")
        fails = diag.get('phase1_failures') or []
        if fails:
            _append_log(job_id, "基础模型筛选", f"phase1 失败模型: {fails}")
        for m in result.candidates:
            _append_log(job_id, "基础模型筛选", f"{m['model_name']} -> R2={m['r2']} MAE={m['mae']} RMSE={m['rmse']}")
        sleep(0.2)

        job["current_stage"] = "超参数微调"
        job["progress_pct"] = 60
        if cfg.get("tuning_enabled", True):
            _append_log(job_id, "超参数微调", "已执行 phase2 调参")
        else:
            _append_log(job_id, "超参数微调", "跳过 phase2（tuning_enabled=false）")
        sleep(0.2)

        job["current_stage"] = "交叉验证"
        job["progress_pct"] = 72
        _append_log(job_id, "交叉验证", f"交叉验证折数: {cfg.get('cv_folds', 5)}")
        sleep(0.2)

        job["current_stage"] = "测试集评估"
        job["progress_pct"] = 82
        winner = result.winner
        _append_log(job_id, "测试集评估", f"winner_name: {winner['model_name']}")
        _append_log(job_id, "测试集评估", f"best_params: {winner['best_params']}")
        _append_log(job_id, "测试集评估", f"metrics: R2={winner['r2']} MAE={winner['mae']} MSE={winner['mse']} RMSE={winner['rmse']}")
        sleep(0.2)

        job["current_stage"] = "模型保存"
        job["progress_pct"] = 90
        model_version_id = cfg["_model_version_id"]
        _append_log(job_id, "模型保存", f"artifact: {result.artifacts.model_pkl_path}")
        _append_log(job_id, "模型保存", f"feature_columns: {result.artifacts.feature_json_path}")

        job["current_stage"] = "版本登记"
        job["progress_pct"] = 96

        metrics_rows = []
        for c in result.candidates:
            row = c.copy()
            row["is_best"] = c["model_name"] == winner["model_name"]
            metrics_rows.append(row)
        _JOB_METRICS[job_id] = metrics_rows

        register_model_version(
            {
                "model_version_id": model_version_id,
                "project_id": job["project_id"],
                "dataset_id": job.get("dataset_id"),
                "task_name": job.get("task_name"),
                "model_name": winner["model_name"],
                "target_column": cfg.get("target_column", ""),
                "feature_columns": cfg.get("feature_columns", []),
                "metrics": {
                    "r2": winner["r2"],
                    "mae": winner["mae"],
                    "mse": winner["mse"],
                    "rmse": winner["rmse"],
                },
                "best_params": winner["best_params"],
                "artifact_path": result.artifacts.model_pkl_path,
                "created_at": _now(),
            }
        )

        job["model_version_id"] = model_version_id
        job["progress_pct"] = 100
        job["status"] = "success"
        job["finished_at"] = _now()
        _append_log(job_id, "版本登记", f"模型版本已登记: {model_version_id}")

    except Exception as e:
        job["status"] = "failed"
        job["error_message"] = str(e)
        job["finished_at"] = _now()
        _append_log(job_id, "失败", f"训练失败: {e}", level="error")



def create_training_job(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("training_rows") or []
    if not isinstance(rows, list):
        rows = []
    payload["training_rows"] = rows

    job_id = f"job_{uuid4().hex[:12]}"
    row = {
        "job_id": job_id,
        "project_id": payload["project_id"],
        "dataset_id": payload.get("dataset_id"),
        "upload_session_id": payload.get("upload_session_id"),
        "task_name": payload["task_name"],
        "status": "pending",
        "progress_pct": 0,
        "current_stage": "未开始",
        "model_version_id": None,
        "error_message": None,
        "config": payload,
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
    }
    _JOBS[job_id] = row
    _JOB_LOGS[job_id] = []
    _JOB_METRICS[job_id] = []

    _append_log(job_id, "初始化", f"已创建训练任务: {payload['task_name']}")

    t = Thread(target=_simulate_training, args=(job_id,), daemon=True)
    t.start()

    return {"success": True, "job_id": job_id, "status": "pending"}



def get_training_job_detail(job_id: str) -> dict[str, Any]:
    row = _JOBS.get(job_id)
    if not row:
        return {"success": False, "error": "job not found"}
    return {"success": True, "item": row}



def get_training_job_progress(job_id: str) -> dict[str, Any]:
    row = _JOBS.get(job_id)
    if not row:
        return {"success": False, "error": "job not found"}

    done = set()
    current = row["current_stage"]
    for s in _STAGES:
        if s == current and row["status"] == "running":
            break
        if row["status"] == "success":
            done.add(s)
        elif current != "未开始" and _STAGES.index(s) < _STAGES.index(current):
            done.add(s)

    items = []
    for s in _STAGES:
        if row["status"] == "failed" and s == current:
            st = "failed"
        elif s in done:
            st = "done"
        elif s == current and row["status"] == "running":
            st = "running"
        else:
            st = "todo"
        items.append({"stage": s, "status": st})

    return {
        "success": True,
        "status": row["status"],
        "progress_pct": row["progress_pct"],
        "current_stage": row["current_stage"],
        "stages": items,
    }



def get_training_job_logs(job_id: str) -> list[dict[str, Any]]:
    return _JOB_LOGS.get(job_id, [])



def get_training_job_metrics(job_id: str) -> list[dict[str, Any]]:
    return _JOB_METRICS.get(job_id, [])
