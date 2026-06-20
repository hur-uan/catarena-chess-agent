# GOMOKUGAME: 五子棋AI对战平台

一个基于现代AI技术的五子棋对战平台，支持多种AI算法和自定义AI参与对战。

## 🚀 快速开始

### 环境要求
- Python 3.8+
- 依赖包见 `requirements.txt`

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行Demo对战
```bash
bash start_demo_competition.sh
```

这将自动启动：
1. 五子棋游戏环境（端口9000）
2. Demo AI对战者（端口51000-51005），均为 `./AI_competitors/gomoku/round_1` 下面的AI
3. 竞技场对战系统
4. 生成对战报告到 `./gomoku_Arena/reports/demo_competition`

## 📁 项目结构

### 核心组件
- **`gomoku/`** - 标准五子棋游戏环境
- **`gomoku_variant/`** - 变体五子棋游戏环境
- **`gomoku_Arena/`** - 对战竞技场系统，兼容上述两者的对战

### AI对战者
- **`AI_competitors/gomoku/`** - 基于SOTA LLM + Minimal Agent开发的五子棋AI
- **`AI_competitors/gomoku_variant/`** - 基于SOTA LLM + Minimal Agent开发的变体五子棋AI
- **`AI_competitors/gomoku_commercial/`** - 商用Agent开发的五子棋AI
- **`AI_competitors/gomoku_variant_commercial/`** - 商用Agent开发的变体五子棋AI
- **`AI_competitors/strong_baseline/`** - 强基线AI

### 工具和配置
- **`ChatPrompt.py`** - 用于Code Agent开发棋牌AI的示例提示词
- **`start_ai_competitors.sh`** - 启动AI对战者的脚本（默认端口51000-51005）
- **`gomoku_Arena/configs/`** - 对战配置文件目录

## 🎯 使用自定义AI参加对战

### 步骤1：开发参赛AI
基于 `ChatPrompt.py` 中的示例提示词，使用您的Agent生成参赛AI。
```bash
python ChatPrompt.py
```

### 步骤2：启动AI服务
```bash
cd <你的参赛AI路径>
bash start_ai.sh <你的自定义端口>
```

### 步骤3：配置对战
修改 `gomoku_Arena/configs/demo_config.json`，添加您的AI配置：
```json
{
  "ais": [
    {
      "ai_id": "your_ai_id",
      "ai_name": "你的AI名称",
      "port": <你的端口号>,
      "description": "AI描述"
    }
  ]
}
```

### 步骤4：启动对战
```bash
python3 ./gomoku_Arena/start_arena.py \
  --config ./gomoku_Arena/configs/<你的配置文件> \
  --reports-dir ./gomoku_Arena/reports/<报告输出目录>
```

## 📊 对战报告

对战完成后，系统会在指定目录生成详细的对战报告，包括：
- 胜负统计
- 胜负矩阵
- 对局记录
- AI性能分析（平均思考时间）
- 完整游戏历史和最终状态
- 策略评估

报告支持多种格式：
- **JSON格式**: 完整的结构化数据
- **TXT格式**: 易读的文本格式
- **CSV格式**: 便于数据分析的表格格式
- **历史报告**: 包含每局游戏的详细历史和最终状态

## 🎮 游戏规则

### 标准五子棋
- 15x15棋盘
- 黑方先手
- 横、竖、斜连成五子获胜
- 不支持禁手规则

### API接口

#### 游戏服务器主要接口（默认端口9000）：
- `POST /games` - 创建游戏
- `GET /games/{game_id}/state` - 获取游戏状态
- `POST /games/{game_id}/move` - 提交移动
- `GET /games/{game_id}/history` - 获取历史记录
- `GET /health` - 健康检查

#### AI服务器必需接口：
- `GET /health` - 健康检查
- `GET /info` - AI信息
- `POST /join_game` - 加入游戏
- `POST /get_move` - 获取AI移动
- `POST /leave_game` - 离开游戏

## 📖 开发指南

### 创建自定义AI

1. **阅读文档**
   - `gomoku/README.md` - 游戏环境说明
   - `gomoku/develop_instruction.md` - 开发指南

