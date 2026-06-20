#!/bin/bash

# AI对战平台启动脚本

echo "启动五子棋AI对战平台..."

# 检查Python是否安装
if ! command -v python &> /dev/null; then
    echo "错误: 未找到Python，请先安装Python 3.7+"
    exit 1
fi

# 检查依赖是否安装
if ! python -c "import requests" &> /dev/null; then
    echo "安装依赖..."
    pip install -r requirements.txt
fi

# 检查游戏服务器是否运行
echo "检查游戏服务器状态..."
if ! curl -s http://localhost:9000/health &> /dev/null; then
    echo "警告: 游戏服务器未运行，请先启动游戏服务器"
    echo "运行命令: cd ../gomoku && python server.py --port 9000"
    echo ""
fi

# 显示帮助信息
echo "使用方法:"
echo "  $0                    # 使用默认配置运行锦标赛"
echo "  $0 --create-config    # 创建示例配置文件"
echo "  $0 --list-ais         # 列出配置的AI"
echo "  $0 --add-ai ID NAME PORT  # 添加AI配置"
echo "  $0 --remove-ai ID     # 移除AI配置"
echo "  $0 --ais AI1 AI2      # 指定参赛AI"
echo "  $0 --timeout 15       # 设置超时时间"
echo ""

# 如果没有参数，运行默认锦标赛
if [ $# -eq 0 ]; then
    echo "运行默认锦标赛..."
    python start_arena.py
else
    echo "运行命令: python start_arena.py $@"
    python start_arena.py "$@"
fi 