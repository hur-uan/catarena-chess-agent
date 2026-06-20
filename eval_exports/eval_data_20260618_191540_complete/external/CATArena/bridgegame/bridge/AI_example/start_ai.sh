#!/bin/bash



set -e

# Check if port argument is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <port>"
    echo "Example: $0 50001"
    exit 1
fi

PORT=$1

# Validate port number
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
    echo "Error: Port must be a number between 1024 and 65535"
    exit 1
fi

# Configuration
GAME_SERVER="http://localhost:9030"
AI_ID="advanced_bridge_AI"
AI_NAME="Advanced Bridge AI"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AI_SCRIPT="$SCRIPT_DIR/ai_http_server.py"

echo "=== Starting Advanced Bridge AI ==="
echo "Port: $PORT"
echo "Game Server: $GAME_SERVER"
echo "AI ID: $AI_ID"
echo "AI Name: $AI_NAME"
echo "Script: $AI_SCRIPT"
echo ""

# Check if the AI script exists
if [ ! -f "$AI_SCRIPT" ]; then
    echo "Error: AI script not found at $AI_SCRIPT"
    exit 1
fi

# Check if Python3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed or not in PATH"
    exit 1
fi

# Check if required Python packages are available
python3 -c "import flask, requests" 2>/dev/null || {
    echo "Error: Required Python packages (flask, requests) are not installed"
    echo "Please install them with: pip install flask requests"
    exit 1
}

# Check if game server is running
echo "Checking game server connection..."
if curl -s -f "$GAME_SERVER/health" > /dev/null 2>&1; then
    echo "✓ Game server is running"
else
    echo "⚠ Warning: Cannot connect to game server at $GAME_SERVER"
    echo "  Make sure the bridge server is running before starting games"
fi

echo ""
echo "Starting AI service..."

# Start the AI service
exec python3 "$AI_SCRIPT" \
    --port "$PORT" \
    --ai_id "$AI_ID" \
    --ai_name "$AI_NAME" \
    --game_server "$GAME_SERVER"