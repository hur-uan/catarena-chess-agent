# 桥牌 AI 对战快速启动指南

## 🚀 5 分钟快速开始

### 前置条件
- ✅ Python 3.7+
- ✅ 已安装依赖：`pip install flask requests`

### 启动步骤

#### 1️⃣ 启动游戏服务器（终端1）
```bash
cd ../bridge
./start_server.sh
# 游戏服务器运行在 http://localhost:9030
```

#### 2️⃣ 启动 AI 队伍 A（终端2-3）
```bash
# 终端 2 - AI A1
cd ../bridge/AI_example
./start_ai.sh 50100

# 终端 3 - AI A2
cd ../bridge/AI_example
./start_ai.sh 50101
```

#### 3️⃣ 启动 AI 队伍 B（终端4-5）
```bash
# 终端 4 - AI B1
cd ../bridge/AI_example
./start_ai.sh 50102

# 终端 5 - AI B2
cd ../bridge/AI_example
./start_ai.sh 50103
```

#### 4️⃣ 验证服务（终端6）
```bash
# 验证所有服务都在运行
curl http://localhost:9030/health    # 游戏服务器
curl http://localhost:50100/health   # AI A1
curl http://localhost:50101/health   # AI A2
curl http://localhost:50102/health   # AI B1
curl http://localhost:50103/health   # AI B2
```

#### 5️⃣ 启动对战（终端6）
```bash
cd .

# Duplicate 模式（推荐新手）
python3 start_arena.py \
  --config config/round1.json \
  --tournament-type duplicate

# 或 Round Robin 模式
python3 start_arena.py \
  --config config/round1.json \
  --tournament-type round_robin
```

#### 6️⃣ 查看结果
```bash
cd .
ls -lt reports/  # 查看最新报告
cat reports/tournament_*.json | python3 -m json.tool
```

---

## 📝 配置文件示例

编辑 `config/round1.json`：

```json
{
  "game_server": {
    "url": "http://localhost:9030",
    "timeout": 10
  },
  "tournament": {
    "rounds_per_match": 1,
    "boards_per_match": 1,
    "max_parallel_matches": 3
  },
  "ais": [
    {
      "ai_id": "Team_A",
      "ai_name": "队伍 A",
      "port": 50100
    },
    {
      "ai_id": "Team_B",
      "ai_name": "队伍 B",
      "port": 50102
    }
  ]
}
```

**重要：** 每个 AI 的 `port` 是**起始端口**，系统会自动使用 port 和 port+1 两个端口。

---

## 🔧 常见问题

### Q: 为什么需要两个连续端口？
A: 桥牌是 2v2 游戏，每个队伍有 2 名玩家，所以需要 2 个独立的 AI 服务实例。

### Q: 端口被占用怎么办？
```bash
# 查看占用
lsof -i :50100

# 终止进程
kill -9 <PID>

# 或使用其他端口
./start_ai.sh 50200
```

### Q: 游戏服务器连接失败？
```bash
# 检查服务器状态
curl http://localhost:9030/health

# 重启服务器
cd ../bridge
./start_server.sh
```

### Q: AI 不响应？
1. 检查 AI 服务是否运行：`curl http://localhost:50100/health`
2. 查看日志：`tail -f logs/arena.log`
3. 增加超时时间：在配置文件中修改 `timeout: 30`

---

## 📊 对战模式

### Duplicate 模式（复式赛制）
- 每个 AI 队伍内部使用相同的 AI
- AA vs BB 格式
- 适合快速测试

```bash
python3 start_arena.py --config config/round1.json --tournament-type duplicate
```

### Round Robin 模式（循环赛）
- 所有队伍互相对战
- 需要在配置文件中定义 `teams`
- 适合综合评估

```bash
python3 start_arena.py --config config/round1.json --tournament-type round_robin
```

---

## 🎯 端口规划

| 服务 | 端口 | 说明 |
|------|------|------|
| 游戏服务器 | 9030 | 固定 |
| AI 队伍 A | 50100-50101 | 连续端口对 |
| AI 队伍 B | 50102-50103 | 连续端口对 |
| AI 队伍 C | 50104-50105 | 连续端口对 |
| AI 队伍 D | 50106-50107 | 连续端口对 |

**规则：** 配置文件中只需填写**偶数端口**（起始端口）

---

## 📖 完整文档

详细的对战流程、故障排除和高级配置，请查看：
- `../BATTLE_GUIDE.md` - 完整对战流程指南
- `../bridge/README.md` - 游戏服务器文档
- `../bridge/AI_example/README.md` - AI 开发文档
- `./README.md` - Arena 平台文档

---

**祝对战顺利！** 🃏♠️♥️♦️♣️

