# BRIDGEGAME: 桥牌AI对战平台

一个基于现代AI技术的桥牌对战平台，支持多种AI算法和自定义AI参与对战。

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
1. 桥牌游戏环境（端口9030-9031，配置中记录9030）
2. Demo AI对战者（端口50001-50012），均为 `./AI_competitors/bridge/round_1` 下面的AI
3. 竞技场对战系统
4. 生成对战报告到 `./bridge_Arena/reports/demo_competition`

**注意**：桥牌服务器需要在相邻的两个端口上启动（如9030和9031），但在配置文件中只需记录第一个端口（9030）。

## 📁 项目结构

### 核心组件
- **`bridge/`** - 标准桥牌游戏环境
- **`bridge_magic/`** - 魔术桥牌游戏环境（特殊规则变体）
- **`bridge_Arena/`** - 对战竞技场系统，兼容上述两者的对战

### AI对战者
- **`AI_competitors/bridge/`** - 基于SOTA LLM + Minimal Agent开发的桥牌AI
- **`AI_competitors/bridge_variant/`** - 基于SOTA LLM + Minimal Agent开发的变体桥牌AI
- **`AI_competitors/bridge_commercial/`** - 商用Agent开发的桥牌AI
- **`AI_competitors/bridge_variant_commercial/`** - 商用Agent开发的变体桥牌AI

### 工具和配置
- **`ChatPrompt.py`** - 用于Code Agent开发棋牌AI的示例提示词
- **`start_ai_competitors.sh`** - 启动AI对战者的脚本（默认端口50001-50012）
- **`bridge_Arena/configs/`** - 对战配置文件目录

## 🎯 使用自定义AI参加对战

### 步骤1：开发参赛AI
基于 `ChatPrompt.py` 中的示例提示词，使用您的Agent生成参赛AI。
```bash
python ChatPrompt.py --game_env bridge --game_server http://127.0.0.1:9030
```

### 步骤2：启动AI服务
桥牌AI需要启动在单个端口：
```bash
cd <你的参赛AI路径>
bash start_ai.sh <你的自定义端口>
```

### 步骤3：配置对战
修改 `bridge_Arena/configs/demo_config.json`，添加您的AI配置：
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

**重要**：在配置文件中只需记录AI的主端口号。

### 步骤4：启动对战
```bash
python3 ./bridge_Arena/start_arena.py \
  --config ./bridge_Arena/configs/<你的配置文件> \
  --reports-dir ./bridge_Arena/reports/<报告输出目录>
```

## 📊 对战报告

对战完成后，系统会在指定目录生成详细的对战报告，包括：
- 队伍排名
- 胜负统计
- 总分统计
- 对局记录
- AI性能分析
- 叫牌和打牌历史

报告支持多种格式：
- **JSON格式**: 完整的结构化数据
- **TXT格式**: 易读的文本格式

## 🎮 游戏规则

### 标准桥牌
- **玩家**: 4人（北N、东E、南S、西W）
- **搭档**: N-S vs E-W
- **每人牌数**: 13张
- **游戏阶段**: 叫牌 → 打牌

### 叫牌规则
- **Pass**: 不叫
- **Bid**: 叫牌（1♣-7NT）
- **Double**: 加倍（仅能在对手叫牌后）
- **Redouble**: 再加倍（仅能在对手加倍后）
- **叫牌结束**: 连续3个Pass

### 打牌规则
- **首攻**: 从庄家左手方首攻
- **跟牌**: 必须跟出同花色（如有）
- **将牌最大**: 将牌>其他花色，同花色比大小
- **赢墩者**: 赢墩者出下一张牌

### 计分规则
- **完成定约**: 基本分 × 加倍倍数
- **未完成定约**: 罚分
- **局况**: 影响罚分计算

### API接口

#### 游戏服务器主要接口（默认端口9030-9031）：
- `POST /games` - 创建游戏
- `POST /games/{game_id}/join` - 加入游戏
- `POST /games/{game_id}/start` - 开始游戏
- `GET /games/{game_id}/state?player_id={id}` - 获取游戏状态
- `GET /games/{game_id}/legal_actions?player_id={id}` - 获取合法动作
- `POST /games/{game_id}/call` - 叫牌
- `POST /games/{game_id}/play` - 打牌
- `GET /games/{game_id}/history` - 获取历史记录
- `GET /health` - 健康检查

#### AI服务器必需接口：
- `GET /health` - 健康检查
- `GET /info` - AI信息
- `POST /join_game` - 加入游戏
- `POST /get_action` - 获取AI动作（叫牌或打牌）
- `POST /leave_game` - 离开游戏
- `GET /games` - 列出活跃游戏

## 📖 开发指南

### 创建自定义AI

1. **阅读文档**
   - `bridge/README.md` - 游戏环境说明
   - `bridge/develop_instruction.md` - 开发指南

2. **参考示例**
   - `bridge/AI_example/` - 示例AI实现

3. **实现接口**
   - 实现标准的HTTP API接口
   - 编写 `start_ai.sh` 启动脚本

