"""
Debug vision tool - shows exactly what gems the detector sees on the board.
"""

import cv2
import numpy as np
from vision import BoardDetector
import time
from config import BOARD_WIDTH, BOARD_HEIGHT

def display_board_detection():
    """Capture and display what the detector sees."""
    detector = BoardDetector()
    
    print("="*60)
    print("VISION DEBUG TOOL")
    print("="*60)
    print("\nCapturing board state...")
    
    # Get board
    board = detector.get_board_state()
    if board is None:
        print("[ERROR] Failed to detect board!")
        return
    
    # Get gem type names
    gem_names = {v: k for k, v in detector.gem_type_map.items()}
    
    print("\n[DETECTED BOARD STATE]")
    print("Rows (top to bottom), Columns (left to right)\n")
    
    # Print board with gem names
    print("    ", end="")
    for col in range(BOARD_WIDTH):
        print(f"C{col:d} ", end="")
    print()
    
    for row in range(BOARD_HEIGHT):
        print(f"R{row} ", end="")
        for col in range(BOARD_WIDTH):
            gem_id = board[row, col]
            if gem_id >= 0:
                gem_name = gem_names.get(gem_id, '?')
                gem_char = gem_name[:1].upper()
            else:
                gem_char = '?'
            print(f" {gem_char:1} ", end="")
        print()
    
    print("\nGem Key:")
    for gem_id in range(len(gem_names)):
        gem_name = gem_names.get(gem_id, 'unknown')
        print(f"  {gem_name[:1].upper()} = {gem_name}")
    
    print(f"\nBoard coverage: {detector.last_coverage*100:.1f}%")
    print(f"Board region: {detector.board_region}")
    print(f"Cell dimensions: {detector.cell_width:.1f}x{detector.cell_height:.1f} pixels")
    
    # Ask to display debug image
    print("\n" + "="*60)
    print("The debug screenshot was saved to debug_output/")
    print("You can open it to see the grid overlay with gem labels.")
    print("="*60)

if __name__ == "__main__":
    display_board_detection()
