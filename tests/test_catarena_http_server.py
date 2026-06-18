import chess

from agents.catarena_http_server import ACTIVE_GAMES, app
from tools.move_validator import validate_move


def test_catarena_http_move_endpoint_returns_demo_shape():
    client = app.test_client()
    board = chess.Board()
    response = client.post("/move", json={"fen": board.fen(), "algorithm": "local_baseline"})
    assert response.status_code == 200
    payload = response.get_json()
    assert validate_move(board, payload["move"]).is_legal
    assert payload["from_square"]
    assert payload["to_square"]
    assert "san" in payload


def test_catarena_http_get_move_requires_joined_game():
    ACTIVE_GAMES.clear()
    client = app.test_client()
    join_response = client.post(
        "/join_game",
        json={"game_id": "g1", "my_color": "white", "game_server_url": "http://localhost:9020"},
    )
    assert join_response.status_code == 200
    board = chess.Board()
    move_response = client.post(
        "/get_move",
        json={"game_id": "g1", "fen": board.fen(), "current_player": "white"},
    )
    assert move_response.status_code == 200
    assert validate_move(board, move_response.get_json()["move"]).is_legal
