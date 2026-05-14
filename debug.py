"""
Debug utilities for Bejeweled 3 bot.
Provides logging and visualization helpers.
"""

import numpy as np
import json
from datetime import datetime
from config import LOG_FILE


class BotLogger:
    """Handles logging of bot activity."""

    def __init__(self, log_file: str = LOG_FILE):
        self.log_file = log_file
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_log = []

        # Create log entry
        with open(self.log_file, "a") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"Session started: {self.session_id}\n")
            f.write(f"{'=' * 60}\n")

    def log_move(
        self, move_number: int, move: tuple, score: int, board_state: np.ndarray
    ):
        """Log a move and its result."""
        (r1, c1), (r2, c2) = move
        log_entry = {
            "move_number": move_number,
            "move": f"({r1},{c1})-({r2},{c2})",
            "score": score,
            "timestamp": datetime.now().isoformat(),
        }

        self.session_log.append(log_entry)

        with open(self.log_file, "a") as f:
            f.write(
                f"Move {move_number}: ({r1},{c1}) <-> ({r2},{c2}), Score: {score}\n"
            )

    def log_game_end(self, total_moves: int, total_score: int, stats: dict):
        """Log game completion."""
        with open(self.log_file, "a") as f:
            f.write(f"\nGame ended after {total_moves} moves\n")
            f.write(f"Total score contribution: {total_score}\n")
            f.write(f"Stats: {json.dumps(stats, indent=2)}\n")
            f.write(f"{'=' * 60}\n")


class BoardVisualizer:
    """Converts board state to human-readable format."""

    GEM_SYMBOLS = {
        -1: ".",
        0: "R",
        1: "O",
        2: "Y",
        3: "G",
        4: "B",
        5: "P",
        6: "W",
    }

    @staticmethod
    def board_to_string(board: np.ndarray) -> str:
        """Convert board to ASCII visualization."""
        if board is None:
            return "Board not initialized"

        gem_names = {
            0: "R",
            1: "O",
            2: "Y",
            3: "G",
            4: "B",
            5: "P",
            6: "W",
            7: "f",
            8: "f",
            9: "f",
            10: "f",
            11: "f",
            12: "f",
            13: "f",
            14: "s",
            15: "s",
            16: "s",
            17: "s",
            18: "s",
            19: "s",
            20: "s",
            21: "H",
        }

        lines = []
        lines.append("  0 1 2 3 4 5 6 7")

        for row in range(len(board)):
            line = f"{row} "
            for col in range(len(board[0])):
                gem_id = board[row, col]
                symbol = gem_names.get(gem_id, "?")
                line += symbol + " "
            lines.append(line)

        return "\n".join(lines)

    @staticmethod
    def print_board(board: np.ndarray):
        """Print board visualization to console."""
        print(BoardVisualizer.board_to_string(board))
