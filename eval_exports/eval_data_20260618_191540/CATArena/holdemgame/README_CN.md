# CATArena_Holdem
## 🚀 快速开始
### 环境安装
- Python 3.8+
- 依赖包见 requirements.txt
```bash
pip install -r requirements.txt
```

### 生成AI代码
通过`ChatPrompt.py`获取prompt，发送给您的code agent，在对应目录下进行开发

完整参数说明：
```bash
python ChatPrompt.py \
  --mode traditional \                    # 游戏模式: traditional 或 variant
  --model_name demo1 \        # 模型名称
  --game_port 9010 \                      # 游戏服务器端口
  --round_num 1 \                         # 比赛轮次
  --code_path /path/to/ai/code \          # AI代码存放路径
  --log_path /path/to/logs \              # 上一轮日志文件路径(轮次>1时必需)
  --last_round_dir /path/to/last/round    # 上一轮代码路径(轮次>1时必需)
```
> **提示：** 将要同时进行对战的AI代码放在一个文件夹下，分成多个子文件夹

### 全流程样例
运行下面命令，可以启动服务器、AI服务，并自动地进行对战（经典版本）：
```bash
cd catarena_holdem/
bash start_demo_competition.sh <AI所在的路径>
```
例如：
```bash
bash start_demo_competition.sh ./AI_examples/traditional/round1/ADK/
```

### 启动德扑服务器
1. 启动经典版本服务器
```bash
bash start_server.sh traditional
```
2. 启动变种版本服务器
```bash
bash start_server.sh variant
```

> **提示：** 记录服务器的端口信息，一般来说普通版9010，变种版本9020

### 启动AI服务
在`AI_examples/`文件夹下，提供了多个AI的样本接口。

运行以下命令，自动在`my_ai_session`窗口启动`/path/to/ai/folder`下所有AI玩家
```bash
bash start_ai.sh /path/to/ai/folder my_ai_session
```
执行完成后，会自动在`/path/to/ai/folder`下生成config.json。
> **提示：** 手动检查config.json服务器的端口信息和前面启动的是否一致（9010/9020）

## 运行Arena比赛
启动服务器和AI服务后，可以进行Tournament比赛。Tournament只需要一个合法的`config.json`文件即可运行。
启动脚本（模式有traditional和variant）：
```bash
bash run_arena.sh <模式> <config所在路径> <log的目标输出路径（可选）>
```
如果没有设置目标log输出路径，report和log会在/path/to/config/的父目录下的log文件夹。
`history_tourney_*.json`是每一轮锦标赛的详细log，`tournament_report_tourney_*.json`是100轮锦标赛的统计信息。



## 项目结构

```
catarena_holdem/
├── README.md                    # 项目说明文档
├── requirements.txt             # Python依赖包列表
├── start_server.sh             # 启动德扑服务器脚本
├── start_ai.py                 # AI服务管理脚本
├── start_ai.sh                 # AI服务启动脚本
├── run_arena.sh                # Arena比赛运行脚本
├── ChatPrompt.py                # Code Agent Prompt生成
│
├── traditional_server/          # 经典版本德扑服务器
│   ├── server.py               # 经典版本游戏服务器
│   ├── README.md               # 服务器说明文档
│   └── TOURNAMENT_MODE_README.md # 锦标赛模式说明
│
├── variant_server/              # 变种版本德扑服务器
│   ├── server.py               # 变种版本游戏服务器
│   ├── requirements.txt        # 服务器依赖
│   ├── README.md               # 服务器说明文档
│   └── TOURNAMENT_MODE_README.md # 锦标赛模式说明
│
├── arena/                       # Arena比赛系统
│   ├── arena_traditional.py    # 经典版本比赛逻辑
│   ├── arena_variant.py        # 变种版本比赛逻辑
│   ├── config.py               # 比赛配置
│   ├── csv_reporter.py         # 报告生成器
│   └── blind_structure.json    # 盲注结构配置
│
├── AI_examples/                 # AI示例代码
│   ├── traditional/            # 经典版本AI示例
│   └── variant/                # 变种版本AI示例
│
├── config/                      # 配置文件目录
├── logs/                        # 日志文件目录
└── __pycache__/                 # Python缓存文件
```

### 核心组件说明

#### 🎮 游戏服务器
- **traditional_server/**: 经典德州扑克服务器，支持标准52张牌
- **variant_server/**: 变种德州扑克服务器，支持32张牌（6-A）

#### 🤖 AI系统
- **AI_examples/**: 提供多种AI实现示例
  - `simple/`: 基础随机策略AI
  - `strong_baseline/`: 基于手牌强度和位置的高级AI
  - `round_i/`: 基线code agent的实现代码
- **start_ai.py**: 智能AI服务管理器，支持批量启动和故障恢复

#### 🏆 Arena比赛系统
- **arena_traditional.py**: 经典版本锦标赛逻辑
- **arena_variant.py**: 变种版本锦标赛逻辑
- **csv_reporter.py**: 生成详细的比赛报告和统计

#### 📊 配置和日志
- **config.json**: AI和比赛配置文件
- **blind_structure.json**: 盲注结构定义
- **log/**: 存储比赛历史和统计报告
