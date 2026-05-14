"""
Quick recalibration tool for Yellow and Orange only.
"""

import cv2
import numpy as np
import json
import os
import time
from PIL import ImageGrab
from config import GEM_COLORS
from typing import Optional, Tuple
import win32gui

class QuickCalibrator:
    """Recalibrate specific gem colors."""

    COLOR_REFERENCE_FILE = "color_reference.json"
    
    def __init__(self):
        self.color_samples = {}
        
    def _find_game_window(self) -> Optional[int]:
        """Find Bejeweled window."""
        handles = []
        def _collect(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if "Bejeweled" in title:
                handles.append(hwnd)
        try:
            win32gui.EnumWindows(_collect, None)
        except:
            pass
        return handles[0] if handles else None

    def _extract_color(self, x1: int, y1: int, x2: int, y2: int) -> Optional[Tuple[int, int, int]]:
        """Extract average BGR from clicked region."""
        screenshot_pil = ImageGrab.grab()
        img = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
        
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        if x2 <= x1 or y2 <= y1:
            return None
        
        region = img[y1:y2, x1:x2]
        if region.size == 0:
            return None
        
        avg_b = int(np.mean(region[:, :, 0]))
        avg_g = int(np.mean(region[:, :, 1]))
        avg_r = int(np.mean(region[:, :, 2]))
        
        return (avg_b, avg_g, avg_r)

    def recalibrate_yellow_orange(self):
        """Recalibrate yellow and orange only."""
        print("\n" + "="*60)
        print("YELLOW & ORANGE RECALIBRATION")
        print("="*60)
        print("\nWe need to fix the Yellow/Orange confusion.")
        print("You'll click on a few YELLOW gems and ORANGE gems.\n")
        
        hwnd = self._find_game_window()
        if hwnd is None:
            print("[ERROR] Bejeweled window not found.")
            return False
        
        try:
            win32gui.SetForegroundWindow(hwnd)
        except:
            pass
        
        time.sleep(1)
        
        # Load existing color reference
        color_ref = {}
        if os.path.exists(self.COLOR_REFERENCE_FILE):
            try:
                with open(self.COLOR_REFERENCE_FILE, "r") as f:
                    color_ref = json.load(f)
            except:
                pass
        
        gems_to_fix = ['yellow', 'orange']
        
        for gem_type in gems_to_fix:
            print(f"\n--- Calibrating {gem_type.upper()} ---")
            print(f"Click on 3-4 {gem_type} gems in the game window.")
            print(f"Press ENTER to continue when done.\n")
            
            self.color_samples[gem_type] = []
            sample_count = 0
            
            screenshot_pil = ImageGrab.grab()
            img = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
            
            window_name = f"Calibrate {gem_type} - Drag boxes around gems, press S to save each"
            state = {
                "selecting": False,
                "start": None,
                "end": None,
            }
            
            def _on_mouse(event, x, y, _flags, _param):
                if event == cv2.EVENT_LBUTTONDOWN:
                    state["selecting"] = True
                    state["start"] = (x, y)
                    state["end"] = (x, y)
                elif event == cv2.EVENT_MOUSEMOVE and state["selecting"]:
                    state["end"] = (x, y)
                elif event == cv2.EVENT_LBUTTONUP:
                    state["selecting"] = False
            
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.setMouseCallback(window_name, _on_mouse)
            
            try:
                while True:
                    canvas = img.copy()
                    
                    if state["start"] is not None and state["end"] is not None:
                        cv2.rectangle(canvas, state["start"], state["end"], (0, 255, 0), 2)
                    
                    text = f"{gem_type.upper()} - Samples: {sample_count} | Drag gem, press S to save or ENTER to skip"
                    cv2.putText(canvas, text, (20, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    
                    cv2.imshow(window_name, canvas)
                    key = cv2.waitKey(20) & 0xFF
                    
                    # S: save sample
                    if key == ord('s') and state["start"] is not None and state["end"] is not None:
                        x1, y1 = state["start"]
                        x2, y2 = state["end"]
                        color = self._extract_color(x1, y1, x2, y2)
                        
                        if color:
                            self.color_samples[gem_type].append(color)
                            sample_count += 1
                            print(f"  Sample {sample_count}: BGR{color}")
                            state["start"] = None
                            state["end"] = None
                        else:
                            print("  Invalid selection")
                    
                    # ENTER: done with this gem
                    elif key == 13:
                        break
            
            finally:
                cv2.destroyWindow(window_name)
        
        # Update color reference with new samples
        print("\n" + "="*60)
        print("UPDATING COLOR REFERENCE")
        print("="*60)
        
        for gem_type in gems_to_fix:
            if gem_type not in self.color_samples or not self.color_samples[gem_type]:
                print(f"\n[SKIP] No samples for {gem_type}")
                continue
            
            samples = self.color_samples[gem_type]
            samples_arr = np.array(samples, dtype=np.float32)
            avg_bgr = np.mean(samples_arr, axis=0)
            min_bgr = np.min(samples_arr, axis=0)
            max_bgr = np.max(samples_arr, axis=0)
            
            center = avg_bgr
            range_b = (max_bgr[0] - min_bgr[0]) / 2.0 + 15
            range_g = (max_bgr[1] - min_bgr[1]) / 2.0 + 15
            range_r = (max_bgr[2] - min_bgr[2]) / 2.0 + 15
            
            expanded_min = [
                max(0, int(center[0] - range_b)),
                max(0, int(center[1] - range_g)),
                max(0, int(center[2] - range_r)),
            ]
            expanded_max = [
                min(255, int(center[0] + range_b)),
                min(255, int(center[1] + range_g)),
                min(255, int(center[2] + range_r)),
            ]
            
            color_ref[gem_type] = {
                "samples": [list(map(int, s)) for s in samples],
                "avg_bgr": [int(x) for x in avg_bgr],
                "min_bgr": expanded_min,
                "max_bgr": expanded_max,
            }
            
            print(f"\n{gem_type.upper()}:")
            print(f"  Samples: {len(samples)}")
            print(f"  Average: BGR{tuple(int(x) for x in avg_bgr)}")
            print(f"  Range:   B[{expanded_min[0]}-{expanded_max[0]}] " +
                  f"G[{expanded_min[1]}-{expanded_max[1]}] R[{expanded_min[2]}-{expanded_max[2]}]")
        
        try:
            with open(self.COLOR_REFERENCE_FILE, "w") as f:
                json.dump(color_ref, f, indent=2)
            print(f"\n✓ Updated {self.COLOR_REFERENCE_FILE}")
            return True
        except Exception as e:
            print(f"\n✗ Failed to update: {e}")
            return False

if __name__ == "__main__":
    calibrator = QuickCalibrator()
    calibrator.recalibrate_yellow_orange()