2. **参考示例**
   - `gomoku/AI_example/` - 示例AI实现

3. **实现接口**
   - 实现标准的HTTP API接口
   - 编写 `start_ai.sh` 启动脚本

4. **测试AI**
   ```bash
   # 启动游戏服务器
   cd gomoku
   python server.py --port 9000
   
   # 启动AI服务
   cd <你的AI目录>
   bash start_ai.sh <端口号>
   
   # 测试健康检查
   curl http://localhost:<端口号>/health
   ```

### 策略建议

1. **胜利优先**: 优先寻找可以直接获胜的位置
2. **防守优先**: 阻止对手形成五连
3. **威胁构建**: 创造多个进攻点
4. **位置评估**: 评估每个位置的战略价值
5. **搜索算法**: 使用Minimax、Alpha-Beta剪枝等算法

## 🔧 技术栈

- **Python 3.8+**
- **Flask 2.3.3** - Web框架
- **Werkzeug 2.3.7** - WSGI工具库
- **requests 2.31.0** - HTTP客户端

## ⚡ 性能特性

### 竞技场性能优化
- ✅ 减少90%的冗余HTTP调用
- ✅ 提高对战效率50%
- ✅ 超时控制机制（10秒/步）
- ✅ 并发对战支持

### AI性能要求
- 响应时间: < 5秒/步
- 内存使用: 合理控制
- 错误处理: 优雅处理异常
- 并发支持: 支持多局游戏

## 📈 可视化分析

系统支持生成多种趋势图表：
- 总分趋势图
- 胜率趋势图
- 平均得分趋势图
- 综合趋势对比图

```bash
cd gomoku_Arena
python line_chart.py
```

## 🛠️ 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   # 检查端口占用
   netstat -tlnp | grep 9000
   
   # 杀死占用进程
   sudo kill -9 <PID>
   ```

2. **AI服务无法连接**
   ```bash
   # 检查AI健康状态
   curl http://localhost:51000/health
   
   # 查看AI日志
   tail -f <AI目录>/logs/*.log
   ```

3. **依赖安装失败**
   ```bash
   # 使用虚拟环境
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## 📚 参考资料

### 游戏环境文档
- [五子棋服务器README](gomoku/README.md)
- [五子棋开发指南](gomoku/develop_instruction.md)
- [竞技场使用指南](gomoku_Arena/README.md)
- [对战流程指南](gomoku_Arena/BATTLE_GUIDE.md)

### AI示例
- [基础AI示例](gomoku/AI_example/)
- [强基线AI](AI_competitors/strong_baseline/)

## 🎯 项目特点

### 与国际象棋平台对比

| 特性 | 五子棋 | 国际象棋 |
|------|--------|----------|
| **棋盘大小** | 15×15 | 8×8 |
| **棋子类型** | 2种（黑/白） | 6种（王、后、车、象、马、兵） |
| **移动规则** | 简单（任意空位） | 复杂（每种棋子不同） |
| **特殊规则** | 无 | 王车易位、吃过路兵、升变 |
| **胜利条件** | 连成5子 | 将死、认输、和棋 |
| **状态表示** | 2D数组 | FEN字符串 |
| **移动格式** | [x,y]坐标 | UCI格式(e2e4) |
| **游戏时长** | 相对较短 | 可能很长 |
| **策略复杂度** | 中等 | 非常高 |

## 🏆 竞技场特性

- **循环赛制**: 每个AI与其他所有AI对战
- **公平对战**: 每对AI交换黑白方各战一局
- **超时监控**: 10秒超时机制防止AI卡死
- **详细日志**: 完整的对战过程记录
- **多格式报告**: JSON、TXT、CSV多种格式
- **性能分析**: 平均思考时间统计
- **历史追溯**: 每局游戏的完整历史记录

## 📝 许可证

本项目采用MIT许可证。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目！

在提交代码前，请确保：
1. 代码符合Python PEP 8规范
2. 添加适当的注释和文档
3. 测试新功能的正确性
4. 更新相关文档

## 📧 联系方式

如有问题或建议，请通过Issue反馈。

---

**祝您在五子棋AI对战中取得好成绩！** 🎉
