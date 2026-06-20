# 国际象棋AI竞技场

一个用于国际象棋AI对战和锦标赛的平台，支持多个AI进行循环赛，并生成详细的比赛报告。

## 功能特性

- **多AI对战**: 支持多个AI同时参与锦标赛
- **循环赛制**: 每个AI都会与其他AI进行对战
- **超时控制**: 防止AI卡死，10秒超时自动判负
- **详细统计**: 记录胜/平/负场次、思考时间等
- **多种报告格式**: JSON、TXT、CSV格式的报告
- **配置管理**: 灵活的配置文件管理
- **健康检查**: 自动检查AI服务状态

## 系统要求

- Python 3.7+
- 国际象棋游戏服务器 (端口40000)
- 多个AI服务器实例

## 安装依赖

```bash
pip install -r requirements.txt
```

## 快速开始

### 1. 启动游戏服务器

确保国际象棋游戏服务器在端口40000运行：

```bash
cd ../chess
python server.py --port 40000
```

### 2. 启动多个AI实例

```bash
chmod +x start_multiple_ais.sh
./start_multiple_ais.sh
```

这将启动6个AI实例：
- Simple AI 1 (端口40001)
- Minimax AI 1 (端口40002)
- Simple AI 2 (端口40003)
- Simple AI 3 (端口40004)
- Minimax AI 2 (端口40005)
- Random AI 1 (端口40006)

### 3. 运行锦标赛

```bash
chmod +x start_arena.sh
./start_arena.sh
```

或者直接运行：

```bash
python start_arena.py
```

## 配置管理

### 创建配置文件

```bash
python start_arena.py --create-config
```

### 查看配置的AI

```bash
python start_arena.py --list-ais
```

### 测试AI连接

```bash
python start_arena.py --test-connection
```

## 配置文件说明

配置文件位于 `configs/arena_config.json`：

```json
{
  "game_server": {
    "url": "http://localhost:40000",
    "timeout": 10,
    "max_moves": 200
  },
  "tournament": {
    "rounds_per_match": 2,
    "timeout_per_move": 10,
    "max_game_duration": 3600
  },
  "ais": [
    {
      "ai_id": "SimpleAI_1",
      "ai_name": "Simple Chess AI 1",
      "port": 40001,
      "algorithm": "simple",
      "enabled": true
    }
  ]
}
```

### 添加新的AI

编辑配置文件或使用Python API：

```python
from config import ChessArenaConfig

config = ChessArenaConfig()
config.add_ai("NewAI", "New Chess AI", 40007, "minimax")
```

## 报告格式

### 1. AI战绩统计

记录每个AI的胜/平/负场次和平均思考时间：

```
AI名称: 胜X 平Y 负Z (平均思考时间: T秒)
```

### 2. 胜负矩阵

显示每对AI之间的对战结果：

```
            AI1    AI2    AI3
AI1         --     1-0-1  0-1-1
AI2         1-0-1  --     1-1-0
AI3         0-1-1  1-1-0  --
```

### 3. 详细游戏记录

包含每局游戏的详细信息：
- 游戏ID
- 对战双方
- 胜者
- 结束原因
- 游戏时长
- 移动数

## 日志记录

竞技场会记录以下信息：

1. **参赛AI的名称**
2. **每个AI对战每个其他AI的胜/平/负场次** (胜负矩阵)
3. **每个AI相对其他所有AI的胜/平/负统计**
4. **每个AI每一步的平均思考时间**

日志文件保存在 `logs/arena.log`。

## 超时处理

- **移动超时**: 如果AI在10秒内没有响应，判定为超时
- **游戏超时**: 单局游戏最大时长3600秒
- **最大移动数**: 单局最大200步

## 文件结构

```
chess_Arena/
├── arena.py              # 主要竞技场逻辑
├── config.py             # 配置管理
├── start_arena.py        # 启动脚本
├── start_arena.sh        # Shell启动脚本
├── start_multiple_ais.sh # 多AI启动脚本
├── requirements.txt      # Python依赖
├── README.md            # 文档
├── configs/             # 配置文件目录
│   └── arena_config.json
├── logs/                # 日志目录
│   └── arena.log
└── reports/             # 报告目录
    ├── tournament_report.json
    ├── tournament_report.txt
    └── tournament_report.csv
```

## 使用示例

### 基本锦标赛

```bash
# 1. 启动游戏服务器
cd ../chess && python server.py --port 40000 &

# 2. 启动AI实例
./start_multiple_ais.sh

# 3. 运行锦标赛
python start_arena.py
```

### 自定义配置

```bash
# 使用自定义配置文件
python start_arena.py --config my_config.json

# 设置超时时间
python start_arena.py --timeout 15

# 设置最大移动数
python start_arena.py --max-moves 100
```

## 故障排除

### 常见问题

1. **AI连接失败**
   - 检查AI服务器是否正在运行
   - 验证端口配置是否正确
   - 使用 `--test-connection` 测试连接

2. **游戏服务器连接失败**
   - 确保游戏服务器在端口40000运行
   - 检查防火墙设置

3. **超时错误**
   - 增加超时时间：`--timeout 20`
   - 检查AI服务器性能

### 日志分析

查看详细日志：

```bash
tail -f logs/arena.log
```

## 扩展开发

### 添加新的AI算法

1. 在AI服务器中实现新算法
2. 更新配置文件中的algorithm字段
3. 重启AI服务器

### 自定义报告格式

修改 `arena.py` 中的报告生成方法：

```python
def save_custom_report(self, report: Dict, filename: str):
    # 自定义报告格式
    pass
```

## 许可证

本项目采用MIT许可证。 