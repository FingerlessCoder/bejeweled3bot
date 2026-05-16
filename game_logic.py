"""
Game logic module for Bejeweled 3 bot.
Handles move validation, match detection, and cascade simulation.
"""

import numpy as np
from typing import List, Tuple, Set
from config import (
    BOARD_WIDTH, BOARD_HEIGHT, MIN_MATCH_LENGTH,
    MAX_CASCADE_DEPTH, CASCADE_DEPTH_BONUS, IMMEDIATE_MATCH_WEIGHT,
    NORMAL_GEM_COUNT, HYPERCUBE_GEM_ID, STAR_GEM_OFFSET
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
    
    def _is_hypercube(self, gem_id: int) -> bool:
        return gem_id == HYPERCUBE_GEM_ID

    def _is_star_gem(self, gem_id: int) -> bool:
        return STAR_GEM_OFFSET <= gem_id < HYPERCUBE_GEM_ID

    def _star_base_color(self, star_id: int) -> int:
        """Return the normal gem ID (0..6) that this star matches with."""
        return star_id - STAR_GEM_OFFSET

    def _is_star_move(self, move: Tuple[Tuple[int, int], Tuple[int, int]]) -> bool:
        """Check if a move activates a star gem (star + same-color normal gem)."""
        (r1, c1), (r2, c2) = move
        if self.board is None:
            return False
        g1 = self.board[r1, c1]
        g2 = self.board[r2, c2]
        if self._is_star_gem(g1):
            return g2 == self._star_base_color(g1)
        if self._is_star_gem(g2):
            return g1 == self._star_base_color(g2)
        return False

    def _is_valid_move(self, move: Tuple[Tuple[int, int], Tuple[int, int]]) -> bool:
        """Check if a move creates at least one match (or involves hypercube/star)."""
        (r1, c1), (r2, c2) = move

        if self.board is not None:
            g1 = self.board[r1, c1] if r1 < self.board.shape[0] and c1 < self.board.shape[1] else -1
            g2 = self.board[r2, c2] if r2 < self.board.shape[0] and c2 < self.board.shape[1] else -1

            # Hypercube swaps are always valid
            if self._is_hypercube(g1) or self._is_hypercube(g2):
                return True

            # Star + same-color gem is always valid
            if self._is_star_move(move):
                return True

            # Swapping two identical gems is a board no-op — can never create new matches
            if g1 == g2:
                return False

        # Make a copy and perform the swap
        test_board = self.board.copy()
        test_board[r1, c1], test_board[r2, c2] = test_board[r2, c2], test_board[r1, c1]

        # Check if any matches are found
        matches = self._find_all_matches(test_board)
        return len(matches) > 0
    
    def _find_all_matches(self, board: np.ndarray) -> List[Tuple[int, int]]:
        """
        Find all cells that are part of a match.
        Returns list of (row, col) tuples.
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
    
    def _analyze_match_shape(self, matches: List[Tuple[int, int]]) -> str:
        """Determine what special gem a match shape would create.

        Returns 'flame', 'star', 'hypercube', or ''.
        """
        if len(matches) < 4:
            return ''

        rows = set(r for r, c in matches)
        cols = set(c for r, c in matches)

        # All in one row → horizontal chain
        if len(rows) == 1:
            count = len(cols)
            if count >= 5:
                return 'hypercube'
            if count >= 4:
                return 'flame'
            return ''

        # All in one column → vertical chain
        if len(cols) == 1:
            count = len(rows)
            if count >= 5:
                return 'hypercube'
            if count >= 4:
                return 'flame'
            return ''

        # Multiple rows AND columns → L, T, or cross = star
        # Verify it's actually a connected cross shape and not scattered
        if len(rows) >= 2 and len(cols) >= 2 and len(matches) >= 4:
            # Check for a pivot cell that has both horizontal and vertical arms
            for r, c in matches:
                h_count = sum(1 for rr, cc in matches if rr == r)
                v_count = sum(1 for rr, cc in matches if cc == c)
                if h_count >= 3 and v_count >= 2:
                    return 'star'
            # Also check: does this form a 2×2+ block (close enough to L/T)
            if len(matches) >= 4:
                return 'star'

        return ''

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
    
    def _simulate_hypercube_move(self, move, r1, c1, r2, c2, g1, g2):
        """Handle hypercube move: clears all gems of target type."""
        target_type = g2 if self._is_hypercube(g1) else g1
        if target_type < 0 or target_type >= NORMAL_GEM_COUNT:
            return 0, self.board.copy()

        test_board = self.board.copy()
        test_board[r1, c1] = -1
        test_board[r2, c2] = -1
        count_cleared = int(np.sum(test_board == target_type))
        test_board[test_board == target_type] = -1
        count_cleared += 1
        test_board = self._apply_gravity(test_board)
        final_board, cascade_score = self.simulate_cascade(test_board, depth=1)
        board_wipe_score = count_cleared * IMMEDIATE_MATCH_WEIGHT * 10
        return board_wipe_score + cascade_score + (r1 + r2) * 2, final_board

    def _simulate_star_move(self, move, r1, c1, r2, c2, g1, g2):
        """Handle star gem move: clears entire row & column of target."""
        if self._is_star_gem(g1):
            star_r, star_c = r1, c1
            target_r, target_c = r2, c2
        else:
            star_r, star_c = r2, c2
            target_r, target_c = r1, c1

        test_board = self.board.copy()
        test_board[star_r, star_c] = -1
        test_board[target_r, target_c] = -1

        for c in range(BOARD_WIDTH):
            if test_board[target_r, c] >= 0:
                test_board[target_r, c] = -1
        for r in range(BOARD_HEIGHT):
            if test_board[r, target_c] >= 0:
                test_board[r, target_c] = -1

        cleared = int(np.sum(test_board < 0)) - (0 if star_r == target_r and star_c == target_c else 0)

        test_board = self._apply_gravity(test_board)
        final_board, cascade_score = self.simulate_cascade(test_board, depth=1)
        star_score = cleared * IMMEDIATE_MATCH_WEIGHT * 5
        return star_score + cascade_score + (r1 + r2) * 2, final_board

    def _simulate_normal_move(self, move, r1, c1, r2, c2):
        """Handle normal gem swap: match-3 detection + cascade."""
        test_board = self.board.copy()
        test_board[r1, c1], test_board[r2, c2] = test_board[r2, c2], test_board[r1, c1]

        matches = self._find_all_matches(test_board)
        immediate_score = len(matches) * IMMEDIATE_MATCH_WEIGHT

        shape = self._analyze_match_shape(matches)
        shape_bonus = 0
        if shape == 'hypercube':
            shape_bonus = IMMEDIATE_MATCH_WEIGHT * 50
        elif shape == 'star':
            shape_bonus = IMMEDIATE_MATCH_WEIGHT * 30
        elif shape == 'flame':
            shape_bonus = IMMEDIATE_MATCH_WEIGHT * 15

        for row, col in matches:
            test_board[row, col] = -1

        final_board, cascade_score = self.simulate_cascade(test_board, depth=1)
        row_bonus = (r1 + r2) * 2
        return immediate_score + cascade_score + row_bonus + shape_bonus, final_board

    def simulate_move(self, move: Tuple[Tuple[int, int], Tuple[int, int]]) -> Tuple[int, np.ndarray]:
        """Simulate a move and return (total_score, board_after_cascades).
        Unlike evaluate_move, this also returns the resulting board for lookahead.
        """
        if not self._is_valid_move(move):
            return 0, self.board.copy()

        (r1, c1), (r2, c2) = move
        g1 = self.board[r1, c1]
        g2 = self.board[r2, c2]

        if self._is_hypercube(g1) or self._is_hypercube(g2):
            return self._simulate_hypercube_move(move, r1, c1, r2, c2, g1, g2)

        if self._is_star_move(move):
            return self._simulate_star_move(move, r1, c1, r2, c2, g1, g2)

        return self._simulate_normal_move(move, r1, c1, r2, c2)

    def evaluate_move(self, move: Tuple[Tuple[int, int], Tuple[int, int]]) -> int:
        """Evaluate the quality of a move. Returns total score."""
        score, _ = self.simulate_move(move)
        return score
    
    def evaluate_board_potential(self, board: np.ndarray = None) -> int:
        """Score a board position for follow-up potential.

        Rewards boards with more valid moves and near-matches
        (adjacent same-colour pairs that aren't yet a match-3).
        Used by 2-ply lookahead to prefer setups over dead boards.
        """
        if board is None:
            board = self.board

        old_board = self.board
        self.board = board
        valid_moves = self.find_valid_moves()
        self.board = old_board

        # Base: more valid moves = better setup
        move_potential = len(valid_moves) * IMMEDIATE_MATCH_WEIGHT * 2

        # Bonus: count near-matches (adjacent same-type pairs)
        near_matches = 0
        for r in range(BOARD_HEIGHT):
            for c in range(BOARD_WIDTH):
                gid = board[r, c]
                if gid < 0 or gid >= NORMAL_GEM_COUNT:
                    continue
                if c + 1 < BOARD_WIDTH and board[r, c + 1] == gid:
                    near_matches += 1
                if r + 1 < BOARD_HEIGHT and board[r + 1, c] == gid:
                    near_matches += 1

        return move_potential + near_matches * IMMEDIATE_MATCH_WEIGHT


