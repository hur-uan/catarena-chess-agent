#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
import uuid
import random
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set

from flask import Flask, request, jsonify
import chess

app = Flask(__name__)


def square_name(square: int) -> str:
    return chess.square_name(square)


def generate_axis_symmetric_obstacles(board: chess.Board, *, num_pairs: int = 6, rng: Optional[random.Random] = None) -> Set[int]:
    rng = rng or random
    obstacles: Set[int] = set()

    candidates: List[int] = []
    for sq in chess.SQUARES:
        file_index = chess.square_file(sq)
        rank_index = chess.square_rank(sq)
        if 2 <= rank_index <= 5 and board.piece_at(sq) is None:
            if file_index <= 3:
                candidates.append(sq)

    rng.shuffle(candidates)

    for sq in candidates:
        if len(obstacles) >= num_pairs * 2:
            break
        if sq in obstacles:
            continue
        file_index = chess.square_file(sq)
        rank_index = chess.square_rank(sq)
        mirror_sq = chess.square(7 - file_index, rank_index)
        if board.piece_at(mirror_sq) is not None:
            continue
        if mirror_sq in obstacles:
            continue
        obstacles.add(sq)
        obstacles.add(mirror_sq)

    return obstacles


def choose_mutated_piece_type(rng: Optional[random.Random] = None) -> chess.PieceType:
    rng = rng or random
    candidates = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK]
    return rng.choice(candidates)


