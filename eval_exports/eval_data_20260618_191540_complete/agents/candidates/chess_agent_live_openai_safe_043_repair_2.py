import time

import chess


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

MATE_SCORE = 100000
INF = 10**9
CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
EXT_CENTER = {
    chess.C3,
    chess.D3,
    chess.E3,
    chess.F3,
    chess.C4,
    chess.D4,
    chess.E4,
    chess.F4,
    chess.C5,
    chess.D5,
    chess.E5,
    chess.F5,
    chess.C6,
    chess.D6,
    chess.E6,
    chess.F6,
}


class ChessAgent:
    def __init__(self, output_format='uci', time_limit_ms=100):
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation):
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(observation, output_format='uci', time_limit_ms=100):
    try:
        board = _parse_board(observation)
        legal_moves = list(board.legal_moves)
        if not legal_moves or board.is_game_over(claim_draw=False):
            return ''
        chosen = _choose_move(board, legal_moves, time_limit_ms)
        if chosen not in legal_moves:
            chosen = legal_moves[0]
        return _format_move(board, chosen, output_format)
    except Exception:
        try:
            board = _parse_board(observation)
            fallback = list(board.legal_moves)
            if fallback:
                return fallback[0].uci()
        except Exception:
            pass
        return ''


def agent(observation):
    return select_move(observation)


def act(observation):
    return select_move(observation)


def move(observation):
    return select_move(observation)


def _parse_board(observation):
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)
    if isinstance(observation, dict):
        for key in ('fen', 'board', 'state'):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                return chess.Board(value.strip())
        nested = observation.get('observation')
        if isinstance(nested, dict):
            return _parse_board(nested)
        if isinstance(nested, str) and nested.strip():
            return chess.Board(nested.strip())
    if isinstance(observation, str) and observation.strip():
        text = observation.strip()
        if text.lower() in {'start', 'startpos'}:
            return chess.Board()
        return chess.Board(text)
    return chess.Board()


def _format_move(board, move_obj, output_format):
    requested = (output_format or 'uci').lower().strip()
    if requested == 'san':
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    return move_obj.uci()


def _choose_move(board, legal_moves, time_limit_ms):
    mate = _find_immediate_mate(board, legal_moves)
    if mate is not None:
        return mate

    budget_ms = max(8, min(180, int(time_limit_ms or 100)))
    deadline = time.perf_counter() + max(0.004, (budget_ms - 4) / 1000.0)
    best_move = max(legal_moves, key=lambda item: _move_order_score(board, item))
    ordered = _ordered_moves(board, legal_moves)

    max_depth = 2
    if budget_ms >= 55:
        max_depth = 3
    if budget_ms >= 130 and len(legal_moves) <= 30:
        max_depth = 4

    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        alpha = -INF
        depth_best = best_move
        depth_score = -INF
        for candidate in ordered:
            if time.perf_counter() >= deadline:
                break
            board.push(candidate)
            score = -_negamax(board, depth - 1, -INF, -alpha, deadline, 1)
            board.pop()
            if score > depth_score:
                depth_score = score
                depth_best = candidate
            if score > alpha:
                alpha = score
        if time.perf_counter() < deadline and depth_best in legal_moves:
            best_move = depth_best
            if depth_score >= MATE_SCORE - 128:
                break
    return best_move


def _negamax(board, depth, alpha, beta, deadline, ply):
    if time.perf_counter() >= deadline:
        return _evaluate_for_turn(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply)

    value = -INF
    moves = _ordered_moves(board, list(board.legal_moves))
    for candidate in moves:
        board.push(candidate)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score > value:
            value = score
        if score > alpha:
            alpha = score
        if alpha >= beta or time.perf_counter() >= deadline:
            break
    return value


