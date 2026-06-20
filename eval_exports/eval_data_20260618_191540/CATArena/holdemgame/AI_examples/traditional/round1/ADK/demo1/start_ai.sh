#!/bin/bash

# Demo1 AI Startup Script
# Usage: bash start_ai.sh <port>

# Check if port argument is provided
if [ $# -ne 1 ]; then
    echo "Usage: bash start_ai.sh <port>"
    echo "Example: bash start_ai.sh 9013"
    exit 1
fi

PORT=$1

# Validate port number
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
    echo "Error: Port must be a number between 1024 and 65535"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the script directory
cd "$SCRIPT_DIR"

echo "Starting Demo1 AI on port $PORT..."
echo "AI Service: demo1_AI"
echo "Health check: curl -s http://localhost:$PORT/health"
echo "Press Ctrl+C to stop the AI service"
echo "----------------------------------------"

# Start the AI service
python3 demo1_ai.py --port "$PORT"