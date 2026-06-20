# Chess HTTP Server

This directory contains a Flask-based HTTP server and a minimal AI example.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python server.py --port 9021
# or
./start_server.sh
```

## Endpoints

- POST `/games`
- GET `/games`
- GET `/games/{id}/state`
- POST `/games/{id}/move`
- GET `/games/{id}/history`
- GET `/games/{id}/board`
- GET `/games/{id}/legal_moves`
- GET `/health`

## Test

```bash
python test_client.py
```

## AI example

See `AI_example/ai_http_server.py`. The AI reads current state and available legal moves from the server and selects a move.


