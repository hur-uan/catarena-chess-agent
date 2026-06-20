# CHESSGAME: 国际象棋AI对战平台

一个基于现代AI技术的国际象棋对战平台，支持多种AI算法和自定义AI参与对战。

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
1. 国际象棋环境（端口9020）
2. Demo AI对战者（端口52000-52005）,均为  `./AI_competitors/chess/round_1` 下面的AI
3. 竞技场对战系统
4. 生成对战报告到 `./chess_Arena/reports/demo_competition`

## 📁 项目结构

### 核心组件
- **`chess/`** - 标准国际象棋游戏环境
- **`chess_variant/`** - 变体国际象棋游戏环境
- **`chess_Arena/`** - 对战竞技场系统。兼容上述两者的对战。

### AI对战者
- **`AI_competitors/chess/`** - 基于SOTA LLM + Minimal Agent开发的国际象棋AI
- **`AI_competitors/chess_variant/`** - 基于SOTA LLM + Minimal Agent开发的变体国际象棋AI
- **`AI_competitors/chess_commercial/`** - 商用Agent开发的国际象棋AI
- **`AI_competitors/chess_commercial_variant/`** - 商用Agent开发的变体国际象棋AI
- **`AI_competitors/strong_baseline/`** - 基于Stockfish引擎的强基线AI，需要单独安装stockfish依赖，见https://stockfishchess.org/download/
- **`AI_competitors/LLM-player/`** - LLM-player对战者

### 工具和配置
- **`ChatPrompt.py`** - 用于Code Agent开发棋牌AI的示例提示词
- **`start_ai_competitors.sh`** - 启动AI对战者的脚本（默认端口52000-52005）
- **`chess_Arena/configs/`** - 对战配置文件目录

## 🎯 使用自定义AI参加对战

### 步骤1：开发参赛AI
基于 `ChatPrompt.py` 中的示例提示词，使用您的Agent生成参赛AI。
```
python ChatPrompt.py
```

### 步骤2：启动AI服务
```bash
cd <你的参赛AI路径>
bash start_ai.sh <你的自定义端口>
```

### 步骤3：配置对战
修改 `chess_Arena/configs/demo_config.json`，添加您的AI配置：
```json
{
  "your_ai_name": {
    "host": "localhost",
    "port": <你的端口号>
  }
}
```

### 步骤4：启动对战
```bash
python3 ./chess_Arena/start_arena.py \
  --config ./chess_Arena/configs/<你的配置文件> \
  --reports-dir ./chess_Arena/reports/<报告输出目录>
```



## 📊 对战报告

对战完成后，系统会在指定目录生成详细的对战报告，包括：
- 胜负统计
- 对局记录
- AI性能分析
- 策略评估
