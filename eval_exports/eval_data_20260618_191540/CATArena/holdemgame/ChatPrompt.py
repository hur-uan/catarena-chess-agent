import argparse
import os



def generate_prompt(args):
    """生成完整的prompt"""
    # 基础路径配置
    dir_path = args.code_path
    game_env_path = os.path.abspath(f'./{args.mode}_server/')

    game_server = f'http://localhost:{args.game_port}'
    
    
    # 构建基础prompt
    prompt_data = f'''
# Game Development
There is a game project under {game_env_path}. You need to read its source code and develop a game AI. Your AI will compete against other AIs in a tournament, so please make your AI as strategic and competitive as possible.

The final AI should be provided as an HTTP service. You can refer to the guides in {game_env_path}/README.md and {game_env_path}/develop_instruction.md for development instructions.
*The content in {game_env_path}/develop_instruction.md is very important, please read it carefully!*
The game is tournament mode, the tournament rules are in {game_env_path}/TOURNAMENT_MODE_README.md.

Please develop your AI service directly under {dir_path}. 
## Script Requirements
Please implement a script to start your AI service, with the name `start_ai.sh` in {dir_path}. The script must accept exactly one argument, which is the port number {args.game_port} to run the HTTP service. You should be able to start the AI service on a specified port by running:
```bash
bash start_ai.sh <port>
```
Your AI service should listen on the given port, and you can check its health status by running:
```bash
curl -s http://localhost:<port>/health
```
**Note:**  The script should not accept any other arguments except for the port number. Make sure your AI service uses this port for HTTP requests.


# Other Requirements
Use your model name as a prefix in the name of your AI service, i.e., `{args.model_name}_AI`.
Develop directly in {dir_path} without repeatedly asking for the next step. Report to me only after you have completed the development.

# Access the main server
You can play game of {game_env_path} in at {game_server}. You can play the games with your own AI or any other AI to improve your strategy. You can use bash tools to improve yourself.

# Final Remind
You should write start_ai.sh in {dir_path} and implement the AI service in {dir_path}. 
DO NOT MODIFY THE CODE IN {game_env_path}. 
Develop directly in {dir_path} without repeatedly asking for the next step.'''.strip()
    
    # 添加上一轮信息（如果轮次大于1）
    if args.round_num > 1:
        # 检查log和上一轮代码是否存在，如果不存在则直接报错
        if not os.path.exists(args.log_path):
            raise FileNotFoundError(f"上一轮日志文件未找到: {args.log_path}")
        if not os.path.exists(args.last_round_dir):
            raise FileNotFoundError(f"上一轮代码目录未找到: {args.last_round_dir}")
        
        prompt_data = prompt_data + f"\n\n ### Last Round Information \n Tournament report of last round is in: {args.log_path}. \n\n `tournament_repost_tourney_*.json` is a technical report of AI players in the tournament. `history_tourney_*.json` is the detailed history of each round in the tournament. \n\n Please read the report and history carefully, learn from it and improve your strategy."
        prompt_data = prompt_data + f"\n\n ### Code of Last Round \n\n Code of Last Round is in: {args.last_round_dir}. Please learn from it and improve your strategy. "
    
    prompt_data = prompt_data + f"\n\n ### Language \n\n Please develop in Python language. \n\n"

    return prompt_data

def main():
    parser = argparse.ArgumentParser(description='生成游戏AI开发的prompt')
    parser.add_argument("--model_name", type=str, default="ModelName", help="模型名称")
    parser.add_argument("--game_port", type=str, default="9010", help="游戏端口")
    parser.add_argument("--mode", type=str, default="traditional", choices=[ "traditional", "variant"], help="游戏模式")
    parser.add_argument("--round_num", type=int, default=1, help="循环赛轮次")
    parser.add_argument("--code_path", type=str, default="", help="代码路径")
    parser.add_argument("--log_path", type=str, default="", help="日志路径")
    parser.add_argument("--last_round_dir", type=str, default="", help="上一轮代码路径")
    args = parser.parse_args()
    
    # 生成并输出完整的prompt
    prompt = generate_prompt(args)
    print(prompt)

if __name__ == "__main__":
    main()
