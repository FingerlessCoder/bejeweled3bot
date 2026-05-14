"""
Show the actual BGR values being detected in each cell.
This tells us what colors the detector is really sampling.
"""

import cv2
import numpy as np
from vision import BoardDetector
from PIL import ImageGrab
import win32gui

def show_cell_colors():
    """Show actual BGR values for each cell."""
    detector = BoardDetector()
    
    print("="*60)
    print("CELL COLOR ANALYSIS")
    print("="*60)
    print("\nCapturing board...")
    
    # Get screenshot
    screenshot_pil = ImageGrab.grab()
    img = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
    
    # Get board state
    board = detector.get_board_state()
    if board is None:
        print("[ERROR] Failed to detect board!")
        return
    
    if detector.board_region is None:
        print("[ERROR] No board region!")
        return
    
    x, y, w, h = detector.board_region
    board_img = img[y:y+int(h), x:x+int(w)]
    
    gem_names = {v: k for k, v in detector.gem_type_map.items()}
    
    print("\nCells where yellow is being misdetected as orange:")
    print("(These should help us fix the color ranges)\n")
    
    from config import BOARD_WIDTH, BOARD_HEIGHT
    
    for row in range(BOARD_HEIGHT):
        for col in range(BOARD_WIDTH):
            cell_left = col * detector.cell_width
            cell_top = row * detector.cell_height
            
            # Get average color in this cell
            x_start = max(0, int(cell_left))
            y_start = max(0, int(cell_top))
            x_end = min(board_img.shape[1], int(cell_left + detector.cell_width))
            y_end = min(board_img.shape[0], int(cell_top + detector.cell_height))
            
            cell_region = board_img[y_start:y_end, x_start:x_end]
            if cell_region.size > 0:
                avg_b = int(np.mean(cell_region[:, :, 0]))
                avg_g = int(np.mean(cell_region[:, :, 1]))
                avg_r = int(np.mean(cell_region[:, :, 2]))
                
                detected_gem_id = board[row, col]
                detected_name = gem_names.get(detected_gem_id, '?')
                
                # Mark suspect cells
                if detected_name == 'orange':  # These might actually be yellow or special
                    print(f"[{row},{col}] Detected: {detected_name:8s} | BGR({avg_b:3d},{avg_g:3d},{avg_r:3d})")

if __name__ == "__main__":
    show_cell_colors()
