# 五子棋AI对战平台

一个用于五子棋AI锦标赛的自动化对战平台，支持多AI循环赛、超时监控、详细统计和报告生成。

> 📖 **快速开始**: 查看 [对战流程指南](BATTLE_GUIDE.md) 获取详细的启动步骤

## 功能特性

- 🏆 **循环锦标赛**: 每个AI对战其他所有AI，确保公平竞争
- ⏱️ **超时监控**: 10秒超时机制，防止AI卡死
- 📊 **详细统计**: 胜/平/负矩阵、平均思考时间、对局记录
- 📝 **完整日志**: JSON和文本格式的详细报告
- ⚙️ **灵活配置**: 支持配置文件管理AI列表和参数
- 🔄 **自动对战**: 完全自动化的对战流程
- 🚀 **性能优化**: 减少90%的冗余HTTP调用，提高对战效率
- 📈 **可视化分析**: 支持生成比赛趋势图表

## 项目结构

```
gomoku_Arena/
├── arena.py                    # 核心对战平台
├── config.py                   # 配置管理（环境配置 + AI配置字典）
├── start_arena.py              # 启动脚本
├── start_arena.sh              # 便捷启动脚本
├── requirements.txt            # Python依赖
├── README.md                   # 项目文档
├── BATTLE_GUIDE.md            # 对战流程指南
├── configs/                    # 配置文件目录
│   └── multiround/            # 多轮比赛配置
│       └── round1.json        # 第一轮比赛配置
├── logs/                       # 日志文件目录
│   └── arena.log              # 运行日志
└── reports/                    # 报告文件目录
    ├── tournament_report_*.json  # JSON格式报告
    ├── tournament_report_*.txt   # 文本格式报告
    ├── tournament_report_*.csv   # CSV格式报告
    └── tournament_report_history_*.json  # 详细历史报告
```

## 快速开始

### 1. 安装依赖

```bash
# 安装Arena依赖（在仓库根或相对路径下运行）
cd ./gomoku_Arena
pip install -r requirements.txt

# 安装AI example依赖
cd ../gomoku/AI_example
pip install flask
```

### 2. 启动游戏服务器

```bash
# 启动五子棋游戏服务器（在仓库根运行或切换到 gomoku 目录）
cd ./gomoku
python server.py --port 9000
```

### 3. 启动AI服务

在多个终端中启动不同的AI服务：

```bash
# 终端1: 启动第一个AI（在仓库中切换到示例AI目录）
cd ./gomoku/AI_example
./start_ai.sh 11001 "AI_Alpha" "Alpha AI"

# 终端2: 启动第二个AI
cd ./gomoku/AI_example
./start_ai.sh 11002 "AI_Beta" "Beta AI"

# 终端3: 启动第三个AI（可选）
cd ./gomoku/AI_example
./start_ai.sh 11003 "AI_Gamma" "Gamma AI"
```

### 4. 配置AI对战

修改配置文件以匹配启动的AI服务：

```bash
# 编辑配置文件（在 gomoku_Arena 目录下）
cd ./gomoku_Arena
nano configs/multiround/round1.json
```

配置文件示例：
```json
{
  "game_server": {
    "url": "http://localhost:9000",
    "timeout": 10,
    "board_size": 15
  },
  "ais": [
    {
      "ai_id": "AI_Alpha",
      "ai_name": "Alpha AI",
      "port": 11001,
      "description": "Alpha AI"
    },
    {
      "ai_id": "AI_Beta",
      "ai_name": "Beta AI",
      "port": 11002,
      "description": "Beta AI"
    }
  ],
  "tournament": {
    "rounds_per_match": 2,
    "delay_between_games": 1,
    "max_games_per_ai": 10
  }
}
```

### 5. 运行锦标赛

```bash
# 使用配置文件运行
cd ./gomoku_Arena
python start_arena.py --config configs/multiround/round1.json

# 或者直接运行（使用默认配置）
python start_arena.py
```

## 配置管理

### 查看当前配置

```bash
# 查看配置文件内容
cat configs/multiround/round1.json

# 或使用启动脚本查看
python start_arena.py --list-ais
```

### 修改配置文件

直接编辑配置文件来添加或修改AI：

```bash
# 编辑配置文件
nano configs/multiround/round1.json
```

### 配置文件结构说明

```json
{
  "game_server": {
    "url": "http://localhost:9000",    // 游戏服务器地址
    "timeout": 10,                     // AI响应超时时间(秒)
    "board_size": 15                   // 棋盘大小
  },
  "ais": [                            // AI列表
    {
      "ai_id": "AI_Alpha",            // AI唯一标识
      "ai_name": "Alpha AI",          // AI显示名称
      "port": 11001,                  // AI服务端口
      "description": "Alpha AI"       // AI描述
    }
  ],
  "tournament": {
    "rounds_per_match": 2,            // 每对AI对战轮数
    "delay_between_games": 1,         // 对局间隔(秒)
    "max_games_per_ai": 10            // 每个AI最大对局数
  }
}
```


