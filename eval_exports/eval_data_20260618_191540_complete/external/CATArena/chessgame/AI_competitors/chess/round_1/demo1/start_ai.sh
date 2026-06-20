#!/bin/bash

# Demo1 Chess AI Service Startup Script

echo "Starting Demo1 Chess AI HTTP Service..."

# Check if port argument is provided
if [ $# -ne 1 ]; then
    echo "Error: Exactly one argument (port number) is required"
    echo "Usage: bash start_ai.sh <port>"
    exit 1
fi

PORT=$1

# Validate port number
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo "Error: Invalid port number. Port must be between 1 and 65535"
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found. Please install Python 3.7+"
    exit 1
fi

# Check if required dependencies are installed
if ! python3 -c "import flask, chess" &> /dev/null; then
    echo "Installing dependencies..."
    pip3 install flask python-chess requests
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies"
        exit 1
    fi
fi

# Set AI configuration
AI_ID="demo1_AI_$(date +%s)"
AI_NAME="demo1_AI"

# Start AI service
echo "AI Service starting..."
echo "Port: $PORT"
echo "AI ID: $AI_ID"
echo "AI Name: $AI_NAME"
echo "Access URL: http://localhost:$PORT"
echo "Health check: curl -s http://localhost:$PORT/health"
echo "Press Ctrl+C to stop service"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Start the AI service
python3 "$SCRIPT_DIR/demo1_ai.py" --port "$PORT" --ai_id "$AI_ID" --ai_name "$AI_NAME"