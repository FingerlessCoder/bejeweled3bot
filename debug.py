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

    @staticmethod
    def print_board_detailed(board: np.ndarray, confidences: np.ndarray, gem_type_map: dict):
        """Print board with full gem type name and confidence per cell.

        Args:
            board: 8x8 int array of gem IDs
            confidences: 8x8 float array of per-cell confidence
            gem_type_map: dict mapping gem_type_name -> gem_id (from BoardDetector)
        """
        # Build reverse map: gem_id -> gem_type_name
        id_to_name = {v: k for k, v in gem_type_map.items()}

        print()
        print("Detailed board state (gem_type confidence):")
        print("  " + "-" * 80)
        for row in range(board.shape[0]):
            cells = []
            for col in range(board.shape[1]):
                gem_id = board[row, col]
                name = id_to_name.get(gem_id, "unknown")
                conf = confidences[row, col]
                # Abbreviate: e.g. "red_flame" -> "R_flame", "blue_star" -> "B_star"
                if "_" in name:
                    prefix, suffix = name.split("_", 1)
                    abbr = prefix[0].upper() + "_" + suffix
                else:
                    abbr = name[:4].upper() if name != "unknown" else "?"
                cells.append(f"{abbr:>10s} {conf:.2f}")
            print(f"  row {row}: " + " | ".join(cells))
        print("  " + "-" * 80)

        # Summary counts
        print("Gem counts by type:")
        counts = {}
        for row in range(board.shape[0]):
            for col in range(board.shape[1]):
                gid = board[row, col]
                name = id_to_name.get(gid, "unknown")
                counts[name] = counts.get(name, 0) + 1
        for name in sorted(counts.keys()):
            count = counts[name]
            print(f"  {name:20s}: {count:2d}")
        print()
