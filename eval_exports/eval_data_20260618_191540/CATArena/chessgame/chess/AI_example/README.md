# 国际象棋AI示例

这是一个国际象棋AI示例，展示了如何创建AI服务与国际象棋服务器进行对战。AI以HTTP服务的形式提供，便于与其他服务进行对战。

## 功能特性

- HTTP服务形式的AI实现
- RESTful API接口
- 支持多AI服务对战
- 多种AI算法实现（简单算法、Minimax算法）
- 自动对战功能
- 兼容性API设计

## AI策略

当前AI采用以下策略（按优先级排序）：

### 简单算法
1. **吃子优先**: 优先选择能吃子的移动
2. **中心控制**: 优先占据中心格子
3. **随机选择**: 在无特殊策略时随机选择合法移动

### Minimax算法
1. **深度搜索**: 使用3层深度的Minimax搜索
2. **Alpha-Beta剪枝**: 优化搜索效率
3. **位置评估**: 基于子力价值的简单评估函数

## 文件说明

- `ai_http_server.py` - AI HTTP服务器（推荐使用）
- `ai_coordinator.py` - AI对战协调器
- `test_ai_client.py` - AI客户端测试脚本
- `simple_ai_test.py` - AI逻辑测试脚本
- `start_ai.sh` - AI服务启动脚本
- `README.md` - 本说明文档

## AI HTTP服务API

### 1. 健康检查
**GET** `/health`

**响应:**
```json
{
  "status": "healthy",
  "ai_id": "ChessAI_1234",
  "active_games": 1,
  "timestamp": "2023-01-01T12:00:00"
}
```

### 2. 获取AI信息
**GET** `/info`

**响应:**
```json
{
  "ai_id": "ChessAI_1234",
  "name": "My Custom Chess AI",
  "version": "1.0",
  "description": "A simple Chess AI with basic strategy",
  "capabilities": ["simple_move", "minimax_move", "position_evaluation", "legal_moves"]
}
```

### 3. 加入游戏
**POST** `/join_game`

**请求体:**
```json
{
  "game_id": "chess_001",
  "my_color": "white",
  "game_server_url": "http://localhost:9020"
}
```

**响应:**
```json
{
  "status": "joined",
  "ai_id": "ChessAI_1234",
  "game_id": "chess_001",
  "my_color": "white"
}
```

### 4. 离开游戏
**POST** `/leave_game`

**请求体:**
```json
{
  "game_id": "chess_001"
}
```

### 5. 列出游戏
**GET** `/games`

**响应:**
```json
{
  "ai_id": "ChessAI_1234",
  "active_games": {
    "chess_001": {
      "my_color": "white",
      "joined_at": "2023-01-01T12:00:00"
    }
  }
}
```

### 6. 获取移动
**POST** `/move`

**请求体:**
```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "algorithm": "simple"
}
```

**响应:**
```json
{
  "ai_id": "ChessAI_1234",
  "ai_name": "My Chess AI",
  "move": "e2e4",
  "san": "e4",
  "from_square": "e2",
  "to_square": "e4",
  "promotion": null,
  "algorithm": "simple",
  "thinking_time": 0.001,
  "evaluation": 0.0,
  "timestamp": "2023-01-01T12:00:00"
}
```

## 使用方法

### 1. 启动AI HTTP服务

```bash
# 使用启动脚本（推荐）
./start_ai.sh                    # 使用默认参数
./start_ai.sh 41001 ChessAI_Alpha "Alpha Chess AI"  # 自定义参数

# 直接启动
python ai_http_server.py

# 自定义参数启动
python ai_http_server.py --port 41001 --ai_id ChessAI_Alpha --ai_name "My Custom AI" --game_server http://localhost:9020

# 启用调试模式
python ai_http_server.py --port 41001 --debug
```

### 2. 测试AI服务

```bash
python test_ai_client.py
```

### 3. AI对战测试

启动多个AI服务：

```bash
# 终端1: 启动AI Alpha
python ai_http_server.py --port 41001 --ai_id ChessAI_Alpha --ai_name "Alpha Chess AI"

# 终端2: 启动AI Beta
python ai_http_server.py --port 41002 --ai_id ChessAI_Beta --ai_name "Beta Chess AI"
```

然后运行对战协调器：

```bash
python ai_coordinator.py
```

### 4. 手动测试AI

使用curl测试AI服务：

```bash
# 健康检查
curl http://localhost:41001/health

# 获取AI信息
curl http://localhost:41001/info

# 加入游戏
curl -X POST http://localhost:41001/join_game \
  -H "Content-Type: application/json" \
  -d '{"game_id":"test_game","my_color":"white"}'

# 获取移动
curl -X POST http://localhost:41001/move \
  -H "Content-Type: application/json" \
  -d '{"fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1","current_player":"white"}'
```

## 启动多个AI服务进行对战

### 方法1: 使用协调器

1. 启动主游戏服务器：
```bash
cd ..
python server.py --port 9020
```

2. 启动多个AI服务：
```bash
# 终端1
python ai_http_server.py --port 41001 --ai_id ChessAI_Alpha --ai_name "Alpha Chess AI"

# 终端2
python ai_http_server.py --port 41002 --ai_id ChessAI_Beta --ai_name "Beta Chess AI"

# 终端3
python ai_http_server.py --port 41003 --ai_id ChessAI_Gamma --ai_name "Gamma Chess AI"
```

3. 运行对战协调器：
```bash
python ai_coordinator.py
```

### 方法2: 手动对战

1. 创建游戏：
```bash
curl -X POST http://localhost:9020/games \
  -H "Content-Type: application/json" \
  -d '{"player_white":"ChessAI_Alpha","player_black":"ChessAI_Beta"}'
```

2. 让AI加入游戏并开始对战

## AI算法说明

### 核心算法

1. **简单算法**: 优先吃子和控制中心的随机选择
2. **Minimax算法**: 使用Alpha-Beta剪枝的深度搜索
3. **位置评估**: 基于子力价值的评估函数

### 算法复杂度

- **简单算法**: O(n) 其中n为合法移动数
- **Minimax算法**: O(b^d) 其中b为分支因子，d为搜索深度

### 评估函数

使用传统的子力价值评估：
- 兵: 1分
- 马/象: 3分  
- 车: 5分
- 后: 9分
- 王: 0分（不参与计算）

## 扩展建议

1. **改进算法**: 实现更复杂的评估函数（位置价值、棋子协调等）
2. **深度学习**: 集成神经网络模型
3. **开局库**: 添加开局理论知识
4. **残局库**: 添加残局定式
5. **外部引擎**: 集成Stockfish等强力引擎
6. **多线程**: 支持并行计算
7. **配置化**: 支持AI参数配置

## 注意事项

- 确保国际象棋主服务器正在运行在端口9020 [[memory:5224680]]
- AI服务需要网络连接与游戏服务器通信
- 建议为不同AI实例使用不同端口避免冲突
- Minimax算法在深度较大时可能比较慢
- 当前评估函数较为简单，可能不够准确

## 依赖安装

```bash
pip install flask python-chess requests
```

## 故障排除

1. **端口冲突**: 使用`--port`参数指定不同端口
2. **依赖缺失**: 运行`pip install -r requirements.txt`
3. **连接失败**: 检查游戏服务器是否启动
4. **移动无效**: 检查FEN格式是否正确