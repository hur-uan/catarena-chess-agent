#!/bin/bash

# 参数1: 传统/变种
MODE=$1
# 参数2: config路径
CONFIG_PATH=$2
# 参数3: log目录(可选)
LOG_DIR=$3

if [ -z "$MODE" ] || [ -z "$CONFIG_PATH" ]; then
    echo "用法: $0 traditional|variant <config路径> [log目录]"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$MODE" = "traditional" ]; then
    PY_FILE="$SCRIPT_DIR/arena/arena_traditional.py"
elif [ "$MODE" = "variant" ]; then
    PY_FILE="$SCRIPT_DIR/arena/arena_variant.py"
else
    echo "未知模式: $MODE, 只能是 traditional 或 variant"
    exit 1
fi

if [ ! -f "$PY_FILE" ]; then
    echo "找不到文件: $PY_FILE"
    exit 1
fi

if [ -n "$LOG_DIR" ]; then
    python3 "$PY_FILE" --config "$CONFIG_PATH" --log_dir "$LOG_DIR"
else
    python3 "$PY_FILE" --config "$CONFIG_PATH"
fi

