#!/bin/bash

# Strong Baseline AI启动脚本
# 用法: ./start_ai.sh [port]

PORT=${1:-51012}

echo "启动Strong Baseline AI服务器..."
echo "端口: $PORT"

# 检查Python是否可用
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3"
    exit 1
fi

# 检查Flask是否安装
python3 -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "错误: 未安装Flask，请运行: pip install flask"
    exit 1
fi

# 启动AI服务器
echo "正在启动AI服务器在端口 $PORT..."
python3 holdem_ai.py --port $PORT
