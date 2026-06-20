# CHESSGAME: Chess AI Battle Platform

A modern AI-powered chess battle platform that supports multiple AI algorithms and custom AI participation in battles.

## 🚀 Quick Start

### Requirements
- Python 3.8+
- Dependencies listed in `requirements.txt`

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Demo Battle
```bash
bash start_demo_competition.sh
```

This will automatically start:
1. Chess environment (port 9020)
2. Demo AI competitors (ports 52000-52005), all from `./AI_competitors/chess/round_1`
3. Arena battle system
4. Generate battle reports to `./chess_Arena/reports/demo_competition`

## 📁 Project Structure

### Core Components
- **`chess/`** - Standard chess game environment
- **`chess_variant/`** - Variant chess game environment
- **`chess_Arena/`** - Battle arena system, compatible with both environments

### AI Competitors
- **`AI_competitors/chess/`** - Chess AIs developed with SOTA LLM + Minimal Agent
- **`AI_competitors/chess_variant/`** - Variant chess AIs developed with SOTA LLM + Minimal Agent
- **`AI_competitors/chess_commercial/`** - Commercial Agent developed chess AIs
- **`AI_competitors/chess_commercial_variant/`** - Commercial Agent developed variant chess AIs
- **`AI_competitors/strong_baseline/`** - Strong baseline AIs based on Stockfish engine, requires separate stockfish dependency installation, see https://stockfishchess.org/download/
- **`AI_competitors/LLM-player/`** - LLM-player competitors

### Tools and Configuration
- **`ChatPrompt.py`** - Example prompts for Code Agent development of board game AIs
- **`start_ai_competitors.sh`** - Script to start AI competitors (default ports 52000-52005)
- **`chess_Arena/configs/`** - Battle configuration directory

## 🎯 Using Custom AI in Battles

### Step 1: Develop Your AI
Based on the example prompts in `ChatPrompt.py`, use your Agent to generate a competing AI.
```
python ChatPrompt.py
```

### Step 2: Start AI Service
```bash
cd <your_ai_path>
bash start_ai.sh <your_custom_port>
```

### Step 3: Configure Battle
Modify `chess_Arena/configs/demo_config.json` to add your AI configuration:
```json
{
  "your_ai_name": {
    "host": "localhost",
    "port": <your_port_number>
  }
}
```

### Step 4: Start Battle
```bash
python3 ./chess_Arena/start_arena.py \
  --config ./chess_Arena/configs/<your_config_file> \
  --reports-dir ./chess_Arena/reports/<report_output_directory>
```



## 📊 Battle Reports

After battle completion, the system generates detailed battle reports in the specified directory, including:
- Win/Loss statistics
- Game records
- AI performance analysis
- Strategy evaluation