## 性能优化

### 优化前的问题

原始设计中，每局游戏中AI每次落子都要调用`join_game`接口，导致：
- **重复调用**: 每局游戏中，AI每次落子都要调用`join_game`
- **性能开销**: 增加了不必要的网络请求和延迟
- **逻辑冗余**: AI在整个游戏过程中只需要加入一次就够了

### 优化方案

1. **拆分接口调用**: 将`join_game`和`get_move`分离为两个独立的方法
2. **游戏流程优化**: 在游戏开始时让AI加入，游戏循环中只调用`get_move`

### 优化效果

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 每局游戏join_game调用 | 10-20次 | 2次 | 90%减少 |
| 6局游戏总调用 | 60-120次 | 12次 | 90%减少 |
| 平均思考时间 | 0.006秒 | 0.003秒 | 50%提升 |

## 详细报告增强

### 新增功能

1. **游戏历史记录 (Game History)**
   - 每一步的落子位置
   - 落子时间戳
   - 玩家信息（黑方/白方）

2. **游戏最终状态 (Final State)**
   - 当前玩家
   - 完整棋盘状态
   - 最后一步落子位置
   - 游戏结束状态
   - 特殊规则相关信息

### 数据格式

**游戏历史记录格式：**
```json
{
  "moves": [
    {"player": "black", "position": [7, 7], "timestamp": "2024-01-01T12:00:00"},
    {"player": "white", "position": [7, 8], "timestamp": "2024-01-01T12:01:00"},
    {"player": "black", "position": [8, 7], "timestamp": "2024-01-01T12:02:00"}
  ]
}
```

**游戏最终状态格式：**
```json
{
  "current_player": "white",
  "board": [[0,0,0,...], ...],
  "last_move": [9, 7],
  "game_status": "black_win",
  "black_triplets_count": 0,
  "white_triplets_count": 0
}
```

## 报告格式

### 1. AI统计表

| AI名称 | 胜 | 平 | 负 | 总场次 | 平均思考时间(秒) |
|--------|----|----|----|--------|------------------|
| Alpha AI | 3 | 1 | 2 | 6 | 0.245 |
| Beta AI | 2 | 1 | 3 | 6 | 0.312 |

### 2. 胜负矩阵

| AI名称 | Alpha AI | Beta AI | Gamma AI |
|--------|----------|---------|----------|
| Alpha AI | - | 2W/0D/0L | 1W/1D/0L |
| Beta AI | 0W/0D/2L | - | 2W/0D/0L |
| Gamma AI | 0W/1D/1L | 0W/0D/2L | - |

### 3. CSV格式报告

CSV报告采用简洁的胜负矩阵格式，便于数据分析：

```csv
AI vs AI,Alpha AI,Beta AI,Gamma AI,总胜/平/负,平均思考时间(秒)
Alpha AI,-,2/0/0,1/0/1,3/0/1,0.0048
Beta AI,0/0/2,-,2/0/0,2/0/2,0.0049
Gamma AI,1/0/1,0/0/2,-,1/0/3,0.0049
```

格式说明：
- `AI vs AI`: 行AI vs 列AI
- `-`: 自己vs自己（无意义）
- `胜/平/负`: 行AI对列AI的胜/平/负场次
- `总胜/平/负`: 行AI对所有其他AI的总胜/平/负场次
- `平均思考时间(秒)`: 行AI每步的平均思考时间，保留4位小数

### 4. 详细对局记录

```
1. arena_1234567890_AI_Alpha_vs_AI_Beta - AI_Alpha vs AI_Beta - 胜者: AI_Alpha - 时长: 45.23秒 - 结束原因: win
2. arena_1234567891_AI_Beta_vs_AI_Alpha - AI_Beta vs AI_Alpha - 胜者: AI_Alpha - 时长: 38.67秒 - 结束原因: win
```

## 可视化分析

### 生成趋势图表

```bash
python line_chart.py
```

该工具会生成以下图表：
- **总分趋势图**: 显示各AI在多轮比赛中的总分变化
- **胜率趋势图**: 显示各AI的胜率变化趋势
- **平均得分趋势图**: 显示各AI每局平均得分变化
- **综合趋势图**: 包含所有指标的2x2子图

### 图表特性

- 支持多轮比赛数据对比
- 自动颜色分配和标记
- 数值标签显示
- 高分辨率输出（300 DPI）
- 中文字体支持

## 日志记录

平台会记录以下信息：

