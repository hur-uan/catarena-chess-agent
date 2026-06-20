# Chess AI示例

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
- `test_ai_client.py` - AI客户端测试脚本
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
  "name": "My Chess AI",
  "version": "1.0",
  "description": "A Chess AI with basic strategy",
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
  "game_server_url": "http://localhost:9021"
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

### 4. 获取移动（主要API）
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

### 5. 获取移动（兼容旧API）
**POST** `/get_move`

**请求体:**
```json
{
  "game_id": "chess_001",
  "current_player": "white"
}
```

**响应:**
```json
{
  "move": "e2e4",
  "ai_id": "ChessAI_1234",
  "game_id": "chess_001"
}
```

### 6. 离开游戏
**POST** `/leave_game`

**请求体:**
```json
{
  "game_id": "chess_001"
}
```

### 7. 列出游戏
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

## 使用方法

### 1. 启动AI HTTP服务

```bash
# 使用默认参数启动
python ai_http_server.py

# 自定义参数启动
python ai_http_server.py --port 41101 --ai_id ChessAI_Alpha --ai_name "My Chess AI" --game_server http://localhost:9021

# 启用调试模式
python ai_http_server.py --port 41101 --debug
```

### 2. 测试AI服务

```bash
python test_ai_client.py
```

### 3. 手动测试AI

使用curl测试AI服务：

```bash
# 健康检查
curl http://localhost:41101/health

# 获取AI信息
curl http://localhost:41101/info

# 加入游戏
curl -X POST http://localhost:41101/join_game \
  -H "Content-Type: application/json" \
  -d '{"game_id":"test_game","my_color":"white"}'

# 获取移动（主要API）
curl -X POST http://localhost:41101/move \
  -H "Content-Type: application/json" \
  -d '{"fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1","algorithm":"simple"}'

# 获取移动（兼容API）
curl -X POST http://localhost:41101/get_move \
  -H "Content-Type: application/json" \
  -d '{"game_id":"test_game","current_player":"white"}'
```

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

- 确保国际象棋主服务器正在运行在端口9021
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


