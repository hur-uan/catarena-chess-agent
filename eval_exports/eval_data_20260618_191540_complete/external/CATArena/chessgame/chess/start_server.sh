#!/bin/bash

# 国际象棋服务器启动脚本

echo "启动国际象棋HTTP服务器..."

# 检查Python是否安装
if ! command -v python &> /dev/null; then
    echo "错误: 未找到Python，请先安装Python 3.7+"
    exit 1
fi

# 检查依赖是否安装
if ! python -c "import flask" &> /dev/null; then
    echo "安装依赖..."
    pip install -r requirements.txt
fi

# 端口参数，默认为9020
PORT=${1:-9020}

# 启动服务器
echo "服务器启动中..."
echo "端口: $PORT"
echo "访问地址: http://localhost:$PORT"
echo "按 Ctrl+C 停止服务器"
echo ""

python server.py --port $PORT 