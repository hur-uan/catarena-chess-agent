#!/bin/bash

# 国际象棋AI竞技场启动脚本

echo "Chess AI Arena Tournament"
echo "========================="

# 检查游戏服务器是否运行
echo "Checking game server..."
if curl -s http://localhost:40000/health > /dev/null; then
    echo "✓ Chess game server is running on port 40000"
else
    echo "✗ Chess game server is not running on port 40000"
    echo "Please start the chess server first:"
    echo "  cd ../chess && python server.py --port 40000"
    exit 1
fi

# 创建必要的目录
echo "Creating directories..."
mkdir -p configs logs reports

# 检查配置文件是否存在
if [ ! -f "configs/arena_config.json" ]; then
    echo "Creating sample configuration..."
    python start_arena.py --create-config
fi

# 列出配置的AI
echo ""
echo "Configured AIs:"
python start_arena.py --list-ais

# 测试AI连接
echo ""
echo "Testing AI connections..."
python start_arena.py --test-connection

# 询问是否继续
echo ""
read -p "Do you want to start the tournament? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting tournament..."
    python start_arena.py
else
    echo "Tournament cancelled."
fi 