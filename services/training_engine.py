from __future__ import annotations

import json
import os
import pickle
from dataclasses import dataclass
from math import sqrt
from typing import Any
from uuid import uuid4

import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, train_test_split

try:
    from xgboost import XGBRegressor

    HAS_XGBOOST = True
except Exception:
    HAS_XGBOOST = False


SUPPORTED_ALGORITHMS = [
    "RandomForest",
    "XGBoost",
    "GradientBoosting",
    "ExtraTrees",
    "LinearRegression",
]


@dataclass
class TrainingArtifacts:
    model_pkl_path: str
    feature_json_path: str


@dataclass
class TrainingResult:
    candidates: list[dict[str, Any]]
    winner: dict[str, Any]
    artifacts: TrainingArtifacts
    diagnostics: dict[str, Any]


class TrainingEngineError(Exception):
    pass


def _validate_split(split_cfg: dict[str, float]) -> tuple[float, float, float]:
    train = float(split_cfg.get("train", 0.7))
    val = float(split_cfg.get("val", 0.15))
    test = float(split_cfg.get("test", 0.15))
    if train <= 0 or val <= 0 or test <= 0:
        raise TrainingEngineError("split_config 必须都大于 0")
    total = train + val + test
    if abs(total - 1.0) > 1e-6:
        raise TrainingEngineError("split_config 总和必须为 1.0")
    return train, val, test


def _build_model(model_name: str, random_state: int):
    if model_name == "RandomForest":
        return RandomForestRegressor(random_state=random_state, n_jobs=-1)
    if model_name == "XGBoost":
        if not HAS_XGBOOST:
            raise TrainingEngineError("当前环境未安装 xgboost，无法训练 XGBoost")
        return XGBRegressor(random_state=random_state, n_jobs=-1)
    if model_name == "GradientBoosting":
        return GradientBoostingRegressor(random_state=random_state)
    if model_name == "ExtraTrees":
        return ExtraTreesRegressor(random_state=random_state, n_jobs=-1)
    if model_name == "LinearRegression":
        return LinearRegression()
    raise TrainingEngineError(f"不支持的算法: {model_name}")


def _param_grid(model_name: str) -> dict[str, list[Any]]:
    if model_name == "RandomForest":
        return {
            "n_estimators": [100, 200, 300],
            "max_depth": [10, 20, None],
            "min_samples_split": [2, 5],
            "min_samples_leaf": [1, 2],
        }
    if model_name == "XGBoost":
        return {
            "n_estimators": [100, 200, 300],
            "max_depth": [3, 6, 9],
            "learning_rate": [0.01, 0.1, 0.2],
            "subsample": [0.8, 1.0],
            "colsample_bytree": [0.8, 1.0],
        }
    if model_name == "GradientBoosting":
        return {
            "n_estimators": [100, 200, 300],
            "max_depth": [3, 5],
            "learning_rate": [0.01, 0.1],
            "min_samples_split": [2, 5],
        }
    if model_name == "ExtraTrees":
        return {
            "n_estimators": [100, 200, 300],
            "max_depth": [10, 20, None],
            "min_samples_split": [2, 5],
            "min_samples_leaf": [1, 2],
        }
    if model_name == "LinearRegression":
        return {"fit_intercept": [True, False]}
    return {}


def _evaluate(model, x_train, y_train, x_val, y_val) -> dict[str, float]:
    model.fit(x_train, y_train)
    pred = model.predict(x_val)
    return {
        "r2": float(r2_score(y_val, pred)),
        "mae": float(mean_absolute_error(y_val, pred)),
    }


def _prepare_dataset(config: dict[str, Any]) -> tuple[pd.DataFrame, str, list[str], list[str]]:
    rows = config.get("training_rows") or []
    if not isinstance(rows, list) or not rows:
        raise TrainingEngineError("training_rows 为空，无法进行真实训练")

    df = pd.DataFrame(rows)
    if df.empty:
        raise TrainingEngineError("training_rows 解析后为空")

    target = str(config.get("target_column") or "")
    if not target or target not in df.columns:
        target = str(df.columns[-1])

    features = config.get("feature_columns") or []
    if not features:
        features = [c for c in df.columns if c != target]

    valid_features = [c for c in features if c in df.columns and c != target]
    if not valid_features:
        raise TrainingEngineError("feature_columns 无有效列")

    # 与根脚本尽量一致：统一转数值后按任一列缺失整行丢弃
    numeric_df = df[valid_features + [target]].apply(pd.to_numeric, errors="coerce").dropna(axis=0, how="any")

    if numeric_df.shape[0] < 5:
        raise TrainingEngineError(f"有效样本不足（{numeric_df.shape[0]}），至少需要 5 条可训练样本")

    return numeric_df, target, valid_features, list(df.columns)


