# 桥牌 AI HTTP 服务器

这是一个基于 HTTP 协议的高级桥牌（Bridge）AI 实现，提供智能的叫牌和出牌策略。

## 项目简介

本项目实现了一个完整的桥牌 AI 系统，可以通过 HTTP API 与桥牌游戏服务器进行交互。AI 具备：

- **智能叫牌**：基于牌力评估的策略性叫牌系统
- **战术出牌**：考虑当前局势的出牌决策
- **牌力分析**：高牌点（HCP）计算和牌型分布评估
- **多游戏管理**：支持同时参与多个游戏

## 功能特性

### 叫牌系统

- **开叫策略**
  - 标准开叫要求（13+ 点）
  - 长套优先原则
  - 平均牌型开叫 1NT（12-14 HCP）
  
- **应叫策略**
  - 支持同伴花色（3 张以上 + 6+ 点）
  - 竞争性叫牌
  - 新花色叫牌（8+ 点）

### 出牌策略

- **首攻选择**
  - 优先打长套（非将牌）
  - 第四高或顶张首攻
  
- **跟牌策略**
  - 必须跟打出的花色
  - 同伴赢牌时垫小牌
  - 对手赢牌时尝试超牌
  - 将吃与垫牌决策

### 牌力评估

- **高牌点计算**：A=4, K=3, Q=2, J=1
- **牌型点数**：短门加分（缺门+3，单张+2，双张+1）
- **荣誉牌调整**：短门中的荣誉牌扣分

## 系统要求

- Python 3.6+
- 桥牌游戏服务器（默认运行在 `http://localhost:9030`）

### 依赖包

```bash
pip install flask requests
```

或者使用 requirements.txt：

```bash
pip install -r requirements.txt
```

## 快速开始

### 1. 启动 AI 服务器

使用启动脚本：

```bash
./start_ai.sh <端口号>
```

示例：

```bash
./start_ai.sh 50001
```

### 2. 直接使用 Python 启动

```bash
python3 ai_http_server.py --port 50001 --ai_id "my_ai" --ai_name "我的桥牌AI"
```

### 3. 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--port` | AI 服务器端口 | 50001 |
| `--ai_id` | AI 标识符 | advanced_bridge_AI |
| `--ai_name` | AI 显示名称 | Advanced Bridge AI |
| `--game_server` | 游戏服务器地址 | http://localhost:9030 |
| `--debug` | 调试模式 | False |

## API 文档

### 健康检查

**请求：**
```http
GET /health
```

**响应：**
```json
{
  "status": "healthy",
  "ai_id": "advanced_bridge_AI"
}
```

### 获取 AI 信息

**请求：**
```http
GET /info
```

**响应：**
```json
{
  "ai_id": "advanced_bridge_AI",
  "ai_name": "Advanced Bridge AI",
  "game_server_url": "http://localhost:9030",
  "active_games": 2
}
```

### 加入游戏

**请求：**
```http
POST /join_game
Content-Type: application/json

{
  "game_id": "game123",
  "player_id": 0
}
```

**响应：**
```json
{
  "status": "joined",
  "game_id": "game123",
  "player_id": 0
}
```

### 获取 AI 行动

**请求：**
```http
POST /get_action
Content-Type: application/json

{
  "game_id": "game123",
  "game_state": {
    "phase": "bidding",
    "players": [...],
    "bidding": {...}
  }
}
```

**响应（叫牌）：**
```json
{
  "call_type": "bid",
  "level": 1,
  "suit": "H"
}
```

**响应（出牌）：**
```json
{
  "type": "play",
  "card": "AS"
}
```

### 离开游戏

**请求：**
```http
POST /leave_game
Content-Type: application/json

{
  "game_id": "game123"
}
```

**响应：**
```json
{
  "status": "left",
  "game_id": "game123"
}
```

### 列出活跃游戏

**请求：**
```http
GET /games
```

**响应：**
```json
{
  "active_games": ["game123", "game456"],
  "game_count": 2
}
```

## 使用示例

### Python 客户端示例

