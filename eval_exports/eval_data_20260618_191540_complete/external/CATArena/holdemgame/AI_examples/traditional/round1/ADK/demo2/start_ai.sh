#!/bin/bash

# Check if port argument is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <port>"
    exit 1
fi

PORT=$1

# Start the AI service
python3 demo2_ai.py --port $PORT