def _quiescence(board, alpha, beta, deadline, ply):
    if board.is_checkmate():
        return -MATE_SCORE + ply
    stand_pat = _evaluate_for_turn(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if time.perf_counter() >= deadline:
        return alpha

    tactical = []
    for candidate in board.legal_moves:
        if board.is_capture(candidate) or candidate.promotion or board.gives_check(candidate):
            tactical.append(candidate)
    for candidate in _ordered_moves(board, tactical):
        if time.perf_counter() >= deadline:
            break
        board.push(candidate)
        score = -_quiescence(board, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _find_immediate_mate(board, legal_moves):
    for candidate in _ordered_moves(board, legal_moves):
        board.push(candidate)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return candidate
    return None


def _ordered_moves(board, moves):
    return sorted(moves, key=lambda item: _move_order_score(board, item), reverse=True)


def _move_order_score(board, move_obj):
    score = 0
    moving_piece = board.piece_at(move_obj.from_square)
    captured_piece = board.piece_at(move_obj.to_square)

    if board.is_capture(move_obj):
        if captured_piece is None and board.is_en_passant(move_obj):
            captured_value = PIECE_VALUES[chess.PAWN]
        elif captured_piece is None:
            captured_value = 0
        else:
            captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0)
        attacker_value = 0
        if moving_piece is not None:
            attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0)
        score += 10000 + captured_value * 10 - attacker_value
    if move_obj.promotion:
        score += 9000 + PIECE_VALUES.get(move_obj.promotion, 0)
    if board.gives_check(move_obj):
        score += 7000
    if board.is_castling(move_obj):
        score += 1200
    if move_obj.to_square in CENTER:
        score += 150
    elif move_obj.to_square in EXT_CENTER:
        score += 60

    if moving_piece is not None:
        piece_type = moving_piece.piece_type
        if piece_type in (chess.KNIGHT, chess.BISHOP):
            if _is_back_rank(move_obj.from_square, moving_piece.color):
                score += 190
        if piece_type == chess.PAWN and move_obj.to_square in CENTER:
            score += 80
        if piece_type == chess.QUEEN and board.fullmove_number <= 8:
            score -= 100
        if piece_type == chess.ROOK and board.fullmove_number <= 10:
            score -= 35
    return score


def _is_back_rank(square, color):
    rank = chess.square_rank(square)
    if color == chess.WHITE:
        return rank == 0
    return rank == 7


def _evaluate_for_turn(board):
    score = _evaluate_white_minus_black(board)
    if board.turn == chess.WHITE:
        return score
    return -score


def _evaluate_white_minus_black(board):
    if board.is_checkmate():
        if board.turn == chess.WHITE:
            return -MATE_SCORE
        return MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    white_bishops = 0
    black_bishops = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES.get(piece.piece_type, 0)
        bonus = _piece_square_bonus(piece, square)
        piece_score = value + bonus
        if piece.color == chess.WHITE:
            score += piece_score
            if piece.piece_type == chess.BISHOP:
                white_bishops += 1
        else:
            score -= piece_score
            if piece.piece_type == chess.BISHOP:
                black_bishops += 1

    if white_bishops >= 2:
        score += 28
    if black_bishops >= 2:
        score -= 28
    score += _pawn_structure_score(board, chess.WHITE)
    score -= _pawn_structure_score(board, chess.BLACK)
    score += _king_safety_score(board, chess.WHITE)
    score -= _king_safety_score(board, chess.BLACK)
    score += _hanging_piece_score(board)
    score += _mobility_score(board)
    if board.is_check():
        if board.turn == chess.WHITE:
            score -= 35
        else:
            score += 35
    return score