4. **测试AI**
   ```bash
   # 启动游戏服务器（相邻两个端口）
   cd bridge
   python server.py --port 9030
   
   # 启动AI服务
   cd <你的AI目录>
   bash start_ai.sh <端口号>
   
   # 测试健康检查
   curl http://localhost:<端口号>/health
   ```

### 策略建议

#### 叫牌策略
1. **开叫**: 13+点开叫，选择合适的叫品
2. **应叫**: 根据搭档的叫品选择合适应叫
3. **竞争**: 对手叫牌时选择合适的竞争叫品
4. **阻击**: 在合适时机使用阻击叫

#### 打牌策略
1. **首攻**: 选择合适的首攻牌
2. **跟牌**: 根据局势选择合适的跟牌
3. **将牌使用**: 合理使用将牌
4. **信号传递**: 通过出牌向搭档传递信号

## 🔧 技术栈

- **Python 3.8+**
- **Flask 2.3.3** - Web框架
- **Werkzeug 2.3.7** - WSGI工具库
- **requests 2.31.0** - HTTP客户端

## ⚡ 性能特性

### 竞技场特性
- ✅ 多种赛制支持（循环赛、复式赛、混合赛）
- ✅ 超时控制机制（10秒/动作）
- ✅ 并发对战支持
- ✅ 健康检查机制
- ✅ 详细日志记录

### AI性能要求
- 响应时间: < 10秒/动作
- 内存使用: 合理控制
- 错误处理: 优雅处理异常
- 并发支持: 支持多局游戏同时进行

## 🏆 竞技场特性

### 赛制类型

#### 1. 循环赛 (Round Robin)
- 每队与其他所有队伍对战
- 适合全面评估
- 游戏较多，持续时间较长

#### 2. 复式赛 (Duplicate - AA vs BB)
- 同一AI复制到两个位置
- 测试AI一致性和策略
- 执行速度较快

#### 3. 混合赛 (Mixed - AB vs CD)
- 不同AI配对组队
- 测试AI兼容性和团队合作
- 均衡评估

### 队伍配置
- **2v2格式**: 桥牌的天然2v2队伍结构
- **搭档协作**: 需要考虑搭档配合
- **信号传递**: 通过叫牌和打牌传递信息

### 部署说明
- **四实例部署**: 每队部署4个相同的AI服务，分别对应N、E、S、W四个位置
- **端口分配**: 通常每队使用4个连续端口（如50001-50004）
- **并发处理**: AI服务必须能够处理并发请求，同时参与多局游戏

## 📈 报告内容

### 队伍统计
- 队伍排名
- 胜/平/负场次
- 总得分
- 已玩游戏数

### 详细记录
- 游戏ID
- 参赛队伍
- 胜者
- 得分
- 游戏时长
- 叫牌历史
- 打牌历史

## 🛠️ 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   # 检查端口占用
   netstat -tlnp | grep 9030
   netstat -tlnp | grep 9031
   
   # 杀死占用进程
   sudo kill -9 <PID>
   ```

2. **AI服务无法连接**
   ```bash
   # 检查AI健康状态
   curl http://localhost:50001/health
   
   # 查看AI日志
   tail -f <AI目录>/logs/*.log
   ```

3. **游戏服务器错误**
   ```bash
   # 确保两个端口都可用
   netstat -tlnp | grep -E "(9030|9031)"
   
   # 重启游戏服务器
   cd bridge
   python server.py --port 9030
   ```

4. **依赖安装失败**
   ```bash
   # 使用虚拟环境
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## 📚 参考资料

### 游戏环境文档
- [桥牌服务器README](bridge/README.md)
- [桥牌开发指南](bridge/develop_instruction.md)
- [竞技场使用指南](bridge_Arena/README.md)
- [对战流程指南](bridge_Arena/BATTLE_GUIDE.md)
- [快速开始指南](bridge_Arena/QUICK_START.md)

### AI示例
- [基础AI示例](bridge/AI_example/)

## 🎯 项目特点

### 桥牌的复杂性

| 特性 | 桥牌 | 五子棋 | 国际象棋 |
|------|------|--------|----------|
| **玩家数** | 4人（2v2） | 2人 | 2人 |
| **合作性** | 搭档合作 | 对抗 | 对抗 |
| **游戏阶段** | 叫牌+打牌 | 单一阶段 | 单一阶段 |
| **信息** | 不完全信息 | 完全信息 | 完全信息 |
| **通信** | 有限（通过叫牌和打牌） | 无 | 无 |
| **计分** | 复杂计分系统 | 胜/负 | 胜/负/和 |
| **策略深度** | 非常高 | 中等 | 非常高 |
| **团队协作** | 核心要素 | 不适用 | 不适用 |

### 桥牌AI的挑战

1. **不完全信息**: 只能看到自己的牌
2. **搭档协作**: 需要与搭档配合
3. **信号传递**: 通过叫牌和打牌传递信息
4. **双阶段决策**: 叫牌和打牌需要不同策略
5. **复杂计分**: 需要理解桥牌计分规则

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

**祝您在桥牌AI对战中取得好成绩！** 🃏

