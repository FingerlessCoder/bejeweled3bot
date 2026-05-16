"""
AI Player module for Bejeweled 3 bot.
Handles move selection strategy.
"""

import numpy as np
from typing import Tuple, Optional
from game_logic import GameLogic


class AIPlayer:
    """AI player that selects moves using 2-ply lookahead."""

    LOOKAHEAD_DISCOUNT = 0.4  # how much to weight the follow-up move

    def __init__(self, board: np.ndarray = None):
        """Initialize with optional starting board."""
        self.logic = GameLogic(board)
        self.move_history = []
        self.score_history = []

    def get_ranked_moves(self, board: np.ndarray, top_n: int = 10) -> list:
        """
        Get top N moves ranked by 2-ply score.
        For each candidate:
          1. Simulate the move + cascades
          2. Score the resulting board position (follow-up potential)
          3. Total = immediate_score + board_potential * discount

        Returns list of (move, score) tuples sorted by score descending.
        """
        self.logic.set_board(board)
        valid_moves = self.logic.find_valid_moves()

        if not valid_moves:
            return []

        move_scores = []
        for move in valid_moves:
            score, final_board = self.logic.simulate_move(move)
            followup = self.logic.evaluate_board_potential(final_board)
            total = score + int(followup * AIPlayer.LOOKAHEAD_DISCOUNT)
            move_scores.append((move, total))

        move_scores.sort(key=lambda x: x[1], reverse=True)
        return move_scores[:top_n]
    
    def track_move(self, board: np.ndarray,
                    move: Tuple[Tuple[int, int], Tuple[int, int]]) -> None:
        """No-op base — only PokerAIPlayer implements hand tracking."""
        pass

    def select_best_move(self, board: np.ndarray) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """
        Analyze board and return the best move.
        Uses greedy strategy: pick move with highest cascade score.
        
        Returns ((row1, col1), (row2, col2)) or None if no valid moves.
        """
        ranked = self.get_ranked_moves(board, top_n=1)
        if not ranked:
            print("[AI] No valid moves available")
            return None
        
        best_move, best_score = ranked[0]
        
        # Log selection
        if best_move:
            (r1, c1), (r2, c2) = best_move
            print(f"[AI] Selected move: ({r1},{c1}) <-> ({r2},{c2}), Score: {best_score}")
            self.move_history.append(best_move)
            self.score_history.append(best_score)
        
        return best_move
    
    def get_move_stats(self) -> dict:
        """Return statistics about moves made."""
        if not self.score_history:
            return {'total_moves': 0, 'avg_score': 0, 'total_score': 0}
        
        return {
            'total_moves': len(self.move_history),
            'avg_score': sum(self.score_history) / len(self.score_history),
            'total_score': sum(self.score_history),
            'best_score': max(self.score_history),
            'worst_score': min(self.score_history),
        }
    
    def reset(self):
        """Reset move history."""
        self.move_history = []
        self.score_history = []