def _save_artifacts(model, feature_columns: list[str], model_version_id: str) -> TrainingArtifacts:
    artifacts_dir = os.path.join(os.getcwd(), "backend", "artifacts", "models")
    os.makedirs(artifacts_dir, exist_ok=True)

    pkl_path = os.path.join(artifacts_dir, f"{model_version_id}.pkl")
    feat_path = os.path.join(artifacts_dir, f"{model_version_id}.feature_columns.json")

    with open(pkl_path, "wb") as f:
        pickle.dump(model, f)

    with open(feat_path, "w", encoding="utf-8") as f:
        json.dump(feature_columns, f, ensure_ascii=False, indent=2)

    return TrainingArtifacts(model_pkl_path=pkl_path, feature_json_path=feat_path)


def run_training(config: dict[str, Any]) -> TrainingResult:
    random_state = int(config.get("random_state", 42))
    train_ratio, val_ratio, test_ratio = _validate_split(config.get("split_config") or {})

    selected = [x for x in (config.get("selected_algorithms") or []) if x in SUPPORTED_ALGORITHMS]
    if not selected:
        raise TrainingEngineError("selected_algorithms 为空或无有效算法")

    if "XGBoost" in selected and not HAS_XGBOOST:
        selected = [x for x in selected if x != "XGBoost"]
        if not selected:
            raise TrainingEngineError("仅勾选了 XGBoost 且当前环境未安装 xgboost，无法继续训练")

    df, target_column, feature_columns, all_columns = _prepare_dataset(config)

    x = df[feature_columns]
    y = df[target_column]

    x_temp, x_test, y_temp, y_test = train_test_split(
        x,
        y,
        test_size=test_ratio,
        random_state=random_state,
    )
    val_ratio_of_temp = val_ratio / (train_ratio + val_ratio)
    x_train, x_val, y_train, y_val = train_test_split(
        x_temp,
        y_temp,
        test_size=val_ratio_of_temp,
        random_state=random_state,
    )

    # Phase1（单模型失败不拖死全局）
    candidates: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for name in selected:
        try:
            model = _build_model(name, random_state)
            m = _evaluate(model, x_train, y_train, x_val, y_val)
            candidates.append(
                {
                    "model_name": name,
                    "r2": round(m["r2"], 6),
                    "mae": round(m["mae"], 6),
                    "is_best": False,
                    "best_params": {},
                    "mse": None,
                    "rmse": None,
                    "cv_folds": int(config.get("cv_folds", 5)),
                }
            )
        except Exception as e:
            failures.append({"model_name": name, "error": str(e)})

    if not candidates:
        raise TrainingEngineError(f"基础模型筛选失败：全部候选模型训练失败，errors={failures}")

    candidates.sort(key=lambda z: z["r2"], reverse=True)
    best_r2 = candidates[0]["r2"]
    top = [c for c in candidates if c["r2"] >= best_r2 - 0.01]
    top.sort(key=lambda z: z["mae"])
    winner_name = top[0]["model_name"]

    # Phase2
    x_tune = pd.concat([x_train, x_val], axis=0)
    y_tune = pd.concat([y_train, y_val], axis=0)

    if bool(config.get("tuning_enabled", True)):
        base_model = _build_model(winner_name, random_state)
        gs = GridSearchCV(
            estimator=base_model,
            param_grid=_param_grid(winner_name),
            cv=int(config.get("cv_folds", 5)),
            scoring="r2",
            n_jobs=-1,
            verbose=0,
        )
        gs.fit(x_tune, y_tune)
        best_model = gs.best_estimator_
        best_params = gs.best_params_
    else:
        best_model = _build_model(winner_name, random_state)
        best_model.fit(x_tune, y_tune)
        best_params = {}

    # Final test
    test_pred = best_model.predict(x_test)
    final_r2 = float(r2_score(y_test, test_pred))
    final_mae = float(mean_absolute_error(y_test, test_pred))
    final_mse = float(mean_squared_error(y_test, test_pred))
    final_rmse = float(sqrt(final_mse))

    winner = {
        "model_name": winner_name,
        "is_best": True,
        "r2": round(final_r2, 6),
        "mae": round(final_mae, 6),
        "mse": round(final_mse, 6),
        "rmse": round(final_rmse, 6),
        "cv_folds": int(config.get("cv_folds", 5)),
        "best_params": best_params,
    }

    for c in candidates:
        c["is_best"] = c["model_name"] == winner_name
        if c["is_best"]:
            c["mse"] = winner["mse"]
            c["rmse"] = winner["rmse"]
            c["best_params"] = best_params

    model_version_id = str(config.get("_model_version_id") or f"mv_{uuid4().hex[:12]}")
    artifacts = _save_artifacts(best_model, feature_columns, model_version_id)

    diagnostics = {
        "rows_count": int(df.shape[0]),
        "all_columns": all_columns,
        "target_column": target_column,
        "feature_columns": feature_columns,
        "split_counts": {
            "train": int(x_train.shape[0]),
            "val": int(x_val.shape[0]),
            "test": int(x_test.shape[0]),
        },
        "selected_algorithms": selected,
        "phase1_failures": failures,
    }

    return TrainingResult(candidates=candidates, winner=winner, artifacts=artifacts, diagnostics=diagnostics)