def _piece_square_bonus(piece, square):
    lookup = square
    if piece.color == chess.BLACK:
        lookup = chess.square_mirror(square)
    file_index = chess.square_file(lookup)
    rank_index = chess.square_rank(lookup)
    center_file_distance = abs(file_index - 3.5)
    center_rank_distance = abs(rank_index - 3.5)
    center_bonus = int(12 - 3 * (center_file_distance + center_rank_distance))

    if piece.piece_type == chess.PAWN:
        bonus = rank_index * 4
        if file_index in (3, 4):
            bonus += 8
        return bonus
    if piece.piece_type == chess.KNIGHT:
        return center_bonus * 3 - (18 if rank_index in (0, 7) else 0)
    if piece.piece_type == chess.BISHOP:
        return center_bonus * 2 + min(rank_index, 5) * 2
    if piece.piece_type == chess.ROOK:
        return 6 if rank_index >= 6 else 0
    if piece.piece_type == chess.QUEEN:
        return center_bonus
    if piece.piece_type == chess.KING:
        material = _non_king_material(board_from_piece_map=None)
        if material <= 2200:
            return center_bonus * 2
        if lookup in (chess.G1, chess.C1, chess.B1):
            return 18
        return -int(center_rank_distance * 8)
    return 0


def _non_king_material(board_from_piece_map):
    return 2400


def _pawn_structure_score(board, color):
    pawns = board.pieces(chess.PAWN, color)
    enemy_pawns = board.pieces(chess.PAWN, not color)
    score = 0
    files = [0] * 8
    for square in pawns:
        file_index = chess.square_file(square)
        rank_index = chess.square_rank(square)
        files[file_index] += 1
        if color == chess.WHITE:
            progress = rank_index
        else:
            progress = 7 - rank_index
        score += progress * 3
        if _is_passed_pawn(square, color, enemy_pawns):
            score += 8 + progress * progress
    for file_index, count in enumerate(files):
        if count > 1:
            score -= 10 * (count - 1)
        if count:
            left = files[file_index - 1] if file_index > 0 else 0
            right = files[file_index + 1] if file_index < 7 else 0
            if left == 0 and right == 0:
                score -= 8 * count
    return score


def _is_passed_pawn(square, color, enemy_pawns):
    pawn_file = chess.square_file(square)
    pawn_rank = chess.square_rank(square)
    for enemy_square in enemy_pawns:
        enemy_file = chess.square_file(enemy_square)
        if abs(enemy_file - pawn_file) > 1:
            continue
        enemy_rank = chess.square_rank(enemy_square)
        if color == chess.WHITE and enemy_rank > pawn_rank:
            return False
        if color == chess.BLACK and enemy_rank < pawn_rank:
            return False
    return True


def _king_safety_score(board, color):
    king_square = board.king(color)
    if king_square is None:
        return -500
    score = 0
    opponent = not color
    for target in chess.SquareSet(chess.BB_KING_ATTACKS[king_square]):
        if board.is_attacked_by(opponent, target):
            score -= 5
    file_index = chess.square_file(king_square)
    rank_index = chess.square_rank(king_square)
    pawn_rank = rank_index + (1 if color == chess.WHITE else -1)
    if 0 <= pawn_rank <= 7:
        for file_delta in (-1, 0, 1):
            pawn_file = file_index + file_delta
            if 0 <= pawn_file <= 7:
                piece = board.piece_at(chess.square(pawn_file, pawn_rank))
                if piece and piece.color == color and piece.piece_type == chess.PAWN:
                    score += 7
    return score


def _hanging_piece_score(board):
    score = 0
    for square, piece in board.piece_map().items():
        if piece.piece_type == chess.KING:
            continue
        attacked = board.is_attacked_by(not piece.color, square)
        defended = board.is_attacked_by(piece.color, square)
        if attacked and not defended:
            penalty = PIECE_VALUES.get(piece.piece_type, 0) // 8
            if piece.color == chess.WHITE:
                score -= penalty
            else:
                score += penalty
    return score


def _mobility_score(board):
    turn = board.turn
    try:
        board.turn = chess.WHITE
        white_mobility = board.legal_moves.count()
        board.turn = chess.BLACK
        black_mobility = board.legal_moves.count()
    finally:
        board.turn = turn
    return 2 * (white_mobility - black_mobility)
