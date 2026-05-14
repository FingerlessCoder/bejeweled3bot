"""
Game logic module for Bejeweled 3 bot.
Handles move validation, match detection, and cascade simulation.
"""

import numpy as np
from typing import List, Tuple, Set
from config import (
    BOARD_WIDTH, BOARD_HEIGHT, MIN_MATCH_LENGTH,
    MAX_CASCADE_DEPTH, CASCADE_DEPTH_BONUS, IMMEDIATE_MATCH_WEIGHT
)


class GameLogic:
    """Handles game rules and board state simulation."""
    
    def __init__(self, board: np.ndarray = None):
        """
        Initialize with initial board state.
        board: 2D numpy array where each cell is gem type ID (-1 for empty).
        """
        self.board = board.copy() if board is not None else None
    
    def set_board(self, board: np.ndarray):
        """Set the current board state."""
        self.board = board.copy()
    
    def find_valid_moves(self) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """
        Find all valid moves (swaps that result in a match).
        Returns list of tuples: ((row1, col1), (row2, col2))
        """
        if self.board is None:
            return []
        
        valid_moves = []
        
        # Try all adjacent swaps
        for row in range(BOARD_HEIGHT):
            for col in range(BOARD_WIDTH):
                # Try swapping right
                if col < BOARD_WIDTH - 1:
                    move = ((row, col), (row, col + 1))
                    if self._is_valid_move(move):
                        valid_moves.append(move)
                
                # Try swapping down
                if row < BOARD_HEIGHT - 1:
                    move = ((row, col), (row + 1, col))
                    if self._is_valid_move(move):
                        valid_moves.append(move)
        
        return valid_moves
    
    def _is_valid_move(self, move: Tuple[Tuple[int, int], Tuple[int, int]]) -> bool:
        """Check if a move creates at least one match."""
        (r1, c1), (r2, c2) = move
        
        # Make a copy and perform the swap
        test_board = self.board.copy()
        test_board[r1, c1], test_board[r2, c2] = test_board[r2, c2], test_board[r1, c1]
        
        # Check if any matches are found
        matches = self._find_all_matches(test_board)
        return len(matches) > 0
    
    def _find_all_matches(self, board: np.ndarray) -> List[Tuple[int, int]]:
        """
        Find all cells that are part of a match.
        Returns set of (row, col) tuples.
        """
        matched = set()
        
        # Check horizontal matches
        for row in range(BOARD_HEIGHT):
            col = 0
            while col < BOARD_WIDTH:
                if board[row, col] < 0:  # Skip empty cells
                    col += 1
                    continue
                
                # Count consecutive gems of same type
                match_start = col
                while col < BOARD_WIDTH and board[row, col] == board[row, match_start]:
                    col += 1
                
                match_length = col - match_start
                if match_length >= MIN_MATCH_LENGTH:
                    for c in range(match_start, col):
                        matched.add((row, c))
        
        # Check vertical matches
        for col in range(BOARD_WIDTH):
            row = 0
            while row < BOARD_HEIGHT:
                if board[row, col] < 0:  # Skip empty cells
                    row += 1
                    continue
                
                # Count consecutive gems of same type
                match_start = row
                while row < BOARD_HEIGHT and board[row, col] == board[match_start, col]:
                    row += 1
                
                match_length = row - match_start
                if match_length >= MIN_MATCH_LENGTH:
                    for r in range(match_start, row):
                        matched.add((r, col))
        
        return list(matched)
    
    def simulate_cascade(self, board: np.ndarray = None, depth: int = 0) -> Tuple[np.ndarray, int]:
        """
        Simulate gravity and cascading matches until no more matches exist.
        Returns (final_board, total_score).
        """
        if board is None:
            board = self.board.copy()
        else:
            board = board.copy()
        
        if depth > MAX_CASCADE_DEPTH:
            return board, 0
        
        # Apply gravity: shift gems down
        board = self._apply_gravity(board)
        
        # Find matches
        matches = self._find_all_matches(board)
        
        if not matches:
            return board, 0  # No more matches
        
        # Score this cascade level
        score = len(matches) * IMMEDIATE_MATCH_WEIGHT
        
        # Remove matched gems
        for row, col in matches:
            board[row, col] = -1
        
        # Recursively cascade
        final_board, cascade_score = self.simulate_cascade(board, depth + 1)
        score += cascade_score + CASCADE_DEPTH_BONUS if depth > 0 else cascade_score
        
        return final_board, score
    
    def _apply_gravity(self, board: np.ndarray) -> np.ndarray:
        """
        Apply gravity to board: shift all gems down to fill empty spaces.
        """
        board = board.copy()
        
        for col in range(BOARD_WIDTH):
            # Extract column and remove empty spaces
            column = board[:, col]
            non_empty = column[column >= 0]
            empty_count = BOARD_HEIGHT - len(non_empty)
            
            # Rebuild column with empty spaces at top
            new_column = np.full(BOARD_HEIGHT, -1, dtype=np.int8)
            new_column[empty_count:] = non_empty
            board[:, col] = new_column
        
        return board
    
    def evaluate_move(self, move: Tuple[Tuple[int, int], Tuple[int, int]]) -> int:
        """
        Evaluate the quality of a move by simulating it and the cascade.
        Returns total score.
        """
        if not self._is_valid_move(move):
            return 0
        
        # Perform the move
        (r1, c1), (r2, c2) = move
        test_board = self.board.copy()
        test_board[r1, c1], test_board[r2, c2] = test_board[r2, c2], test_board[r1, c1]
        
        # Find immediate matches
        matches = self._find_all_matches(test_board)
        immediate_score = len(matches) * IMMEDIATE_MATCH_WEIGHT
        
        # Remove matched gems
        for row, col in matches:
            test_board[row, col] = -1
        
        # Simulate cascade
        final_board, cascade_score = self.simulate_cascade(test_board, depth=1)

        # ADDED: Bottom-up priority bonus
        # The lower the gems are on the board (higher row index), the better
        # the cascade potential. Give a small bonus proportional to the
        # involved rows to prefer bottom-up moves.
        row_bonus = (r1 + r2) * 2

        return immediate_score + cascade_score + row_bonus
    
    def get_gem_type_name(self, gem_id: int) -> str:
        """Convert gem ID back to name."""
        id_to_name = {v: k for k, v in {
            'red': 0, 'orange': 1, 'yellow': 2, 'green': 3,
            'blue': 4, 'purple': 5, 'pink': 6
        }.items()}
        return id_to_name.get(gem_id, 'unknown')


def evaluate_move_quality(board: np.ndarray, move: Tuple[Tuple[int, int], Tuple[int, int]]) -> int:
    """Convenience function to evaluate a move."""
    logic = GameLogic(board)
    return logic.evaluate_move(move)
