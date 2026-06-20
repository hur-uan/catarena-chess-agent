import chess
import random
import time
from typing import Optional, Dict, List

class ChessAI:
    """Chess AI implementation with Minimax algorithm and alpha-beta pruning"""
    
    # Piece values for position evaluation
    PIECE_VALUES = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 0  # King value is not used in standard evaluation as it can't be captured
    }
    
    # Piece square tables for positional evaluation
    PIECE_SQUARE_TABLES = {
        chess.PAWN: [
            0,  0,  0,  0,  0,  0,  0,  0,
            5, 10, 10,-20,-20, 10, 10,  5,
            5, -5,-10,  0,  0,-10, -5,  5,
            0,  0, 20, 30, 30, 20,  0,  0,
            5,  5, 10, 25, 25, 10,  5,  5,
            10, 10, 20, 30, 30, 20, 10, 10,
            50, 50, 50, 50, 50, 50, 50, 50,
            0, 0, 0, 0, 0, 0, 0, 0
        ],
        chess.KNIGHT: [
            -50,-40,-30,-30,-30,-30,-40,-50,
            -40,-20,  0,  5,  5,  0,-20,-40,
            -30,  5, 10, 15, 15, 10,  5,-30,
            -30,  0, 15, 20, 20, 15,  0,-30,
            -30,  5, 15, 20, 20, 15,  5,-30,
            -30,  0, 10, 15, 15, 10,  0,-30,
            -40,-20,  0,  0,  0,  0,-20,-40,
            -50,-40,-30,-30,-30,-30,-40,-50
        ],
        chess.BISHOP: [
            -20,-10,-10,-10,-10,-10,-10,-20,
            -10,  5,  0,  0,  0,  0,  5,-10,
            -10, 10, 10, 10, 10, 10, 10,-10,
            -10,  0, 10, 10, 10, 10,  0,-10,
            -10,  5,  5, 10, 10,  5,  5,-10,
            -10,  0,  5, 10, 10,  5,  0,-10,
            -10,  0,  0,  0,  0,  0,  0,-10,
            -20,-10,-10,-10,-10,-10,-10,-20
        ],
        chess.ROOK: [
            0,  0,  0,  0,  0,  0,  0,  0,
            5, 10, 10, 10, 10, 10, 10,  5,
            -5,  0,  0,  0,  0,  0,  0, -5,
            -5,  0,  0,  0,  0,  0,  0, -5,
            -5,  0,  0,  0,  0,  0,  0, -5,
            -5,  0,  0,  0,  0,  0,  0, -5,
            -5,  0,  0,  0,  0,  0,  0, -5,
            0,  0,  0, 5, 5,  0,  0,  0
        ],
        chess.QUEEN: [
            -20,-10,-10, -5, -5,-10,-10,-20,
            -10,  0,  0,  0,  0,  0,  0,-10,
            -10,  0,  5,  5,  5,  5,  0,-10,
            -5,  0,  5,  5,  5,  5,  0, -5,
            0,  0,  5,  5,  5,  5,  0, -5,
            -10,  5,  5,  5,  5,  5,  0,-10,
            -10, 0,  5,  0,  0,  0,  0,-10,
            -20,-10,-10, -5, -5,-10,-10,-20
        ],
        chess.KING: [
            -30,-40,-40,-50,-50,-40,-40,-30,
            -30,-40,-40,-50,-50,-40,-40,-30,
            -30,-40,-40,-50,-50,-40,-40,-30,
            -30,-40,-40,-50,-50,-40,-40,-30,
            -20,-30,-30,-40,-40,-30,-30,-20,
            -10,-20,-20,-20,-20,-20,-20,-10,
            20, 20,  0,0,0,0,20,20,
            20,30,10,0,0,10,30,20
        ]
    }
    
    def __init__(self, depth: int = 3):
        """
        Initialize ChessAI with specified search depth
        
        Args:
            depth: Search depth for Minimax algorithm
        """
        self.search_depth = depth
        
    def evaluate_position(self, board: chess.Board) -> float:
        """
        Evaluate the current position from the perspective of the current player
        
        Args:
            board: Current chess board state
            
        Returns:
            Evaluation score (positive for advantage to current player, negative otherwise)
        """
        if board.is_checkmate():
            # If current player is in checkmate, this is a losing position
            return -float('inf')
        if board.is_stalemate() or board.is_insufficient_material():
            # Draw positions have neutral evaluation
            return 0
        
        score = 0
        
        # Evaluate material balance
        for piece_type in self.PIECE_VALUES:
            # Count pieces for both sides
            white_count = len(board.pieces(piece_type, chess.WHITE))
            black_count = len(board.pieces(piece_type, chess.BLACK))
            
            # Add material value (positive for white, negative for black)
            piece_value = self.PIECE_VALUES[piece_type]
            score += (white_count - black_count) * piece_value
        
        # Evaluate piece positions
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                # Get the piece square table value
                # Flip the square for black pieces
                adjusted_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
                piece_value = self.PIECE_SQUARE_TABLES[piece.piece_type][adjusted_square] / 10
                
                # Add to score (positive for white, negative for black)
                if piece.color == chess.WHITE:
                    score += piece_value
                else:
                    score -= piece_value
        
        # Adjust score based on current player
        if board.turn == chess.BLACK:
            score = -score
            
        return score
    
    def minimax(self, board: chess.Board, depth: int, alpha: float, beta: float, maximizing_player: bool) -> float:
        """
        Minimax algorithm with alpha-beta pruning
        
        Args:
            board: Current board state
            depth: Current search depth
            alpha: Alpha value for pruning
            beta: Beta value for pruning
            maximizing_player: Whether the current player is maximizing
            
        Returns:
            Evaluation score for the position
        """
        if depth == 0 or board.is_game_over():
            return self.evaluate_position(board)
        
        if maximizing_player:
            max_eval = -float('inf')
            for move in board.legal_moves:
                board.push(move)
                eval_score = self.minimax(board, depth - 1, alpha, beta, False)
                board.pop()
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break  # Beta cutoff
            return max_eval
        else:
            min_eval = float('inf')
            for move in board.legal_moves:
                board.push(move)
                eval_score = self.minimax(board, depth - 1, alpha, beta, True)
                board.pop()
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break  # Alpha cutoff
            return min_eval
    
    def get_best_move_minimax(self, board: chess.Board) -> Optional[chess.Move]:
        """
        Get best move using Minimax algorithm with alpha-beta pruning
        
        Args:
            board: Current board state
            
        Returns:
            Best move found or None if no moves available
        """
        best_move = None
        best_score = -float('inf')
        alpha = -float('inf')
        beta = float('inf')
        
        # Order moves to improve alpha-beta pruning efficiency
        moves = list(board.legal_moves)
        
        # Try to find a winning move immediately
        for move in moves:
            board.push(move)
            if board.is_checkmate():
                board.pop()
                return move
            board.pop()
        
        # Search each move
        for move in moves:
            board.push(move)
            current_score = self.minimax(board, self.search_depth - 1, alpha, beta, False)
            board.pop()
            
            if current_score > best_score:
                best_score = current_score
                best_move = move
                
            alpha = max(alpha, current_score)
            
        return best_move
    
    def get_best_move(self, board: chess.Board, algorithm: str = "minimax") -> Optional[chess.Move]:
        """
        Get best move using specified algorithm
        
        Args:
            board: Current board state
            algorithm: Algorithm to use ("simple" or "minimax")
            
        Returns:
            Best move found or None if no moves available
        """
        if not board.legal_moves:
            return None
            
        if algorithm == "minimax":
            return self.get_best_move_minimax(board)
        else:  # Default to simple random move
            return random.choice(list(board.legal_moves))
    
    def get_legal_moves(self, board: chess.Board) -> List[Dict]:
        """
        Get legal moves for current position
        
        Args:
            board: Current board state
            
        Returns:
            List of legal moves in dictionary format
        """
        legal_moves = []
        for move in board.legal_moves:
            move_dict = {
                "uci": move.uci(),
                "san": board.san(move),
                "from_square": chess.square_name(move.from_square),
                "to_square": chess.square_name(move.to_square),
                "promotion": chess.piece_name(move.promotion) if move.promotion else None
            }
            legal_moves.append(move_dict)
        return legal_moves