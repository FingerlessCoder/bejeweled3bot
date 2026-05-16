#!/usr/bin/env python3
"""
Quick test script to debug board detection.

Usage:
    1. Open Bejeweled 3 game (any resolution)
    2. Run: python test_detection.py
    3. Click on the Bejeweled game window when prompted
    
This will:
1. Auto-detect the board region
2. Detect gem colors
3. Show detection coverage percentage
4. Save debug screenshot
"""

import sys
import argparse
from vision import BoardDetector, WindowManager
from config import DEBUG_OUTPUT_DIR
import time

def test_detection(calibrate: bool = False):
    """Test board detection and save debug output."""
    
    print("=" * 60)
    print("BEJEWELED 3 BOT - DETECTION TEST")
    print("=" * 60)
    
    # Setup window
    print("\n[STEP 1] Setting up game window...")
    print("[INFO] Game can be any resolution: 800x600, 1024x768, 1920x1200, etc.")
    print("[INFO] You have 5 seconds to CLICK on the Bejeweled game window...")
    print()
    
    if not WindowManager.setup_window():
        print("[ERROR] Failed to focus game window!")
        print("\n[HELP] Did you click on the Bejeweled game window?")
        return False
    
    print("[OK] Game window focused!")
    time.sleep(1)
    
    # Create detector
    print("\n[STEP 2] Initializing board detector...")
    detector = BoardDetector()
    print("[OK] Detector initialized!")

    if calibrate:
        print("\n[STEP 3] Starting manual board calibration...")
        if not detector.calibrate_board_region():
            print("[ERROR] Calibration was cancelled or failed.")
            return False
        print("[OK] Calibration saved!")
        time.sleep(1)
    
    # Capture and detect
    print("\n[STEP 4] Capturing screenshot and detecting board...")
    board = detector.get_board_state()
    
    if board is None:
        print("[ERROR] Board detection FAILED!")
        print("\nPossible issues:")
        print("  - Game window not visible")
        print("  - Board not properly visible in screenshot")
        print("  - Gem colors don't match RGB ranges in config.py")
        return False
    
    print("[OK] Board detected successfully!")
    
    # Display board state
    print("\n[STEP 5] Board state (gem type IDs):")
    print(board)
    
    print("\nGem color mappings:")
    for color, gem_id in detector.gem_type_map.items():
        print(f"  {gem_id}: {color}")
    
    # Check for valid board
    valid_count = (board >= 0).sum()
    total_cells = board.size
    coverage = (valid_count / total_cells) * 100
    
    print(f"\nDetection coverage: {valid_count}/{total_cells} cells ({coverage:.1f}%)")
    print(f"Cell dimensions: {detector.cell_width:.2f} x {detector.cell_height:.2f} pixels")
    
    if coverage < 30:
        print("\n[ERROR] VERY LOW detection coverage!")
        print("  Possible causes:")
        print("  - Wrong window was captured")
        print("  - Board not fully visible in screenshot")
        print("  - RGB color ranges don't match your game")
        print("\n  Next steps:")
        print("  1. Check debug screenshot: debug_output/board_debug_*.png")
        print("  2. Verify game board is visible and properly positioned")
        print("  3. If board is visible but gems not detected:")
        print("     - Adjust RGB ranges in config.py")
        print("     - Use image editor to sample actual gem RGB values")
    elif coverage < 70:
        print("\n[WARNING] Low-to-moderate detection coverage")
        print("  - Some gems not being detected")
        print("  - Bot may still work, but accuracy affected")
        print("  - Adjust RGB ranges in config.py for better results")
    else:
        print("\n[SUCCESS] ✅ Excellent detection coverage!")
        print("  Bot should work very well with this configuration")
    
    print(f"\n[OK] Debug screenshot saved to: {DEBUG_OUTPUT_DIR}/board_debug_*.png")
    
    return coverage >= 30


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Bejeweled 3 board detection test")
    parser.add_argument("--calibrate", action="store_true", help="Open a snipping-tool-style board calibration overlay")
    args = parser.parse_args()

    success = test_detection(calibrate=args.calibrate)
    sys.exit(0 if success else 1)
