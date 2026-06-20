#!/bin/bash

# 国际象棋AI服务启动脚本

# 默认参数
PORT=${1:-41101}
AI_ID=${2:-"ChessAI_$(date +%s)"}
AI_NAME=${3:-"Chess AI"}
GAME_SERVER=${4:-"http://localhost:9021"}

echo "=== 启动国际象棋AI服务 ==="
echo "端口: $PORT"
echo "AI ID: $AI_ID"
echo "AI名称: $AI_NAME"
echo "游戏服务器: $GAME_SERVER"
echo ""

# 检查Python环境
if ! command -v python &> /dev/null; then
    echo "错误: 未找到Python环境"
    exit 1
fi

# 检查依赖
echo "检查依赖..."
python -c "import flask, chess, requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "警告: 缺少依赖，尝试安装..."
    pip install flask python-chess requests
fi

# 启动AI服务
echo "启动AI服务..."
python ai_http_server.py \
    --port "$PORT" \
    --ai_id "$AI_ID" \
    --ai_name "$AI_NAME" \
    --game_server "$GAME_SERVER" \
    --debug
