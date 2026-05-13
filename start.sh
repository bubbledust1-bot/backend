#!/bin/bash
set -e

echo "Starting DeepSight SynCore backend..."

# Railway 会自动设置 PORT 环境变量
# 如果未设置，使用默认值 8000
export PORT=${PORT:-8000}

echo "Using port: $PORT"
uvicorn main:app --host 0.0.0.0 --port $PORT
