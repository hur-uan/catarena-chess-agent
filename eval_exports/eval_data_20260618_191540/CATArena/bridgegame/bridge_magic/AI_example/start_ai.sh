#!/bin/bash

# 智能桥牌AI启动脚本
# 用法: ./start_ai.sh <端口>

set -e

# 检查端口参数
if [ $# -ne 1 ]; then
    echo "错误: 需要提供端口号参数"
    echo "用法: $0 <端口>"
    exit 1
fi

PORT=$1

# 验证端口是数字
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "错误: 端口必须是数字"
    exit 1
fi

# 检查端口是否被占用
if lsof -i:$PORT > /dev/null 2>&1; then
    echo "警告: 端口 $PORT 已被占用，尝试停止现有进程..."
    PID=$(lsof -t -i:$PORT)
    if [ ! -z "$PID" ]; then
        echo "停止进程 $PID（使用端口 $PORT）"
        kill $PID 2>/dev/null || true
        sleep 2
        
        # 如果仍在运行，强制停止
        if lsof -i:$PORT > /dev/null 2>&1; then
            echo "强制停止进程（使用端口 $PORT）"
            kill -9 $PID 2>/dev/null || true
            sleep 1
        fi
    fi
fi

# 脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查Python依赖
echo "检查Python依赖..."
python3 -c "import flask" 2>/dev/null || {
    echo "安装Flask..."
    pip3 install flask requests
}

# 启动AI服务
echo "启动智能桥牌AI（端口 $PORT）..."

# 后台运行
nohup python3 smart_bridge_ai.py --port $PORT &

# 等待服务启动
sleep 2

# 检查服务是否运行
if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
    echo "✓ 智能桥牌AI启动成功（端口 $PORT）"
    echo "健康检查: curl -s http://localhost:$PORT/health"
    echo "日志文件: smart_bridge_ai_$PORT.log"
else
    echo "❌ 启动智能桥牌AI失败（端口 $PORT）"
    echo "查看日志文件: smart_bridge_ai_$PORT.log"
    exit 1
fi

