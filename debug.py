"""
Debug utilities for Bejeweled 3 bot.
Provides logging and visualization helpers.
"""

import numpy as np
import os
import json
from datetime import datetime
from config import LOG_FILE, GEM_COLORS, DEBUG_MODE


class BotLogger:
    """Handles logging of bot activity."""
    
    def __init__(self, log_file: str = LOG_FILE):
        self.log_file = log_file
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_log = []
        
        # Create log entry
        with open(self.log_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Session started: {self.session_id}\n")
            f.write(f"{'='*60}\n")
    
    def log_move(self, move_number: int, move: tuple, score: int, board_state: np.ndarray):
        """Log a move and its result."""
        (r1, c1), (r2, c2) = move
        log_entry = {
            'move_number': move_number,
            'move': f"({r1},{c1})-({r2},{c2})",
            'score': score,
            'timestamp': datetime.now().isoformat()
        }
        
        self.session_log.append(log_entry)
        
        with open(self.log_file, 'a') as f:
            f.write(f"Move {move_number}: ({r1},{c1}) <-> ({r2},{c2}), Score: {score}\n")
    
    def log_game_end(self, total_moves: int, total_score: int, stats: dict):
        """Log game completion."""
        with open(self.log_file, 'a') as f:
            f.write(f"\nGame ended after {total_moves} moves\n")
            f.write(f"Total score contribution: {total_score}\n")
            f.write(f"Stats: {json.dumps(stats, indent=2)}\n")
            f.write(f"{'='*60}\n")


class BoardVisualizer:
    """Converts board state to human-readable format."""
    
    # Map gem IDs to symbols
    GEM_SYMBOLS = {
        -1: '.',
        0: 'R',   # Red
        1: 'O',   # Orange
        2: 'Y',   # Yellow
        3: 'G',   # Green
        4: 'B',   # Blue
        5: 'P',   # Purple
        6: 'K',   # pinK
    }
    
    @staticmethod
    def board_to_string(board: np.ndarray) -> str:
        """Convert board to ASCII visualization."""
        if board is None:
            return "Board not initialized"
        
        lines = []
        lines.append("  0 1 2 3 4 5 6 7")
        
        for row in range(len(board)):
            line = f"{row} "
            for col in range(len(board[0])):
                gem_id = board[row, col]
                symbol = BoardVisualizer.GEM_SYMBOLS.get(gem_id, '?')
                line += symbol + " "
            lines.append(line)
        
        return "\n".join(lines)
    
    @staticmethod
    def print_board(board: np.ndarray):
        """Print board visualization to console."""
        print(BoardVisualizer.board_to_string(board))
    
    @staticmethod
    def board_to_image(board: np.ndarray, cell_size: int = 40) -> 'PIL.Image':
        """Convert board to PIL Image for visualization."""
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            print("[WARNING] PIL not available for image generation")
            return None
        
        # Create image
        img_size = 8 * cell_size
        img = Image.new('RGB', (img_size, img_size), color='white')
        draw = ImageDraw.Draw(img)
        
        # Color mapping
        color_map = {
            -1: (200, 200, 200),  # Empty - gray
            0: (255, 0, 0),       # Red
            1: (255, 165, 0),     # Orange
            2: (255, 255, 0),     # Yellow
            3: (0, 128, 0),       # Green
            4: (0, 0, 255),       # Blue
            5: (128, 0, 128),     # Purple
            6: (255, 192, 203),   # Pink
        }
        
        # Draw cells
        for row in range(8):
            for col in range(8):
                gem_id = board[row, col]
                color = color_map.get(gem_id, (100, 100, 100))
                
                x0 = col * cell_size
                y0 = row * cell_size
                x1 = x0 + cell_size
                y1 = y0 + cell_size
                
                draw.rectangle([x0, y0, x1, y1], fill=color, outline='black')
        
        return img


def print_debug_info(board: np.ndarray, valid_moves: list, selected_move: tuple = None):
    """Print debug information about current game state."""
    if not DEBUG_MODE:
        return
    
    print("\n" + "="*50)
    print("BOARD STATE")
    print("="*50)
    BoardVisualizer.print_board(board)
    
    print(f"\nValid moves: {len(valid_moves)}")
    if valid_moves:
        for i, move in enumerate(valid_moves[:5]):  # Show first 5
            (r1, c1), (r2, c2) = move
            print(f"  {i+1}. ({r1},{c1}) <-> ({r2},{c2})")
        if len(valid_moves) > 5:
            print(f"  ... and {len(valid_moves) - 5} more")
    
    if selected_move:
        (r1, c1), (r2, c2) = selected_move
        print(f"\nSelected: ({r1},{c1}) <-> ({r2},{c2})")
    
    print("="*50 + "\n")
