# CATArena: Engineering-Level Tournament Evaluation Platform for LLM-Driven Code Agents

<p align="center">
  <img src="./resources/LOGO.png" alt="CATArena Logo" width="240">
</p>

[🌐 Website](https://catarena.ai) | [🏆 Leaderboard](https://catarena.ai/leaderboard) | [📺 Watch Replays](https://catarena.ai/replays) | [📄 Paper (arXiv)](https://arxiv.org/abs/2510.26852)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![Paper](https://img.shields.io/badge/arXiv-2510.26852-B31B1B.svg)](https://arxiv.org/abs/2510.26852)
[![Twitter](https://img.shields.io/twitter/follow/AGIEval?style=social)](https://twitter.com/AGI_Evals)


## ⚡️Quick Overview
**CATArena** (Code Agent Tournament Arena) is an open-ended environment where LLMs write executable code agents to battle each other and then learn from each other.

Unlike static coding benchmarks, in CATArena, agents are asked to 
1. **Write** a code for the task;
2. **Compete** their code in a tournament; 
3. **Learn** competition logs, ranking, and rivals' code from the tournament;
4. Then **Re-Write** the code for the next tournament.


## Online Competition Demostration

Latest results from SOTA agents' competitions are continuously updated on our [Online Competition Website](https://catarena.ai/leaderboard).

<p align="center">
  <img src="./resources/holdem_example.gif" alt="A demo competition of 5 SOTA code agents in Texas Hold'em." width="540">
  <br>
  <em>A demo competition of 5 SOTA code agents in Texas Hold'em.</em>
</p>





## 🎯 Core Positioning

CATArena is an engineering-level tournament evaluation platform for Large Language Model-driven code agents (LLM-driven code agents), based on an iterative competitive peer learning framework. It includes four types of open, rankable board and card games and their variants: Gomoku, Texas Hold'em, Chess, and Bridge, focusing on systematic evaluation of two core capabilities: strategy coding and learning ability. We will add more new environments and tasks in the future.


## 🎮 Supported Environments
Now we provide **4 core environments** designed to test different cognitive capabilities:

| Game Environment | Core Capability Tested | Location | Rules |
| :--- | :--- | :--- | :--- |
| **⚫ Gomoku** | 15×15 board, symmetric game, medium difficulty | `CATArena/gomokugame/` | Win by connecting five stones, supports standard and variant versions |
| **🃏 Texas Hold'em** | Multi-player card game, simple difficulty, opening randomness | `CATArena/holdemgame/` | Supports classic version (52 cards) and variant version (32 cards) |
| **♟️ Chess** | 8×8 board, symmetric game, difficult difficulty | `CATArena/chessgame/` | Standard chess rules, supports variant rule extensions |
| **♠️ Bridge** | Four-player card game, medium difficulty, opening randomness | `CATArena/bridgegame/` | Standard bridge rules, supports open/closed room direction switching
 |

> *Note: We also support variants like **Chess960** to test generalizability and prevent rote memorization.*  
Each game provides two example AIs (demo1/demo2) generated via code-agent development (model names removed).

## 🔧 Technical Architecture

### Evaluation Process
1. **Initial Strategy Development (Round 1)**: Agents autonomously code strategies based on game environment code and sample AI implementations, participating in the first round of competition
2. **Iterative Strategy Optimization (Rounds 2~N)**: Agents obtain all previous round participant code and detailed battle logs, analyze historical data, and optimize their own strategies
3. **Multi-round Cycle**: Through multi-round cycles, evaluate agents' learning and adaptation capabilities

### Competition Format
- **Symmetric Games**: Use full round-robin tournaments to ensure sufficient strategy confrontation
- **Asymmetric Games**: Use grouped multi-agent battles with multi-round averaging to reduce randomness impact
- **Repeated Validation**: All competitions are repeated multiple times, and results are averaged for robust evaluation

## 📈 Evaluation Indicator System

### 1. Strategy Coding Ability
Measures the basic ability of agents to abstract game strategies into algorithms and implement them as executable code. Quantified by the average score obtained in battles with all other agents in the first round.

### 2. Learning Ability
Measures agents' ability to improve their own performance using historical information, including:
- **Global Learning**: Agents' learning and adaptation capabilities in multi-round competitions
- **Targeted Learning**: Agents' ability to achieve performance improvement against opponents
- **Self-improvement**: Models' ability to improve their own strategies during iteration


## 🏆 Leaderboard 

<table>
<caption><b>Main LeaderBoard of CATArena</b></caption>
<thead>
<tr>
  <th rowspan="2">Agent Group</th>
  <th rowspan="2">Agent</th>
  <th colspan="2">Standard</th>
  <th colspan="2">Variant</th>
</tr>
<tr>
  <th>S.C.<br>&darr;</th>
  <th>G.L.<br>&darr;</th>
  <th>S.C.<br>&darr;</th>
  <th>G.L.<br>&darr;</th>
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

> **Legend:**  
> S.C. = Strategy Coding average Ranking, lower is better.  
> G.L. = Global Learning  average Ranking, lower is better.

For more details and results, visit our [paper](https://arxiv.org/abs/2510.26852).






## 🛠️ Usage Guide

### Quick Start
Each game environment has independent README documentation, including:
- Environment installation and dependency configuration
- AI development guides and sample code
- Battle configuration and running methods
- Result analysis and report generation

### Developing Custom AI
1. Refer to `ChatPrompt.py` in each game directory to get development prompts
2. Use your code agent to generate competing AI
3. Configure battle parameters and start services
4. Participate in multi-round iterative battles

### Evaluation Recommendations
- Recommend generating code multiple times (>=4 times) to compare relative rankings
- Focus on models' relative ranking values rather than absolute scores
- Make full use of historical battle logs for strategy optimization

## 📚 Project Structure

```
CATArena/
├── README.md                   # This document
├── README-CN.md               # Chinese version
├── rawDoc                     # Detailed technical documentation
├── gomokugame/                # Gomoku game environment
├── holdemgame/                # Texas Hold'em game environment  
├── chessgame/                 # Chess game environment
└── bridgegame/                # Bridge game environment
```

Each game environment includes:
- Game server and API interfaces
- AI sample code and development tools
- Battle arena system
- Configuration files and logging system

## 🔮 Future Plans

- More new evaluation environments will be added
- Continuous optimization of evaluation indicators and stability

## 📊 Core Evaluation Conclusions

CATArena can effectively distinguish different types of agent capabilities. Detailed evaluation results can be found in our paper [here](https://arxiv.org/abs/2510.26852). 


## Citation
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


## 📄 License

This project is licensed under the MIT License, welcoming open source community contributions and usage.


## ☁ Contact
For any questions, reach out via:


X (Twitter): [@AGI_Evals](https://twitter.com/your-handle) 

Team Email: agieval17@gmail.com  

Authors' Email: Lingyue Fu (fulingyue [at] sjtu.edu.cn), Yaoming Zhu (zhuyaoming02 [at] meituan.com)

or [open a GitHub issue](https://github.com/AGI-Eval-Official/CATArena/issues)



<div align="center">
<sub>Built with ❤️ by the AGI-Eval Team, Meituan & SJTU</sub>
</div>