#!/bin/bash

# Bridge Arena Startup Script
# This script starts the bridge AI tournament platform

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}=== Bridge AI Tournament Platform ===${NC}"
echo

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

# Check if required packages are installed
echo -e "${YELLOW}Checking dependencies...${NC}"
python3 -c "import requests, json, logging, threading, csv, datetime, typing, dataclasses, concurrent.futures, signal, sys, os" 2>/dev/null || {
    echo -e "${RED}Error: Required Python packages are missing${NC}"
    echo "Please install required packages:"
    echo "pip3 install requests"
    exit 1
}

# Create necessary directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p logs
mkdir -p reports
mkdir -p configs

# Check if bridge server is running
echo -e "${YELLOW}Checking bridge server status...${NC}"
if curl -s http://localhost:50000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Bridge server is running on port 50000${NC}"
else
    echo -e "${YELLOW}⚠ Bridge server is not running on port 50000${NC}"
    echo "Please start the bridge server first:"
    echo "cd ../bridge && python3 server.py --port 50000"
    echo
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --config FILE           Configuration file (default: configs/arena_config.json)"
    echo "  --server-url URL        Bridge server URL (default: http://localhost:50000)"
    echo "  --timeout SECONDS       AI timeout (default: 10)"
    echo "  --rounds N              Rounds per match (default: 2)"
    echo "  --tournament-type TYPE  Tournament type: round_robin or duplicate (default: round_robin)"
    echo "  --create-config TYPE    Create config: quick, duplicate, or mixed"
    echo "  --list-configs          List available configurations"
    echo "  --validate              Validate configuration"
    echo "  --help                  Show this help message"
    echo
    echo "Examples:"
    echo "  $0 --list-configs                    # List configurations"
    echo "  $0 --create-config duplicate         # Create duplicate teams config"
    echo "  $0 --config configs/duplicate_config.json --tournament-type duplicate"
    echo "  $0 --server-url http://localhost:50000 --rounds 3"
}

# Parse command line arguments
if [[ $# -eq 0 ]]; then
    show_usage
    exit 0
fi

# Check for help
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    show_usage
    exit 0
fi

# Build Python command
PYTHON_CMD="python3 start_arena.py"

# Add arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            PYTHON_CMD="$PYTHON_CMD --config $2"
            shift 2
            ;;
        --server-url)
            PYTHON_CMD="$PYTHON_CMD --server-url $2"
            shift 2
            ;;
        --timeout)
            PYTHON_CMD="$PYTHON_CMD --timeout $2"
            shift 2
            ;;
        --rounds)
            PYTHON_CMD="$PYTHON_CMD --rounds $2"
            shift 2
            ;;
        --tournament-type)
            PYTHON_CMD="$PYTHON_CMD --tournament-type $2"
            shift 2
            ;;
        --create-config)
            PYTHON_CMD="$PYTHON_CMD --create-config $2"
            shift 2
            ;;
        --list-configs)
            PYTHON_CMD="$PYTHON_CMD --list-configs"
            shift
            ;;
        --validate)
            PYTHON_CMD="$PYTHON_CMD --validate"
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_usage
            exit 1
            ;;
    esac
done

# Run the arena
echo -e "${GREEN}Starting Bridge Arena...${NC}"
echo "Command: $PYTHON_CMD"
echo

eval $PYTHON_CMD

echo
echo -e "${GREEN}Bridge Arena finished${NC}"
