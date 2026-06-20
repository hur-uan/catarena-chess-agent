#!/bin/bash

# =============================================================================
# AI对战者启动脚本
# =============================================================================
# 本脚本用于启动SOTA Agent开发的桥牌AI，用于对战
# 功能：
#   1. 扫描指定环境(bridge/bridge_magic)和轮次(round_1/round_2/...)下的所有AI
#   2. 为每个AI分配不同的端口号
#   3. 并行启动所有AI服务
#   4. 检查AI服务是否正常启动
#
# 注意：桥牌是4人游戏，通常需要至少4个AI实例（N/E/S/W位置）
# =============================================================================

# 脚本参数说明：
# $1: round - 轮次编号，默认为1 (对应round_1目录)
# $2: env - 环境类型，默认为bridge (bridge/bridge_magic/bridge_commercial等)
# $3: start_port - 起始端口号，默认为50001

# 获取命令行参数
round=$1
env=$2
start_port=$3

# 设置默认值：轮次默认为1
if [ -z "$round" ]; then
    round=1
fi

# 设置默认值：环境默认为bridge
if [ -z "$env" ]; then
    env="bridge"
fi

# 设置默认值：起始端口默认为50001
if [ -z "$start_port" ]; then
    start_port=50001
fi

# 显示配置信息
echo "Round: $round"
echo "Env: $env"
echo "Start Port: $start_port"

# 切换到脚本所在目录（项目根目录）
cd "$(dirname "$0")" || exit 1

# Use the script directory as the project root so paths are portable and not user-specific
base_dir=$(pwd)

echo "Starting AI competitors..."
echo "Project root: $base_dir"
echo "Current directory: $(pwd)"

# 扫描指定环境下的所有AI目录
# 路径格式：<project_root>/AI_competitors/{env}/round_{round}/*
# 例如：<project_root>/AI_competitors/bridge/round_1/demo1_AI
subdirs=$(ls -d "$base_dir/AI_competitors/$env/round_$round"/*/bridge_v1/ 2>/dev/null)

if [ -z "$subdirs" ]; then
    echo "Warning: No AI directories found in $base_dir/AI_competitors/$env/round_$round/"
    exit 1
fi

echo "Subdirs: $subdirs"

# =============================================================================
# 端口管理函数
# =============================================================================
# 功能：杀死占用指定端口的进程，确保端口可用
kill_port() {
    if [ -z "$1" ]; then
        echo "用法: kill_port <端口号>"
        return 1
    fi
    PORT=$1
    # 使用lsof命令查找占用端口的进程ID
    PID=$(sudo lsof -ti :"$PORT" 2>/dev/null)
    if [ -z "$PID" ]; then
        echo "端口 $PORT 未被任何进程占用。"
        return 0
    fi
    # 强制杀死占用端口的进程
    sudo kill -9 $PID
    echo "已杀死占用端口 $PORT 的进程: $PID"
}

# =============================================================================
# AI服务启动循环
# =============================================================================
# 初始化数组用于记录启动的AI信息
model_list=()   # 存储AI目录路径
port1_list=()   # 存储AI使用的第一个端口号
port2_list=()   # 存储AI使用的第二个端口号

# 遍历所有找到的AI目录
for subdir in $subdirs; do
    echo "entering $subdir"
    # 进入AI目录
    cd $subdir || exit 1
    
    # 为每个AI分配两个连续的端口
    port1=$start_port
    port2=$((start_port + 1))
    
    # 清理端口：杀死可能占用当前端口的进程
    kill_port $port1
    kill_port $port2
    
    echo "  启动第一个实例在端口 $port1"
    # 启动AI服务第一个实例：调用每个AI目录下的start_ai.sh脚本
    # 使用&符号在后台运行，实现并行启动
    bash start_ai.sh $port1 &
    
    # 等待第一个实例启动
    sleep 2
    
    echo "  启动第二个实例在端口 $port2"
    # 启动AI服务第二个实例
    bash start_ai.sh $port2 &
    
    # 记录AI信息到数组
    model_list+=($subdir)
    port1_list+=($port1)
    port2_list+=($port2)
    
    # 端口号递增，为下一个AI分配新的两个端口
    # 跳过两个端口号
    start_port=$((start_port + 2))
done

# =============================================================================
# 服务健康检查
# =============================================================================
# 等待8秒让所有AI服务完全启动
sleep 8

echo ""
echo "================================"
echo "检查AI服务健康状态"
echo "================================"

# 检查每个AI服务的健康状态（两个实例）
for i in ${!model_list[@]}; do
    model_name=$(basename ${model_list[$i]})
    echo "Model: $model_name"
    echo "  端口1: ${port1_list[$i]}"
    # 发送HTTP请求到AI的健康检查端点
    curl -s http://localhost:${port1_list[$i]}/health
    if [ $? -ne 0 ]; then
        echo "  Warning: 端口 ${port1_list[$i]} 可能未正常启动"
    fi
    
    echo "  端口2: ${port2_list[$i]}"
    curl -s http://localhost:${port2_list[$i]}/health
    if [ $? -ne 0 ]; then
        echo "  Warning: 端口 ${port2_list[$i]} 可能未正常启动"
    fi
    echo ""
done

echo "================================"
echo "AI服务启动完成"
echo "总共启动了 ${#model_list[@]} 个AI（每个AI 2个实例）"
echo "端口范围: ${port1_list[0]} - ${port2_list[-1]}"
echo "================================"

# =============================================================================
# 生成配置文件
# =============================================================================
echo ""
echo "生成配置文件..."

# 配置文件路径
config_dir="$base_dir/bridge_Arena/configs"
mkdir -p "$config_dir"
config_file="$config_dir/round_${round}_${env}_config.json"

# 生成配置文件内容
cat > "$config_file" << EOF
{
  "game_server": {
    "url": "http://localhost:9030",
    "timeout": 10
  },
  "logging": {
    "level": "INFO",
    "file": "logs/arena.log",
    "console": true
  },
  "tournament": {
    "rounds_per_match": 1,
    "boards_per_match": 12,
    "max_parallel_matches": 3,
    "delay_between_games": 0.001,
    "max_games_per_team": 1000
  },
  "ais": [
EOF

# 添加AI配置
ai_count=0
for i in ${!model_list[@]}; do
    # 提取AI名称（从路径中获取）
    ai_name=$(basename $(dirname ${model_list[$i]}))
    
    # 检查第一个端口是否正常启动
    if curl -s http://localhost:${port1_list[$i]}/health > /dev/null 2>&1; then
        if [ $ai_count -gt 0 ]; then
            echo "," >> "$config_file"
        fi
        
        cat >> "$config_file" << EOF
    {
      "ai_id": "$ai_name",
      "ai_name": "$ai_name AI",
      "port": ${port1_list[$i]},
      "description": "$ai_name based Bridge AI"
    }
EOF
        ai_count=$((ai_count + 1))
    fi
done

# 完成配置文件
cat >> "$config_file" << EOF

  ],
  "teams": []
}
EOF

echo "✓ 配置文件已生成: $config_file"
echo "  包含 $ai_count 个成功启动的AI"

# 同时生成一个demo配置文件
demo_config_file="$config_dir/demo_config.json"
cp "$config_file" "$demo_config_file"
echo "✓ Demo配置文件已生成: $demo_config_file"

echo ""
echo "================================"
echo "配置文件生成完成"
echo "主配置文件: $config_file"
echo "Demo配置文件: $demo_config_file"
echo "================================"

