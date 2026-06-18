# CATArena Chess Agent

这个仓库当前收缩为一条可直接接入正式实验的 `profile-only` 参数自学习管线。

## 仓库结构

推荐提交到 GitHub 的主体目录如下：

- `agents/`: 正式棋类 agent、HTTP 适配器和内部搜索引擎。
- `optimization/`: 轮间自我提升主控逻辑。
- `tuning/`: 参数注册、SPSA、SPRT、prescreen 和 match runner。
- `tools/`: 日志解析、self-play、profile 管理、合法性校验、CATArena 适配等工具模块。
- `scripts/`: 单轮/连续运行、检查和校准入口。
- `config/`: 当前正式 profile、参数注册表和少量历史 profile 快照。
- `tests/`: 单元测试和核心流程回归测试。
- `web_ui/`: 本地棋盘调试界面。
- `external/` 与 `memory/`: 只保留占位文件，真实外部平台代码和 memory 日志本地生成或单独下载。

未提交到 GitHub 的内容：

- `.env`、虚拟环境、缓存文件。
- `reports/`、`eval_exports/`、`memory/*.jsonl` 等运行产物。
- `agents/candidates/`、`agents/generated/`、`agents/archive/` 等历史候选和生成代码。
- `external/CATArena/` 与 `black_numba-master/` 等第三方/大体积依赖。

核心结论：

- 正式运行时默认只走内部搜索引擎，不再默认使用 `black_numba`。
- 运行时代码固定，不允许轮间自动改写 `agents/chess_agent.py`。
- 只允许优化 `config/strategy_profile.json` 中已注册、可验证的参数。
- 正式在线自治优化面只保留 `search.tt_move_bonus`。
- 本地 self-play 生成的 `battle_logs/`、`ranking.csv`、历史 memory 和反馈 FEN 是默认反馈输入；CATArena 保留为外部对照/验收输入。

当前管线版本：

- `optimization_mode`: `profile_only`
- `pipeline_version`: `profile_only_v2_internal_runtime`
- `runtime_policy`: `formal_internal_only`
- `formal_execution_backend`: `internal_engine`

## 正式工具链

### 运行时下棋链路

入口是 `agents/chess_agent.py`。

正式实验链路固定为：

`observation -> strategy_profile -> search_router -> internal engine -> legal guard -> move`

保留下来的正式运行时 tool：

- `tools/strategy_profile.py`
- `tools/search_router.py`
- `agents/engine.py`
- `tools/move_validator.py`

`black_numba` 相关代码仍保留为研究备用路径，但默认 profile 已设置：

```json
"external_engine": {
  "enabled": false
}
```

这一步很重要：当前唯一在线可调参数 `search.tt_move_bonus` 直接作用于内部引擎的搜索排序。如果正式比赛默认走外部引擎，调参反馈会和实际执行器脱钩。

### 轮间自我提升链路

入口是 `optimization/meta_agent.py`

正式优化链路固定为：

`self-play logs/ranking/memory -> failure classification -> feedback FEN suite -> SPSA -> paired self-play -> SPRT -> feedback prescreen -> same-policy historical regression -> promotion gate -> optional profile promotion`

保留下来的正式优化 tool：

- `tools/log_parser.py`
- `tools/ranking_analyzer.py`
- `tools/self_play_platform.py`
- `tools/failure_classifier.py`
- `tools/fen_suite.py`
- `tuning/parameter_registry.py`
- `tuning/optimize_profile.py`
- `tuning/spsa.py`
- `tuning/match_runner.py`
- `tuning/sprt.py`
- `tuning/prescreen.py`
- `tools/opponent_pool.py`
- `tools/profile_regression.py`
- `tools/memory_store.py`

历史回归池现在只选择同一正式链路时代的 profile，也就是带有：

- `runtime_policy == formal_internal_only`
- `formal_execution_backend == internal_engine`

旧的 `profile_only_v1` 或外部执行器时代记录不会进入新候选的正式回归比较。

## 正式可调参数

正式在线自治优化只开放一个 block：

- `search.history_order`

其中真正可调参数只有：

- `search.tt_move_bonus`

同 block 中以下参数已冻结：

- `search.history_bonus_scale`
- `search.history_bonus_power`

其他已注册 block 均为离线研究对象，默认不进入正式在线自治优化：

- `eval.weights`
- `piece_activity`
- `pawn_structure`
- `king_safety`
- `search.depth_time`
- `move_ordering.tactical`
- `move_ordering.development`
- `search.mate_threshold`
- `eval.constants`
- `piece_values`
- `phase`
- `external_engine.*`

## 成熟反馈机制来源

当前正式链路只保留能对应成熟工程反馈机制的部分：

- Stockfish/Fishtest 风格：`SPSA + paired matches + SPRT + staged acceptance`
- AlphaZero/KataGo 风格：`self-play/evaluation gating + candidate promotion`
- 本仓库落地：`self-play feedback -> feedback FEN -> local prescreen -> historical regression -> promotion gate`

相关参考：

- https://github.com/official-stockfish/fishtest
- https://official-stockfish.github.io/docs/fishtest-wiki/Creating-my-first-test.html
- https://arxiv.org/abs/1712.01815
- https://github.com/lightvector/KataGo/blob/master/SelfplayTraining.md

## 已移除的正式链路

这些旧路径不再属于正式实验：

- LLM 生成候选 Python agent
- repair loop 自动修复候选代码
- 自动晋升运行时代码
- 默认外部 `black_numba` 下棋
- 未经成熟反馈门控的宽参数面在线优化

旧 CLI 参数仍保留兼容：

- `--backend rule`
- `--backend openai`
- `--promote-agent`
- `--max-repair-attempts`

实际执行语义统一为 `profile-only`。

## 正式实验入口

单轮：

```bash
env PYTHONPYCACHEPREFIX=.pycache .venv/bin/python \
  scripts/run_catarena_platform_round.py \
  --round-id self_play_profile_001 \
  --backend profile \
  --feedback-source self-play \
  --reports-dir reports/self_play_profile
```

连续多轮：

```bash
env PYTHONPYCACHEPREFIX=.pycache .venv/bin/python \
  scripts/run_continuous_learning.py \
  --start-round 1 \
  --round-count 10 \
  --round-prefix self_play_profile \
  --backend profile \
  --feedback-source self-play \
  --reports-dir reports/self_play_profile
```

外部 CATArena 对照可显式切换：

```bash
env PYTHONPYCACHEPREFIX=.pycache .venv/bin/python \
  scripts/run_continuous_learning.py \
  --start-round 1 \
  --round-count 3 \
  --round-prefix catarena_check \
  --backend profile \
  --feedback-source catarena \
  --reports-dir reports/catarena_platform
```

每轮核心产物：

- `optimization_report.json`
- `round_record.json`
- `evaluation_record.json`
- `parameter_record.json`
- `strategy_profile_before.json`
- `strategy_profile_after.json`
- `candidate_profile.json`
- `feedback_fen_suite.json`

候选 profile 只有在 validator、参数变化、反馈 prescreen、同链路历史回归和 promotion gate 都通过后，才允许写回正式 profile。
