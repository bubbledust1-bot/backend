"""
algorithm 包路径与可配置项。

说明：
- 默认所有资源文件与本包同级目录（algorithm/）。
- 将来部署到云服务器或 Docker 时，通常只需改环境变量或本文件中的路径，
  无需改动预测逻辑代码。
"""

from pathlib import Path

# 本包根目录（包含 load_model.py、predictor.py 的目录）
PACKAGE_DIR = Path(__file__).resolve().parent

# 模型与元数据文件（可与训练产出保持一致文件名）
MODEL_PATH = PACKAGE_DIR / "best_strength_model.pkl"
FEATURE_COLUMNS_PATH = PACKAGE_DIR / "feature_columns.json"
TRAINING_RANGES_PATH = PACKAGE_DIR / "training_ranges.json"

# 便于前端/日志展示；换模型时手动更新此字符串即可
MODEL_VERSION = "extra_trees_cement_strength_v1"

# 可选：通过环境变量覆盖模型路径（云部署时常用）
import os

_env_model = os.environ.get("DEEPSIGHT_MODEL_PATH")
if _env_model:
    MODEL_PATH = Path(_env_model)
