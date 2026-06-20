#!/bin/bash

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <port>"
    exit 1
fi

PORT=$1

# Start the AI HTTP service
DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$DIR/demo2_ai.py" --port $PORT