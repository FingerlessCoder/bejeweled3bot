"""
Capture board state before and after a move to diagnose if game is responding.
"""

import time
from vision import BoardDetector
from config import BOARD_WIDTH, BOARD_HEIGHT

def compare_board_states():
    """Capture before/after to see if game updates after a move."""
    detector = BoardDetector()
    
    print("="*60)
    print("BEFORE/AFTER MOVE COMPARISON")
    print("="*60)
    
    # Capture BEFORE
    print("\n[1/3] Capturing BEFORE board state...")
    time.sleep(1)
    board_before = detector.get_board_state()
    if board_before is None:
        print("[ERROR] Failed to detect board!")
        return
    
    gem_names = {v: k for k, v in detector.gem_type_map.items()}
    
    print("\n[BEFORE] Board state:")
    print_board_visual(board_before, gem_names)
    
    # Wait for user to make manual move or bot makes one
    print("\n[2/3] MAKE A MOVE (manually click and drag in game, or wait for bot to move)")
    print("      Waiting 3 seconds...")
    time.sleep(3)
    
    # Capture AFTER
    print("\n[3/3] Capturing AFTER board state...")
    time.sleep(1)
    board_after = detector.get_board_state()
    if board_after is None:
        print("[ERROR] Failed to detect board after move!")
        return
    
    print("\n[AFTER] Board state:")
    print_board_visual(board_after, gem_names)
    
    # Compare
    print("\n" + "="*60)
    print("COMPARISON")
    print("="*60)
    
    changed_cells = 0
    for row in range(BOARD_HEIGHT):
        for col in range(BOARD_WIDTH):
            if board_before[row, col] != board_after[row, col]:
                changed_cells += 1
                before_name = gem_names.get(board_before[row, col], 'unknown')
                after_name = gem_names.get(board_after[row, col], 'unknown')
                print(f"  [{row},{col}] {before_name} → {after_name}")
    
    if changed_cells == 0:
        print("\n⚠️  NO CHANGES DETECTED between before and after!")
        print("   This means either:")
        print("   1. The game didn't respond to the move")
        print("   2. The move is being detected the same way")
        print("   3. The cascade animation hasn't completed yet")
    else:
        print(f"\n✓ Board changed in {changed_cells} cells")

def print_board_visual(board, gem_names):
    """Pretty-print a board state."""
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

if __name__ == "__main__":
    compare_board_states()
