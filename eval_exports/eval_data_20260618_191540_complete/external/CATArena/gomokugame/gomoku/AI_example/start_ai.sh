#!/bin/bash

# 快速五子棋AI启动脚本

echo "启动快速五子棋AI服务器..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python3"
    exit 1
fi

# 检查依赖
echo "检查依赖..."
python3 -c "import flask" 2>/dev/null || {
    echo "正在安装Flask依赖..."
    pip3 install flask
}

# 默认参数
PORT=${1:-11001}
AI_ID=${2:-"FastGomoku"}
AI_NAME=${3:-"Fast Gomoku AI"}

echo "========================================="
echo "快速AI服务器配置:"
echo "端口: $PORT"
echo "AI ID: $AI_ID"
echo "AI名称: $AI_NAME"
echo "优化特性:"
echo "  - 搜索深度: 2层"
echo "  - 最大思考时间: 8秒"
echo "  - 候选走法: 12个"
echo "  - 迭代加深搜索"
echo "========================================="

# 启动快速AI服务器
python3 ai_server.py \
    --port $PORT \
    --ai_id "$AI_ID" \
    --ai_name "$AI_NAME"

echo "快速AI服务器已关闭"
