#!/bin/bash

# 启动AI管理脚本
# 用法: ./start_ai.sh <AI文件夹路径> <tmux会话名称> [起始端口]

# 检查参数数量
if [ $# -lt 2 ]; then
    echo "用法: $0 <AI文件夹路径> <tmux会话名称> [起始端口]"
    echo "示例: $0 /path/to/ai/folder my_ai_session"
    echo "示例: $0 /path/to/ai/folder my_ai_session 52000"
    exit 1
fi

# 获取参数
AI_PATH="$1"
TMUX_NAME="$2"
START_PORT="${3:-51000}"
GAME_PORT="${4:-9010}"

# 获取当前脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 检查AI文件夹路径是否存在
if [ ! -d "$AI_PATH" ]; then
    echo "错误: AI文件夹路径不存在: $AI_PATH"
    exit 1
fi

# 检查start_ai.py是否存在
if [ ! -f "$SCRIPT_DIR/start_ai.py" ]; then
    echo "错误: start_ai.py 脚本不存在: $SCRIPT_DIR/start_ai.py"
    exit 1
fi

echo "=========================================="
echo "启动AI管理脚本"
echo "=========================================="
echo "AI文件夹路径: $AI_PATH"
echo "tmux会话名称: $TMUX_NAME"
echo "起始端口: $START_PORT"
echo "脚本目录: $SCRIPT_DIR"
echo "=========================================="

# 启动start_ai.py
python3 "$SCRIPT_DIR/start_ai.py" "$AI_PATH" "$TMUX_NAME" --start_port "$START_PORT" --game_port "$GAME_PORT"

# 检查启动结果
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "AI管理脚本启动完成"
    echo "=========================================="
    echo "使用以下命令连接到tmux会话:"
    echo "tmux attach-session -t $TMUX_NAME"
    echo ""
    echo "使用以下命令查看所有窗口:"
    echo "tmux list-windows -t $TMUX_NAME"
    echo ""
    echo "使用以下命令终止会话:"
    echo "tmux kill-session -t $TMUX_NAME"
else
    echo ""
    echo "=========================================="
    echo "AI管理脚本启动失败"
    echo "=========================================="
    exit 1
fi
