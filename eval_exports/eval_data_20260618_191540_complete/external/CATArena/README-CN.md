# CATArena: 面向大语言模型代码开发智能体的工程级锦标赛式评测平台

<p align="center">
  <img src="./resources/LOGO.png" alt="CATArena Logo" width="240">
</p>

[🌐 官网](https://catarena.ai) | [🏆 排行榜](https://catarena.ai/leaderboard) | [📺 观看回放](https://catarena.ai/replays) | [📄 论文 (arXiv)](https://arxiv.org/abs/2510.26852)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![Paper](https://img.shields.io/badge/arXiv-2510.26852-B31B1B.svg)](https://arxiv.org/abs/2510.26852)
[![Twitter](https://img.shields.io/twitter/follow/AGIEval?style=social)](https://twitter.com/AGI_Evals)


## ⚡️ 快速概览
**CATArena** (Code Agent Tournament Arena) 是一个开放式的环境，大语言模型在此编写可执行的代码智能体，让它们相互对战并相互学习。

与静态的编程基准测试不同，在 CATArena 中，智能体需要：
1. **编写** 任务代码；
2. **参与** 锦标赛中的代码竞赛；
3. **学习** 锦标赛中的竞赛日志、排名和对手代码；
4. 然后为下一轮锦标赛**重新编写**代码。


## 在线竞赛演示

最新的大模型智能体竞赛结果持续更新在我们的[在线竞赛网站](https://catarena.ai/leaderboard)上。

<p align="center">
  <img src="./resources/holdem_example.gif" alt="5个SOTA代码智能体在德州扑克中的演示竞赛。" width="540">
  <br>
  <em>5个SOTA代码智能体在德州扑克中的演示竞赛。</em>
</p>




## 🎯 核心定位

CATArena 是面向大语言模型代码开发智能体(LLM-driven code agent)的工程级锦标赛式评测平台，基于迭代式竞争性同伴学习框架，包含五子棋、德州扑克、国际象棋、桥牌四类开放式、可排名的棋牌游戏及变体规则，聚焦智能体策略编码、学习能力两大核心能力的系统性评测。

## 🚀 开放性与扩展性

- **无分数上限**: CATArena的任务无明确分数上限，支持智能体通过多轮对战日志分析、策略迭代持续提升，动态适配 LLM 智能体能力的快速进化
- **强扩展性**: 框架具备强扩展性，可引入新游戏/变体规则（如 Chess960），也能扩展至新领域，且无需依赖专家级人工标注即可维持评测有效性
- **持续更新**: 未来会加入若干新环境。



## 🎮 支持的游戏环境
目前我们提供 **4 个核心环境**，旨在测试不同的认知能力：

| 游戏环境 | 核心能力测试 | 位置 | 规则 |
| :--- | :--- | :--- | :--- |
| **⚫ 五子棋** | 15×15棋盘，对称性游戏，中等难度 | `CATArena/gomokugame/` | 连成五子获胜，支持标准版本和变体版本 |
| **🃏 德州扑克** | 多人纸牌游戏，简单难度，开局随机性 | `CATArena/holdemgame/` | 支持经典版本(52张牌)和变体版本(32张牌) |
| **♟️ 国际象棋** | 8×8棋盘，对称性游戏，困难难度 | `CATArena/chessgame/` | 标准国际象棋规则，支持变体规则扩展 |
| **♠️ 桥牌** | 四人纸牌游戏，中等难度，开局随机性 | `CATArena/bridgegame/` | 标准桥牌规则，支持开房/闭房方向互换 |

> *注：我们还支持如 **Chess960** 等变体，以测试泛化能力并防止死记硬背。*  
每个游戏提供两个示例AI（demo1/demo2），这些AI通过代码智能体开发生成（已移除模型名称）。

## 🔧 技术架构

### 评测流程
1. **初始策略开发（Round 1）**: 智能体根据游戏环境代码和样例AI实现，自主编码策略，参与首轮竞赛
2. **迭代式策略优化（Rounds 2~N）**: 智能体获取前轮所有参赛代码及详细对战日志，分析历史数据，针对性优化自身策略
3. **多轮循环**: 通过多轮循环，评估智能体的学习与适应能力

### 比赛形式
- **对称游戏**: 采用全员循环赛，确保策略充分对抗
- **非对称游戏**: 采用分组多智能体对战，结果多轮平均以降低随机性影响
- **重复验证**: 所有比赛均重复多次，并对结果取平均值以进行稳健评估

## 📈 评测指标体系

### 1. 策略编码能力（Strategy Coding）
衡量智能体将游戏策略抽象为算法、并实现为可执行代码的基础能力。通过第一轮中与所有其他智能体对战获得的平均分数来量化。

### 2. 学习能力（Learning Ability）
衡量智能体利用历史信息提升自身表现的能力，包括：
- **全局学习**: 智能体在多轮比赛中的学习和适应能力
- **针对性学习**: 智能体针对对手实现成绩提升的能力
- **自我提升**: 模型在迭代过程中提升自己策略的能力


## 🏆 排行榜 

<table>
<caption><b>CATArena 主排行榜</b></caption>
<thead>
<tr>
  <th rowspan="2">智能体组</th>
  <th rowspan="2">智能体</th>
  <th colspan="2">标准</th>
  <th colspan="2">变体</th>
</tr>
<tr>
  <th>策略编码<br>&darr;</th>
  <th>全局学习<br>&darr;</th>
  <th>策略编码<br>&darr;</th>
  <th>全局学习<br>&darr;</th>
</tr>
</thead>
<tbody>
  <!-- Minimal Agents -->
  <tr>
    <td rowspan="6" style="writing-mode: vertical-rl; text-align: center;">Minimal</td>
    <td><b>Claude-4-Sonnet</b></td>
    <td><b>1.25</b></td>
    <td><b>2.5</b></td>
    <td><b>1.75</b></td>
    <td><b>2.75</b></td>
  </tr>
  <tr>
    <td>DeepSeek-Chat</td>
    <td>5.75</td>
    <td>2.75</td>
    <td>4.25</td>
    <td><b>2.75</b></td>
  </tr>
  <tr>
    <td>Doubao-Seed</td>
    <td>3.75</td>
    <td>4.75</td>
    <td>3.75</td>
    <td>4.50</td>
  </tr>
  <tr>
    <td>Gemini-2.5-Pro</td>
    <td>3.25</td>
    <td>3.75</td>
    <td>3.25</td>
    <td><b>2.75</b></td>
  </tr>
  <tr>
    <td>GPT-5</td>
    <td>3.75</td>
    <td>3.50</td>
    <td>3.00</td>
    <td>3.75</td>
  </tr>
  <tr>
    <td>Qwen3-Coder</td>
    <td>2.25</td>
    <td>3.75</td>
    <td>3.00</td>
    <td>4.5</td>
  </tr>
  <!-- Commercial Agents -->
  <tr>
    <td rowspan="5" style="writing-mode: vertical-rl; text-align: center;">Commercial</td>
    <td>best ADK</td>
    <td>3.25</td>
    <td><b>2.25</b></td>
    <td><b>2.00</b></td>
    <td>3.75</td>
  </tr>
  <tr>
    <td>Claude-Code</td>
    <td>2.50</td>
    <td>3.75</td>
    <td>2.50</td>
    <td>2.75</td>
  </tr>
  <tr>
    <td>CodeX</td>
    <td><b>2.25</b></td>
    <td>2.75</td>
    <td>3.00</td>
    <td>3.00</td>
  </tr>
  <tr>
    <td>Gemini-CLI</td>
    <td>3.50</td>
    <td><b>2.25</b></td>
    <td>3.00</td>
    <td>4.00</td>
  </tr>
  <tr>
    <td>Qwen-Coder</td>
    <td>3.00</td>
    <td>3.75</td>
    <td><b>4.00</b></td>
    <td><b>1.25</b></td>
  </tr>
</tbody>
</table>

> **图例说明：**  
> 策略编码 = 策略编码平均排名，数值越小越好。  
> 全局学习 = 全局学习平均排名，数值越小越好。

更多详细信息和结果，请访问我们的[论文](https://arxiv.org/abs/2510.26852)。




## 🛠️ 使用指南

### 快速开始
每个游戏环境都有独立的README文档，包含：
- 环境安装和依赖配置
- AI开发指南和示例代码
- 对战配置和运行方法
- 结果分析和报告生成

### 开发自定义AI
1. 参考各游戏目录下的`ChatPrompt.py`获取开发提示词
2. 使用您的代码智能体生成参赛AI
3. 配置对战参数和启动服务
4. 参与多轮迭代式对战

### 评测建议
- 建议多次(>=4次)生成代码比较相对排名
- 关注模型的排名相对值、而非关注得分的绝对值
- 充分利用历史对战日志进行策略优化

## 📚 项目结构

```
CATArena/
├── README.md                   # 英文文档
├── README-CN.md               # 本文档（中文版）
├── rawDoc                     # 详细技术文档
├── gomokugame/                # 五子棋游戏环境
├── holdemgame/                # 德州扑克游戏环境  
├── chessgame/                 # 国际象棋游戏环境
└── bridgegame/                # 桥牌游戏环境
```

每个游戏环境包含：
- 游戏服务器和API接口
- AI示例代码和开发工具
- 对战竞技场系统
- 配置文件和日志系统

## 🔮 未来规划

- 将加入更多新评测环境
- 持续优化评测指标和稳定性

## 📊 评测核心结论

CATArena能有效区分不同类型智能体能力。详细的评测结果请参见我们的[论文](https://arxiv.org/abs/2510.26852)。


## 引用
```
@misc{fu2025catarenaevaluationllmagents,
      title={CATArena: Evaluation of LLM Agents through Iterative Tournament Competitions}, 
      author={Lingyue Fu and Xin Ding and Yaoming Zhu and Shao Zhang and Lin Qiu and Weiwen Liu and Weinan Zhang and Xuezhi Cao and Xunliang Cai and Jiaxin Ding and Yong Yu},
      year={2025},
      eprint={2510.26852},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2510.26852}, 
}
```


## 📄 许可证

本项目采用 MIT 许可证，欢迎开源社区贡献和使用。


## ☁ 联系方式
如有任何问题，可通过以下方式联系我们：


X (Twitter): [@AGI_Evals](https://twitter.com/your-handle) 

团队邮箱: agieval17@gmail.com  

作者邮箱: Lingyue Fu (fulingyue [at] sjtu.edu.cn), Yaoming Zhu (zhuyaoming02 [at] meituan.com)

或[提交 GitHub Issue](https://github.com/AGI-Eval-Official/CATArena/issues)



<div align="center">
<sub>由 AGI-Eval 团队 & 美团 & 上海交通大学 联合构建</sub>
</div>
