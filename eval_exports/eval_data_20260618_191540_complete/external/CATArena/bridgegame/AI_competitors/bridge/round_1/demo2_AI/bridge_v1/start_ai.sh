#!/bin/bash

# Check if port argument is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <port>"
    exit 1
fi

PORT=$1

# Start the AI server with the specified port
python3 demo2.py --port $PORT
