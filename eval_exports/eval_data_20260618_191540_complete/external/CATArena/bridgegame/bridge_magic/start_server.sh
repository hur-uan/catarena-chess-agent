#!/bin/bash

# 桥牌服务器启动脚本

echo "启动桥牌HTTP服务器..."

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

# 启动服务器
echo "服务器启动中..."
echo "端口: 9031"
echo "访问地址: http://localhost:9031"
echo "按 Ctrl+C 停止服务器"
echo ""

python server.py --port ${1:-9031}