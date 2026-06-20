#!/bin/bash

# =============================================================================
# AI对战者启动脚本
# =============================================================================
# 本脚本用于启动SOTA Agent开发的棋牌类AI，用于对战
# 功能：
#   1. 扫描指定环境(gomoku/gomoku_variant)和轮次(round_1/round_2/...)下的所有AI
#   2. 为每个AI分配不同的端口号
#   3. 并行启动所有AI服务
#   4. 检查AI服务是否正常启动
# =============================================================================

# 脚本参数说明：
# $1: round - 轮次编号，默认为1 (对应round_1目录)
# $2: env - 环境类型，默认为gomoku (gomoku/gomoku_variant/gomoku_commercial等)
# $3: start_port - 起始端口号，默认为51000

# 获取命令行参数
round=$1
env=$2
start_port=$3

# 设置默认值：轮次默认为1
if [ -z "$round" ]; then
    round=1
fi

# 设置默认值：环境默认为gomoku
if [ -z "$env" ]; then
    env="gomoku"
fi

# 设置默认值：起始端口默认为51000
if [ -z "$start_port" ]; then
    start_port=51000
fi

# 显示配置信息
echo "Round: $round"
echo "Env: $env"
echo "Start Port: $start_port"

# 切换到脚本所在目录（项目根目录）
cd "$(dirname "$0")" || exit 1

echo "Starting AI competitors..."
echo "Current directory: $(pwd)"

# 计算仓库根目录（脚本所在目录）并使用相对路径查找AI目录
repo_root="$(pwd)"

# 扫描指定环境下的所有AI目录（例如: ./AI_competitors/gomoku/round_1/*/gomoku_v1/）
subdirs=$(ls -d "$repo_root/AI_competitors/$env/round_$round"/*/gomoku_v1/ 2>/dev/null)
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
model_list=()  # 存储AI目录路径
port_list=()   # 存储AI使用的端口号

# 遍历所有找到的AI目录
for subdir in $subdirs; do
    echo "entering $subdir"
    # 进入AI目录
    cd $subdir || exit 1
    
    # 清理端口：杀死可能占用当前端口的进程
    kill_port $start_port
    
    # 启动AI服务：调用每个AI目录下的start_ai.sh脚本
    # 使用&符号在后台运行，实现并行启动
    bash start_ai.sh $start_port &
    
    # 记录AI信息到数组
    model_list+=($subdir)
    port_list+=($start_port)
    
    # 端口号递增，为下一个AI分配新端口
    start_port=$((start_port + 1))
done

# =============================================================================
# 服务健康检查
# =============================================================================
# 等待8秒让所有AI服务完全启动
sleep 8

# 检查每个AI服务的健康状态
for i in ${!model_list[@]}; do
    echo "Model: ${model_list[$i]}, Port: ${port_list[$i]}"
    # 发送HTTP请求到AI的健康检查端点
    curl -s http://localhost:${port_list[$i]}/health
    if [ $? -ne 0 ]; then
        echo "Warning: ${model_list[$i]}, Port: ${port_list[$i]} maybe not running"
    fi
done

echo ""
echo "================================"
echo "AI服务启动完成"
echo "总共启动了 ${#model_list[@]} 个AI服务"
echo "端口范围: ${port_list[0]} - ${port_list[-1]}"
echo "================================"

# =============================================================================
# 生成配置文件
# =============================================================================
echo ""
echo "生成配置文件..."

# 配置文件路径（置于仓库的 gomoku_Arena/configs）
config_dir="$repo_root/gomoku_Arena/configs"
mkdir -p "$config_dir"
config_file="$config_dir/round_${round}_${env}_config.json"

# 生成配置文件内容
cat > "$config_file" << EOF
{
  "game_server": {
    "url": "http://localhost:9000",
    "timeout": 10,
    "board_size": 15
  },
  "ais": [
EOF

# 添加AI配置
ai_count=0
for i in ${!model_list[@]}; do
    # 提取AI名称（从路径中获取）
    ai_name=$(basename $(dirname $(dirname ${model_list[$i]})))
    
    # 检查端口是否正常启动
    if curl -s http://localhost:${port_list[$i]}/health > /dev/null 2>&1; then
        if [ $ai_count -gt 0 ]; then
            echo "," >> "$config_file"
        fi
        
        cat >> "$config_file" << EOF
    {
      "ai_id": "$ai_name",
      "ai_name": "$ai_name AI",
      "port": ${port_list[$i]},
      "description": "$ai_name based Gomoku AI"
    }
EOF
        ai_count=$((ai_count + 1))
    fi
done

# 完成配置文件
cat >> "$config_file" << EOF

  ],
  "tournament": {
    "rounds_per_match": 2,
    "delay_between_games": 1,
    "max_games_per_ai": 100
  }
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

