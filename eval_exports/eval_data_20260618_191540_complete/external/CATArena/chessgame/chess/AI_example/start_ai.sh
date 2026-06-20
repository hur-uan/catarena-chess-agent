#!/bin/bash

# AI服务启动脚本

echo "启动国际象棋AI HTTP服务..."

# 检查Python是否安装
if ! command -v python &> /dev/null; then
    echo "错误: 未找到Python，请先安装Python 3.7+"
    exit 1
fi

# 检查依赖是否安装
if ! python -c "import flask, chess" &> /dev/null; then
    echo "安装依赖..."
    pip install flask python-chess requests
fi

# 默认参数
PORT=${1:-41001}
AI_ID=${2:-"ChessAI_Alpha"}
AI_NAME=${3:-"Alpha Chess AI"}

# 启动AI服务
echo "AI服务启动中..."
echo "端口: $PORT"
echo "AI ID: $AI_ID"
echo "AI名称: $AI_NAME"
echo "访问地址: http://localhost:$PORT"
echo "按 Ctrl+C 停止服务"
echo ""

python ai_http_server.py --port $PORT --ai_id $AI_ID --ai_name "$AI_NAME" 