```python
import requests

# AI 服务器地址
AI_SERVER = "http://localhost:50001"

# 1. 检查 AI 健康状态
response = requests.get(f"{AI_SERVER}/health")
print(response.json())

# 2. 加入游戏
join_data = {
    "game_id": "game123",
    "player_id": 0
}
response = requests.post(f"{AI_SERVER}/join_game", json=join_data)
print(response.json())

# 3. 获取 AI 行动
action_data = {
    "game_id": "game123",
    "game_state": {
        "phase": "bidding",
        "players": [...],
        "bidding": {...}
    }
}
response = requests.post(f"{AI_SERVER}/get_action", json=action_data)
print(response.json())

# 4. 离开游戏
leave_data = {"game_id": "game123"}
response = requests.post(f"{AI_SERVER}/leave_game", json=leave_data)
print(response.json())
```

### curl 示例

```bash
# 健康检查
curl http://localhost:50001/health

# 获取 AI 信息
curl http://localhost:50001/info

# 加入游戏
curl -X POST http://localhost:50001/join_game \
  -H "Content-Type: application/json" \
  -d '{"game_id":"game123","player_id":0}'

# 获取行动
curl -X POST http://localhost:50001/get_action \
  -H "Content-Type: application/json" \
  -d '{"game_id":"game123","game_state":{...}}'
```

## 配置说明

### 启动脚本配置

编辑 `start_ai.sh` 中的配置变量：

```bash
GAME_SERVER="http://localhost:9030"  # 游戏服务器地址
AI_ID="advanced_bridge_AI"           # AI 标识符
AI_NAME="Advanced Bridge AI"         # AI 显示名称
```

### AI 策略调整

可以在 `ai_http_server.py` 中修改以下参数：

```python
# 高牌点计算
self.hcp_values = {'A': 4, 'K': 3, 'Q': 2, 'J': 1}

# 开叫点力要求（第 147 行）
if total_points >= 13:  # 可调整为 12 或 14

# 1NT 开叫范围（第 217-218 行）
if 12 <= hand_analysis["hcp"] <= 14:  # 可调整为 15-17
```

## 故障排除

### 问题 1：无法连接到游戏服务器

**解决方案：**
- 确保桥牌游戏服务器正在运行
- 检查 `GAME_SERVER` 地址配置是否正确
- 验证网络连接和防火墙设置

### 问题 2：缺少 Python 依赖

**错误信息：**
```
ModuleNotFoundError: No module named 'flask'
```

**解决方案：**
```bash
pip install flask requests
```

### 问题 3：端口已被占用

**错误信息：**
```
Address already in use
```

**解决方案：**
- 使用不同的端口号
- 或者终止占用该端口的进程：
```bash
lsof -i :50001
kill -9 <PID>
```

## 架构说明

### 核心类

#### `AdvancedBridgeAI`

主要的 AI 实现类，包含以下核心方法：

- `calculate_hand_strength()` - 牌力评估
- `make_bid()` - 叫牌决策
- `play_card()` - 出牌决策
- `get_legal_actions()` - 获取合法行动
- `find_longest_suits()` - 找到最长花色

### 数据结构

**手牌格式：**
```python
[
  {"suit": "S", "rank": "A"},
  {"suit": "H", "rank": "K"},
  ...
]
```

**叫品格式：**
```python
{
  "call_type": "bid",  # 或 "pass", "double", "redouble"
  "level": 1,          # 1-7
  "suit": "H"          # "C", "D", "H", "S", "NT"
}
```

**出牌格式：**
```python
{
  "type": "play",
  "card": "AS"  # 牌面 + 花色
}
```

## 性能优化建议

1. **并发处理**：使用 gunicorn 或 uwsgi 部署生产环境
   ```bash
   gunicorn -w 4 -b 0.0.0.0:50001 ai_http_server:app
   ```

2. **缓存策略**：对重复的牌力计算结果进行缓存

3. **异步处理**：使用 asyncio 处理多个游戏请求

## 扩展开发

### 添加新的叫牌约定

在 `make_bid()` 方法中添加新的逻辑：

```python
def make_bid(self, game_state: dict, player_id: int):
    # 添加你的自定义叫牌逻辑
    if your_condition:
        return your_bid
    # ... 原有逻辑
```

### 改进出牌算法

在 `play_card()` 方法中实现更高级的策略：

```python
def play_card(self, game_state: dict, player_id: int):
    # 实现蒙特卡洛模拟、双明手求解等
    pass
```

## 许可证

本项目仅供学习和研究使用。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题或建议，请联系项目维护者。

---

**祝你游戏愉快！** 🃏♠️♥️♦️♣️


