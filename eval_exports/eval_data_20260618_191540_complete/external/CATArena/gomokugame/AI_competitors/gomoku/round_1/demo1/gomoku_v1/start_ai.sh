#!/bin/bash

# Demo1 AI Service Startup Script

if [ $# -ne 1 ]; then
    echo "Usage: $0 <port>"
    echo "Example: $0 50009"
    exit 1
fi

PORT=$1

echo "Starting Demo1 Gomoku AI HTTP Service..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 not found, please install Python 3.7+"
    exit 1
fi

# Check if Flask is available
if ! python3 -c "import flask" &> /dev/null; then
    echo "Installing dependencies..."
    pip3 install flask requests
fi

# Start AI service
echo "AI Service starting..."
echo "Port: $PORT"
echo "AI ID: demo1_AI"
echo "Access URL: http://localhost:$PORT"
echo "Press Ctrl+C to stop service"
echo ""

python3 demo1_ai.py --port $PORT --ai_id "demo1_AI" --ai_name "Demo1 AI"