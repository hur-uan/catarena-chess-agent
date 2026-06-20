#!/bin/bash

# Set mode from argument, default to 'traditional'
mode=${1:-traditional}
if [[ "$mode" == "variant" ]]; then
  tmux_name="variant_holdem_server"
else
  tmux_name="holdem_server"
fi

# Kill existing tmux session if it exists
if tmux has-session -t "$tmux_name" 2>/dev/null; then
  echo "Existing tmux session '$tmux_name' found. Killing it..."
  tmux kill-session -t "$tmux_name"
fi

# Find an available port starting from 9010(traditional)/9020(variant)
if [[ "$mode" == "variant" ]]; then
  port=9020
else
  port=9010
fi
while $(netstat -tuln | grep -q ":$port "); do
  port=$((port+1))
done

echo "Starting server on port $port (mode: $mode)"

# Get the absolute path of the current script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$mode" == "variant" ]]; then
  server_cmd="python $SCRIPT_DIR/variant_server/server.py --port $port"
else
  server_cmd="python $SCRIPT_DIR/traditional_server/server.py --port $port"
fi
# Start the server in a new tmux session
tmux new-session -d -s "$tmux_name" "$server_cmd"

echo "Server started in tmux session '$tmux_name' on port $port (mode: $mode)"