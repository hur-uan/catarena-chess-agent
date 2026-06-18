import chess

from agents.engine import evaluate_board, search_best_move, select_move_record


def test_engine_select_move_record_returns_structured_search_data():
    board = chess.Board()
    record = select_move_record({"fen": board.fen()})
    assert record.selected_move
    assert record.depth >= 0
    assert record.nodes >= 0
    assert record.qnodes >= 0
    assert "win" in record.wdl


def test_engine_prefers_forced_mate_when_available():
    board = chess.Board("6k1/5Q2/6K1/8/8/8/8/8 w - - 0 1")
    result = search_best_move(board, time_limit_ms=100)
    assert result.move is not None
    board.push(result.move)
    assert board.is_checkmate()
    assert result.mate_distance is not None and result.mate_distance > 0


def test_evaluate_board_is_positive_for_large_material_advantage():
    board = chess.Board("7k/8/8/8/8/8/7Q/7K w - - 0 1")
    assert evaluate_board(board, chess.WHITE) > 500


def test_search_avoids_expensive_threefold_claim_check(monkeypatch):
    def fail_threefold_claim(self):
        raise AssertionError("threefold claim check should not run inside search")

    monkeypatch.setattr(chess.Board, "can_claim_threefold_repetition", fail_threefold_claim)

    board = chess.Board()
    result = search_best_move(board, time_limit_ms=20)

    assert result.move is not None
    assert evaluate_board(board, chess.WHITE) == 0