class ChessMagicGame:

    def __init__(self, game_id: str, player_white: str, player_black: str, *, chess960: bool = True,
                 num_obstacle_pairs: int = 6, seed: Optional[int] = None):
        self.game_id = game_id
        self.player_white = player_white
        self.player_black = player_black
        self.random = random.Random(seed)

        if chess960:
            self.chess960_pos = self.random.randint(0, 959)
            self.board = chess.Board.from_chess960_pos(self.chess960_pos)
        else:
            self.chess960_pos = None
            self.board = chess.Board()

        self.obstacles: Set[int] = generate_axis_symmetric_obstacles(self.board, num_pairs=num_obstacle_pairs, rng=self.random)
        self.mutated_piece_type: chess.PieceType = choose_mutated_piece_type(self.random)

        self.game_status = "ongoing"  # ongoing, white_win, black_win, draw
        self.moves_history: List[Dict] = []
        self.last_move: Optional[str] = None
        self.created_at = datetime.now()

        self.extra_move_available: bool = False
        self.pending_square: Optional[int] = None
        self.override_turn_color: Optional[bool] = None

    def get_current_player(self) -> str:
        if self.extra_move_available and self.override_turn_color is not None:
            return "white" if self.override_turn_color else "black"
        return "white" if self.board.turn else "black"

    def get_player_id(self, color: str) -> str:
        return self.player_white if color == "white" else self.player_black

    def _piece_type_at(self, square: int) -> Optional[chess.PieceType]:
        piece = self.board.piece_at(square)
        return piece.piece_type if piece else None

    def _is_move_with_mutated_piece(self, move: chess.Move) -> bool:
        return self._piece_type_at(move.from_square) == self.mutated_piece_type

    def _apply_obstacle_rule(self, move: chess.Move) -> Optional[str]:
        if move.to_square in self.obstacles:
            self.board.remove_piece_at(move.to_square)
            return f"piece_removed_by_obstacle@{square_name(move.to_square)}"
        return None

    def _update_game_status(self, moved_color: str) -> None:
        if self.board.is_checkmate():
            self.game_status = f"{moved_color}_win"
        elif self.board.is_stalemate():
            self.game_status = "draw_stalemate"
        elif self.board.is_insufficient_material():
            self.game_status = "draw_insufficient_material"
        elif self.board.is_fivefold_repetition():
            self.game_status = "draw_fivefold_repetition"
        elif self.board.is_seventyfive_moves():
            self.game_status = "draw_seventyfive_moves"

    def is_valid_move(self, player: str, move_uci: str) -> Tuple[bool, str]:
        if self.game_status != "ongoing":
            return False, "Game is already over"

        current_player = self.get_current_player()
        if player != current_player:
            return False, "Not your turn"

        try:
            move = chess.Move.from_uci(move_uci)
        except ValueError:
            return False, "Invalid move format"

        if self.extra_move_available:
            if self.pending_square is None:
                return False, "No pending piece for extra move"
            if move.from_square != self.pending_square:
                return False, "Second move must be with the same mutated piece"
            if self._piece_type_at(self.pending_square) != self.mutated_piece_type:
                return False, "Pending piece is not mutated or no longer available"

        if move not in self.board.legal_moves:
            return False, "Invalid move"

        return True, "Valid move"

    def make_move(self, player: str, move_uci: str) -> Tuple[bool, str, Optional[Dict]]:
        """Execute move and return (success, message, extra_info)."""
        is_valid, message = self.is_valid_move(player, move_uci)
        if not is_valid:
            return False, message, None

        move = chess.Move.from_uci(move_uci)
        moved_color_bool = (player == "white")
        extra_info: Dict = {}
        try:
            san_move = self.board.san(move)
            self.board.push(move)

            obstacle_effect = self._apply_obstacle_rule(move)
            if obstacle_effect:
                extra_info["obstacle_effect"] = obstacle_effect

            self.moves_history.append({
                "player": player,
                "move": move_uci,
                "obstacle": obstacle_effect is not None
            })
            self.last_move = move_uci

            if not self.extra_move_available:
                used_mutated = self._is_move_with_mutated_piece(move)
                piece_survived = (self.board.piece_at(move.to_square) is not None)
                if used_mutated and piece_survived:
                    self.extra_move_available = True
                    self.pending_square = move.to_square
                    self.override_turn_color = moved_color_bool
                else:
                    self.extra_move_available = False
                    self.pending_square = None
                    self.override_turn_color = None
            else:
                self.extra_move_available = False
                self.pending_square = None
                self.override_turn_color = None

            if self.extra_move_available:
                pending_piece = self.board.piece_at(self.pending_square) if self.pending_square is not None else None
                if pending_piece is None or pending_piece.piece_type != self.mutated_piece_type:
                    self.extra_move_available = False
                    self.pending_square = None
                    self.override_turn_color = None
                else:
                    has_followup = False
                    for lm in self.board.legal_moves:
                        if lm.from_square == self.pending_square:
                            has_followup = True
                            break
                    if not has_followup:
                        self.extra_move_available = False
                        self.pending_square = None
                        self.override_turn_color = None

            self._update_game_status(player)

            return True, "Move successful", extra_info
        except Exception as e:
            return False, f"Move execution failed: {str(e)}", None

    def get_state(self) -> Dict:
        current_player = self.get_current_player()
        return {
            "current_player": current_player,
            "fen": self.board.fen(),
            "last_move": self.last_move,
            "game_status": self.game_status,
            "is_check": self.board.is_check(),
            "is_checkmate": self.board.is_checkmate(),
            "is_stalemate": self.board.is_stalemate(),
            "legal_moves": self._list_legal_moves_filtered(),
            "chess960": True if self.chess960_pos is not None else False,
            "chess960_pos": self.chess960_pos,
            "obstacles": [square_name(sq) for sq in sorted(self.obstacles)],
            "mutated_piece_type": self._mutated_piece_name(),
            "extra_move_available": self.extra_move_available,
            "pending_square": square_name(self.pending_square) if self.pending_square is not None else None
        }

    def _mutated_piece_name(self) -> str:
        mapping = {
            chess.PAWN: "pawn",
            chess.KNIGHT: "knight",
            chess.BISHOP: "bishop",
            chess.ROOK: "rook",
            chess.QUEEN: "queen",
            chess.KING: "king",
        }
        return mapping.get(self.mutated_piece_type, "unknown")

    def _list_legal_moves_filtered(self) -> List[str]:
        if not self.extra_move_available or self.pending_square is None:
            return [m.uci() for m in self.board.legal_moves]
        return [m.uci() for m in self.board.legal_moves if m.from_square == self.pending_square]

    def get_history(self) -> Dict:
        return {"moves": self.moves_history}

    def get_board_visual(self) -> str:
        return str(self.board)


# In-memory games storage
games: Dict[str, ChessMagicGame] = {}


