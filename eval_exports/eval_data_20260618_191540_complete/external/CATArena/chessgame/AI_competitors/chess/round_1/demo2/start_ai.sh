#!/bin/bash

# # Check if exactly one argument is provided
# if [ $# -ne 1 ]; then
#     echo "Usage: $0 <port>"
#     exit 1
# fi

PORT=$1

# # Check if port is a number
# if ! [[ $PORT =~ ^[0-9]+$ ]]; then
#     echo "Error: Port must be a number"
#     exit 1
# fi

# # Install dependencies if not already installed
# if [ ! -d "venv" ]; then
#     python -m venv venv
#     source venv/bin/activate
#     pip install -r requirements.txt
# else
#     source venv/bin/activate
# fi

# Start the AI service
python3 demo2_ai.py --port $PORT