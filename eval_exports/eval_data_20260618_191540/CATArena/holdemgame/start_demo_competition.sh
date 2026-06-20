
#!/bin/bash
PATH_TO_AI_EXAMPLES=$1
# example of running all steps
tmux_name="holdem_server"

# Kill existing tmux session if it exists
if tmux has-session -t "$tmux_name" 2>/dev/null; then
  echo "Existing tmux session '$tmux_name' found. Killing it..."
  tmux kill-session -t "$tmux_name"
fi

echo "Starting server..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
server_cmd="python $SCRIPT_DIR/traditional_server/server.py --port 9010"
tmux new-session -d -s "$tmux_name" "$server_cmd"

echo "Starting AIs ...."
bash $SCRIPT_DIR/start_ai.sh $PATH_TO_AI_EXAMPLES demo_AIs 51000 9010

echo "Starting arena..."
arena_cmd="python $SCRIPT_DIR/arena/arena_traditional.py --config $PATH_TO_AI_EXAMPLES/config.json"
tmux new-session -d -s "demo_arena" "$arena_cmd"

echo "Demo competition is running in tmux session 'demo_arena'!"