import requests
import json
import os
import shutil
import time
# for each prompt, I should first create a session, then send the query
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--model_name", type=str, default="gpt_4_1")
parser.add_argument("--language", type=str, default="")
parser.add_argument("--game_env", type=str, default="chess")
parser.add_argument("--game_suffix", type=str, default="chess")
parser.add_argument("--game_server", type=str, default="http://127.0.0.1:9020")
parser.add_argument("--dir_path", type=str, default="./develop_ai")

# 循环赛轮次
parser.add_argument("--round_num", type=int, default=1)
# round > 1时需要提供上一轮的日志和code
parser.add_argument("--log_path", type=str, default=None)
parser.add_argument("--last_round_dir", type=str, default=None)


args = parser.parse_args()

dir_path = args.dir_path
model_name = args.model_name
language = args.language
game_env = args.game_env
game_suffix = args.game_suffix
round_num = args.round_num
game_server = args.game_server
log_path = args.log_path
last_round_dir = args.last_round_dir


game_env_path = f'./{game_env}'


prompt_data = f'''
# Game Development
There is a game project under {game_env_path}. You need to read its source code and develop a game AI. Your AI will compete against other AIs in a tournament, so please make your AI as strategic and competitive as possible.

The final AI should be provided as an HTTP service. You can refer to the guides in {game_env_path}/README.md and {game_env_path}/develop_instruction.md for development instructions.
*The content in {game_env_path}/develop_instruction.md is very important, please read it carefully!*

Please develop your AI service directly under {dir_path}. 
## Script Requirements
Please implement a script to start your AI service, with the name `start_ai.sh` in {dir_path}. The script must accept exactly one argument, which is the port number to run the HTTP service. You should be able to start the AI service on a specified port by running:
```bash
bash start_ai.sh <port>
```
Your AI service should listen on the given port, and you can check its health status by running:
```bash
curl -s http://localhost:<port>/health
```
**Note:**  The script should not accept any other arguments except for the port number. Make sure your AI service uses this port for HTTP requests.


# Other Requirements
Use your model name as a prefix in the name of your AI service, i.e., `{model_name}_AI`.
Develop directly in {dir_path} without repeatedly asking for the next step. Report to me only after you have completed the development.

# Access the main server
You can play game of {game_env_path} in at {game_server}. You can play the games with your own AI or any other AI to improve your strategy. 
You can use bash tools to self-play to improve yourself.

# Final Remind
You should write game-play strategy by yourself, do not use any external game engine or API.
Do not set venv environment in your dir, just use python3 from bash.
You should write start_ai.sh in {dir_path} and implement the AI service in {dir_path}. DO NOT MODIFY THE CODE IN {game_env_path}.
'''.strip()


import glob

if round_num  > 1:
    assert os.path.exists(last_round_dir), f"上一轮的代码不存在: {last_round_dir}"
    last_round_log_dir = glob.glob(os.path.join(log_path, f'tournament_report_history_*.json'))
    last_round_log_dir = sorted(last_round_log_dir, key=lambda x: int(x.split('_')[-1].split('.')[0]))[-1]
    last_round_info = glob.glob(os.path.join(log_path, f'*_arena_report_*.csv'))
    last_round_info = sorted(last_round_info, key=lambda x: int(x.split('_')[-1].split('.')[0]))[-1]
    # find last one
    assert os.path.exists(last_round_log_dir), f"上一轮的日志不存在: {last_round_log_dir}"
    prompt_data = prompt_data + f"\n Tournament report of last round is in {last_round_info} and detailed history in {last_round_log_dir}. The historical records json are quite large. Please use tools `start_interactive_shell` and `run_interactive_shell` to analyze the data efficiently. You can use head or tail to pre-view the data, or use python to load this json file."
    prompt_data = prompt_data + f"\n The code of the previous round corresponding to the log is stored in:  {last_round_dir}. Please learn from it and improve your strategy. " 

if language:
    prompt_data = prompt_data + f"\n{language} is the language you should use to develop your AI service."

print(prompt_data)




