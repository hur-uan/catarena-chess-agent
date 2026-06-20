# CATArena_Holdem
## 🚀 Quick Start
### Environment Setup
- Python 3.8+
- Dependencies listed in requirements.txt
```bash
pip install -r requirements.txt
```

### Generate AI Code
Use `ChatPrompt.py` to get prompts, send to your code agent, and develop in the corresponding directory

Complete parameter description:
```bash
python ChatPrompt.py \
  --mode traditional \                    # Game mode: traditional or variant
  --model_name demo1 \        # Model name
  --game_port 9010 \                      # Game server port
  --round_num 1 \                         # Competition round
  --code_path /path/to/ai/code \          # AI code storage path
  --log_path /path/to/logs \              # Previous round log file path (required when round > 1)
  --last_round_dir /path/to/last/round    # Previous round code path (required when round > 1)
```
> **Tip:** Place AI codes that will battle simultaneously in one folder, divided into multiple subfolders

### Complete Workflow Example
Run the following command to start server, AI services, and automatically conduct battles (classic version):
```bash
cd catarena_holdem/
bash start_demo_competition.sh <AI_path>
```
For example:
```bash
bash start_demo_competition.sh ./AI_examples/traditional/round1/ADK/
```

### Start Hold'em Server
1. Start classic version server
```bash
bash start_server.sh traditional
```
2. Start variant version server
```bash
bash start_server.sh variant
```

> **Tip:** Record the server port information, generally 9010 for normal version, 9020 for variant version

### Start AI Services
Multiple AI sample interfaces are provided in the `AI_examples/` folder.

Run the following command to automatically start all AI players in `/path/to/ai/folder` in the `my_ai_session` window:
```bash
bash start_ai.sh /path/to/ai/folder my_ai_session
```
After execution, `config.json` will be automatically generated in `/path/to/ai/folder`.
> **Tip:** Manually check if the server port information in config.json matches the previously started one (9010/9020)

## Run Arena Competition
After starting server and AI services, you can conduct Tournament competitions. Tournament only requires a valid `config.json` file to run.
Start script (modes include traditional and variant):
```bash
bash run_arena.sh <mode> <config_path> <target_log_output_path_(optional)>
```
If no target log output path is set, reports and logs will be in the log folder under the parent directory of /path/to/config/.
`history_tourney_*.json` is the detailed log for each round of tournament, `tournament_report_tourney_*.json` is the statistical information for 100 rounds of tournament.



## Project Structure

```
catarena_holdem/
├── README.md                    # Project documentation
├── requirements.txt             # Python dependency list
├── start_server.sh             # Hold'em server startup script
├── start_ai.py                 # AI service management script
├── start_ai.sh                 # AI service startup script
├── run_arena.sh                # Arena competition run script
├── ChatPrompt.py                # Code Agent Prompt generation
│
├── traditional_server/          # Classic version Hold'em server
│   ├── server.py               # Classic version game server
│   ├── README.md               # Server documentation
│   └── TOURNAMENT_MODE_README.md # Tournament mode documentation
│
├── variant_server/              # Variant version Hold'em server
│   ├── server.py               # Variant version game server
│   ├── requirements.txt        # Server dependencies
│   ├── README.md               # Server documentation
│   └── TOURNAMENT_MODE_README.md # Tournament mode documentation
│
├── arena/                       # Arena competition system
│   ├── arena_traditional.py    # Classic version competition logic
│   ├── arena_variant.py        # Variant version competition logic
│   ├── config.py               # Competition configuration
│   ├── csv_reporter.py         # Report generator
│   └── blind_structure.json    # Blind structure configuration
│
├── AI_examples/                 # AI example code
│   ├── traditional/            # Classic version AI examples
│   └── variant/                # Variant version AI examples
│
├── config/                      # Configuration file directory
├── logs/                        # Log file directory
└── __pycache__/                 # Python cache files
```

### Core Component Description

#### 🎮 Game Server
- **traditional_server/**: Classic Texas Hold'em server, supports standard 52-card deck
- **variant_server/**: Variant Texas Hold'em server, supports 32-card deck (6-A)

#### 🤖 AI System
- **AI_examples/**: Provides multiple AI implementation examples
  - `simple/`: Basic random strategy AI
  - `strong_baseline/`: Advanced AI based on hand strength and position
  - `round_i/`: Baseline code agent implementation code
- **start_ai.py**: Intelligent AI service manager, supports batch startup and fault recovery

#### 🏆 Arena Competition System
- **arena_traditional.py**: Classic version tournament logic
- **arena_variant.py**: Variant version tournament logic
- **csv_reporter.py**: Generates detailed competition reports and statistics

#### 📊 Configuration and Logs
- **config.json**: AI and competition configuration file
- **blind_structure.json**: Blind structure definition
- **log/**: Stores competition history and statistical reports