#!/bin/bash

# 智能五子棋AI启动脚本

echo "启动智能五子棋AI服务..."

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python 3.7+"
    exit 1
fi

# 检查依赖
echo "检查依赖..."
python3 -c "import flask; import requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "安装依赖..."
    pip3 install flask requests
fi

# 默认参数
PORT=${1:-21000}
AI_ID=${AI_ID:-"SmartAI_Alpha"}
AI_NAME=${AI_NAME:-"智能AI Alpha"}

echo ""
echo "================================================"
echo "  智能五子棋AI服务"
echo "================================================"
echo "端口: $PORT"
echo "AI ID: $AI_ID"
echo "AI名称: $AI_NAME"
echo "访问地址: http://localhost:$PORT"
echo "================================================"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 启动AI服务
python3 ai_http_server.py \
    --port $PORT \
    --ai_id "$AI_ID" \
    --ai_name "$AI_NAME"