@app.route('/games', methods=['POST'])
def create_game():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400

        player_white = data.get('player_white')
        player_black = data.get('player_black')
        num_obstacle_pairs = data.get('num_obstacle_pairs', 6)
        seed = data.get('seed')

        if not player_white or not player_black:
            return jsonify({"error": "Both players must be specified"}), 400

        game_id = f"chess_magic_{str(uuid.uuid4())[:8]}"
        game = ChessMagicGame(game_id, player_white, player_black, chess960=True,
                              num_obstacle_pairs=int(num_obstacle_pairs), seed=seed)
        games[game_id] = game

        return jsonify({
            "game_id": game_id,
            "first_player": game.get_current_player(),
            "fen": game.board.fen(),
            "message": "Game created successfully",
            "chess960": True,
            "chess960_pos": game.chess960_pos,
            "obstacles": [square_name(sq) for sq in sorted(game.obstacles)],
            "mutated_piece_type": game._mutated_piece_name()
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/games/<game_id>/state', methods=['GET'])
def get_game_state(game_id):
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    game = games[game_id]
    return jsonify(game.get_state())


@app.route('/games/<game_id>/move', methods=['POST'])
def make_move(game_id):
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400

        player = data.get('player')
        move = data.get('move')

        if not player or not move:
            return jsonify({"error": "Player and move must be specified"}), 400

        if player not in ['white', 'black']:
            return jsonify({"error": "Player must be 'white' or 'black'"}), 400

        game = games[game_id]
        success, message, extra_info = game.make_move(player, move)

        if success:
            return jsonify({
                "status": "valid_move",
                "game_status": game.game_status,
                "message": message,
                "extra": extra_info or {},
                "new_state": game.get_state()
            })
        else:
            return jsonify({
                "status": "invalid_move",
                "error": message
            }), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/games/<game_id>/history', methods=['GET'])
def get_game_history(game_id):
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    game = games[game_id]
    return jsonify(game.get_history())


@app.route('/games/<game_id>/board', methods=['GET'])
def get_board_visual(game_id):
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    game = games[game_id]
    return jsonify({
        "game_id": game_id,
        "board_visual": game.get_board_visual(),
        "fen": game.board.fen(),
        "obstacles": [square_name(sq) for sq in sorted(game.obstacles)]
    })


@app.route('/games/<game_id>/legal_moves', methods=['GET'])
def get_legal_moves(game_id):
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    game = games[game_id]
    legal_moves = [chess.Move.from_uci(uci) for uci in game._list_legal_moves_filtered()]
    moves_info = []
    for m in legal_moves:
        moves_info.append({
            "uci": m.uci(),
            "san": game.board.san(m),
            "from_square": square_name(m.from_square),
            "to_square": square_name(m.to_square),
            "promotion": chess.piece_symbol(m.promotion) if m.promotion else None
        })
    return jsonify({
        "game_id": game_id,
        "current_player": game.get_current_player(),
        "legal_moves": moves_info,
        "extra_move_available": game.extra_move_available,
        "pending_square": square_name(game.pending_square) if game.pending_square is not None else None
    })


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "active_games": len(games),
        "server": "Chess Magic HTTP Server",
        "version": "1.0",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/games', methods=['GET'])
def list_games():
    games_info = []
    for game_id, game in games.items():
        games_info.append({
            "game_id": game_id,
            "player_white": game.player_white,
            "player_black": game.player_black,
            "game_status": game.game_status,
            "current_player": game.get_current_player(),
            "moves_count": len(game.moves_history),
            "created_at": game.created_at.isoformat(),
            "mutated_piece_type": game._mutated_piece_name(),
            "chess960_pos": game.chess960_pos
        })

    return jsonify({
        "games": games_info,
        "total_games": len(games)
    })


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


def main():
    parser = argparse.ArgumentParser(description='Chess HTTP Server')
    parser.add_argument('--port', type=int, default=40100, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    print(f"=== Chess HTTP Server ===")
    print(f"Port: {args.port}")
    print(f"Debug: {args.debug}")
    print(f"Address: http://localhost:{args.port}")
    print("")
    print("Endpoints:")
    print("  POST /games")
    print("  GET  /games")
    print("  GET  /games/{id}/state")
    print("  POST /games/{id}/move")
    print("  GET  /games/{id}/history")
    print("  GET  /games/{id}/board")
    print("  GET  /games/{id}/legal_moves")
    print("  GET  /health")
    print("")

    app.run(host='0.0.0.0', port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()


