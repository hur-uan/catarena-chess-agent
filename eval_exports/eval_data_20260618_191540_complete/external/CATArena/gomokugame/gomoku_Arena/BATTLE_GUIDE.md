# 五子棋AI对战流程指南

这是一个简单的步骤指南，帮助您快速启动五子棋AI对战。

## 📋 准备工作

### 1. 环境检查
确保您有以下环境：
- Python 3.7+
- 网络连接正常
- 足够的终端窗口（建议4-5个）

### 2. 目录结构
```
```bash
cd ./gomoku
python server.py --port 9000
```
│       ├── ai_server.py      # AI服务器
```bash
cd ./gomoku
python server.py --port 9001
```
  └── configs/              # 配置文件
    └── multiround/
      └── round1.json   # 比赛配置
```

## 🚀 启动步骤

### 步骤1: 启动游戏服务器
```bash
cd ./gomoku/AI_example
./start_ai.sh 11002 "AI_Beta" "Beta AI"
```
cd ./gomoku
```bash
cd ./gomoku/AI_example
./start_ai.sh 11003 "AI_Gamma" "Gamma AI"
```
```
五子棋游戏服务器启动成功
服务器地址: http://localhost:9000
等待连接...
```bash
cd ./gomoku_Arena
nano configs/multiround/round1.json
```
python server.py --port 9001
```
五子棋游戏服务器启动成功
服务器地址: http://localhost:9001
等待连接...
```
```bash
cd ./gomoku_Arena
python start_arena.py --config configs/multiround/round1.json
```
cd ./gomoku/AI_example
./start_ai.sh 11001 "AI_Alpha" "Alpha AI"
```

#### 启动第二个AI（终端3）
```bash
cd ./gomoku/AI_example
./start_ai.sh 11002 "AI_Beta" "Beta AI"
```

#### 启动第三个AI（终端4，可选）
```bash
cd ./gomoku/AI_example
./start_ai.sh 11003 "AI_Gamma" "Gamma AI"
```

**预期输出：**
```
启动快速五子棋AI服务器...
快速AI服务器配置:
端口: 11001
AI ID: AI_Alpha
AI名称: Alpha AI
AI服务器启动成功，监听端口: 11001
```

### 步骤3: 配置对战参数

编辑配置文件以匹配您启动的AI服务：

```bash
cd ./gomoku_Arena
nano configs/multiround/round1.json
```

**配置文件内容示例：**
```json
标准版本
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
  },
  "logging": {
    "level": "INFO",
    "file": "arena.log",
    "console": true
  }
}
```
```json
变体版本
{
  "game_server": {
    "url": "http://localhost:9001",
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
  },
  "logging": {
    "level": "INFO",
    "file": "arena.log",
    "console": true
  }
}
```

**重要配置说明：**
- `game_server.url`: 必须与步骤1中启动的游戏服务器地址一致
- `ais[].port`: 必须与步骤2中启动的AI服务端口一致
- `ais[].ai_id`: 必须与启动AI时指定的ID一致

### 步骤4: 运行对战

打开**终端5**，启动对战：

```bash
cd ./gomoku_Arena
python start_arena.py --config configs/multiround/round1.json
```

**预期输出：**
```
============================================================
五子棋AI对战平台
============================================================
游戏服务器: http://localhost:9000
超时时间: 10秒
每对AI对战轮数: 2
参赛AI数量: 2
  - Alpha AI (端口: 11001)
  - Beta AI (端口: 11002)

开始锦标赛...
检查AI健康状态...
✓ Alpha AI 健康
✓ Beta AI 健康
进行第 1/1 局对战
开始对战: Alpha AI (黑) vs Beta AI (白) - arena_xxx
...
```

## 📊 查看结果

对战完成后，您可以在以下位置查看结果：

### 1. 控制台输出
对战过程中会实时显示进度和结果

### 2. 报告文件
```bash
# 查看报告目录（在 gomoku_Arena 内）
ls reports/

# 查看文本格式报告
cat reports/tournament_report_*.txt

# 查看CSV格式报告
cat reports/tournament_report_*.csv
```

### 3. 日志文件
```bash
# 查看详细日志
tail -f logs/arena.log
```

## 🔧 常见问题

### 问题1: AI服务无法连接
**错误信息：** `AI Alpha AI 健康检查失败`

**解决方案：**
1. 检查AI服务是否正常启动
2. 确认端口号是否正确
3. 检查防火墙设置

```bash
# 检查AI服务状态
curl http://localhost:11001/health

# 检查端口占用
netstat -tlnp | grep 11001
```

### 问题2: 游戏服务器无法连接
**错误信息：** `创建游戏失败`

**解决方案：**
1. 确认游戏服务器正在运行
2. 检查端口9000是否被占用
3. 确认配置文件中的URL正确

```bash
# 检查游戏服务器状态
curl http://localhost:9000/health

# 重新启动游戏服务器（在仓库根或切换到 gomoku 目录）
cd ./gomoku
python server.py --port 9000
```

### 问题3: 配置文件错误
**错误信息：** `加载配置文件失败`

**解决方案：**
1. 检查JSON格式是否正确
2. 确认所有必需字段都存在
3. 验证端口号和AI ID匹配

```bash
# 验证JSON格式
python -m json.tool configs/multiround/round1.json
```

## 🎯 高级用法

### 1. 自定义AI数量
修改配置文件中的`ais`数组，添加或删除AI：

```json
{
  "ais": [
    {
      "ai_id": "AI_Alpha",
      "ai_name": "Alpha AI",
      "port": 11001
    },
    {
      "ai_id": "AI_Beta", 
      "ai_name": "Beta AI",
      "port": 11002
    },
    {
      "ai_id": "AI_Gamma",
      "ai_name": "Gamma AI", 
      "port": 11003
    }
  ]
}
```

### 2. 调整对战参数
```json
{
  "tournament": {
    "rounds_per_match": 3,      // 每对AI对战3轮
    "delay_between_games": 2,   // 对局间隔2秒
    "max_games_per_ai": 20      // 每个AI最多20局
  }
}
```

### 3. 指定特定AI对战
```bash
# 只让Alpha和Beta对战
python start_arena.py --config configs/multiround/round1.json --ais AI_Alpha AI_Beta
```

## 📝 注意事项

1. **端口冲突**: 确保每个AI使用不同的端口
2. **资源限制**: 大量对局时注意系统资源使用
3. **网络延迟**: 本地运行效果最佳
4. **日志清理**: 定期清理日志文件以节省空间

## 🎉 完成！

按照以上步骤，您就可以成功运行五子棋AI对战了。如果遇到问题，请检查日志文件或参考故障排除部分。

**祝您对战愉快！** 🎮