1. **参赛AI的名称和ID**
2. **每个AI对战每个其他AI的胜/平/负场次**（胜负矩阵）
3. **每个AI相对其他所有AI的总胜/平/负统计**
4. **每个AI每一步的平均思考时间**
5. **详细的游戏历史和最终状态信息**

## 超时机制

- **默认超时**: 10秒
- **超时处理**: AI在指定时间内未响应，直接判负
- **实现方式**: 使用 `ThreadPoolExecutor` 和 `TimeoutError` 实现

## 错误处理

- **AI服务不可用**: 自动跳过不健康的AI
- **网络异常**: 记录错误并继续下一局
- **游戏服务器异常**: 记录错误并尝试重试

## 示例使用

### 基本对战流程

1. **启动游戏服务器**
```bash
cd ./gomoku
python server.py --port 9000
```

2. **启动AI服务**
```bash
# 终端1
cd ./gomoku/AI_example
./start_ai.sh 11001 "AI_Alpha" "Alpha AI"

# 终端2  
cd ./gomoku/AI_example
./start_ai.sh 11002 "AI_Beta" "Beta AI"
```

3. **运行对战**
```bash
cd ./gomoku_Arena
python start_arena.py --config configs/multiround/round1.json
```

### 多AI锦标赛

```bash
# 启动多个AI服务（每个终端一个）
# 终端1: AI_Alpha (端口11001)
# 终端2: AI_Beta (端口11002)  
# 终端3: AI_Gamma (端口11003)

# 修改配置文件添加所有AI
# 然后运行锦标赛
python start_arena.py --config configs/multiround/round1.json
```

### 指定特定AI对战

```bash
# 只让Alpha和Beta对战
python start_arena.py --config configs/multiround/round1.json --ais AI_Alpha AI_Beta
```

## 输出文件

- `logs/arena.log`: 详细运行日志
- `reports/tournament_report_*.json`: JSON格式的完整报告
- `reports/tournament_report_*.txt`: 易读的文本格式报告
- `reports/tournament_report_*.csv`: CSV格式报告（便于数据分析）
- `reports/tournament_report_history_*.json`: 包含游戏历史和状态的详细报告
- `visualization_output/*.png`: 各种趋势图表

## 技术栈

- Python 3.7+
- requests: HTTP客户端
- ThreadPoolExecutor: 超时控制
- JSON: 配置和报告格式
- pandas: 数据处理
- matplotlib: 图表生成

## 注意事项

1. 确保游戏服务器和AI服务都在运行
2. AI服务必须实现标准的HTTP API接口
3. 超时时间不宜设置过短，建议10-15秒
4. 大量对局时注意服务器负载
5. 报告文件大小会因详细数据而增加，建议定期清理

## 故障排除

### AI服务无法连接

**错误信息：** `AI Alpha AI 健康检查失败`

```bash
# 检查AI服务状态
curl http://localhost:11001/health

# 检查端口是否被占用 (不同平台命令可能不同)
# Linux: netstat -tlnp | grep 11001
# Windows (PowerShell): netstat -ano | Select-String 11001

# 重新启动AI服务（在仓库示例AI目录下）
cd ./gomoku/AI_example
./start_ai.sh 11001 "AI_Alpha" "Alpha AI"
```

### 游戏服务器无法连接

**错误信息：** `创建游戏失败`

```bash
# 检查游戏服务器状态
curl http://localhost:9000/health

# 确保游戏服务器正在运行（在仓库根或切换到 gomoku 目录）
cd ./gomoku
python server.py --port 9000
```

### 配置文件错误

**错误信息：** `加载配置文件失败`

```bash
# 验证JSON格式
python -m json.tool configs/multiround/round1.json

# 检查配置文件路径
ls -la configs/multiround/round1.json
```

### 端口冲突

```bash
# 查看端口占用情况
netstat -tlnp | grep -E "(9000|11001|11002|11003)"

# 杀死占用端口的进程
sudo kill -9 <PID>
```

## 版本历史

### v2.0 - 性能优化版本
- 减少90%的冗余HTTP调用
- 提高对战效率50%
- 优化代码结构，提高可维护性

### v1.1 - 详细报告增强版本
- 新增游戏历史记录功能
- 新增游戏最终状态信息
- 支持AI复盘分析
- 向后兼容现有报告格式

### v1.0 - 基础版本
- 循环锦标赛功能
- 超时监控机制
- 基础统计报告
- 配置文件管理

## 贡献指南

欢迎提交Issue和Pull Request来改进这个项目。在提交代码前，请确保：

1. 代码符合Python PEP 8规范
2. 添加适当的注释和文档
3. 测试新功能的正确性
4. 更新相关文档

## 许可证

本项目采用MIT许可证，详见LICENSE文件。
