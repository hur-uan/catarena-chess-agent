#!/bin/bash

# Check if the port argument is provided
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <port>"
  exit 1
fi

PORT=$1

# Start the AI HTTP service
python3 ai_http_server.py --port $PORT