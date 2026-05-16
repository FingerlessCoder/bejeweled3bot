"""
Interactive color calibration tool for Bejeweled 3 bot.
Click on gems of each type in the game window to learn actual RGB values.
"""

import cv2
import numpy as np
import json
import os
import time
from PIL import ImageGrab
from config import GEM_COLORS
from typing import Dict, Optional, Tuple
import win32gui  # type: ignore[import-not-found]


class ColorCalibrator:
    """Learn gem colors by user clicking on actual gems in the game."""

    COLOR_REFERENCE_FILE = "color_reference.json"
    
    def __init__(self):
        self.color_samples: Dict[str, list] = {gem: [] for gem in GEM_COLORS.keys()}
        self.current_gem_type = None
        self.selecting = False
        self.selection_start = None
        self.selection_end = None
        
    def _find_game_window(self) -> Optional[int]:
        """Find Bejeweled window."""
        handles = []
        def _collect(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if "Bejeweled" in title:
                handles.append(hwnd)
        try:
            win32gui.EnumWindows(_collect, None)
        except Exception as e:
            print(f"[WARN] Error enumerating windows: {e}")
        return handles[0] if handles else None

    def _extract_color(self, x1: int, y1: int, x2: int, y2: int) -> Optional[Tuple[int, int, int]]:
        """Extract average BGR from clicked region."""
        screenshot_pil = ImageGrab.grab()
        img = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
        
        # Normalize coordinates
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

    def calibrate(self):
        """Interactive calibration UI."""
        print("\n" + "="*60)
        print("COLOR CALIBRATION TOOL")
        print("="*60)
        print("\nInstructions:")
        print("1. Click on a gem type from the list below")
        print("2. Drag a rectangle around a single gem in the game window")
        print("3. Release to record that color sample")
        print("4. Repeat 2-3 times per gem type for better accuracy")
        print("5. Press ENTER when done with a gem, Q to finish calibration")
        print("\nGem types: " + ", ".join(sorted(GEM_COLORS.keys())))
        print("="*60 + "\n")
        
        # Show game window
        hwnd = self._find_game_window()
        if hwnd is None:
            print("[ERROR] Bejeweled window not found. Please click on the game window.")
            return False
        
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception as e:
            print(f"[WARN] Could not focus game window: {e}")
        
        time.sleep(1)
        
        # Show color selection menu
        while True:
            print("\nAvailable gem types:")
            gem_types = sorted(GEM_COLORS.keys())
            for i, gem in enumerate(gem_types, 1):
                samples = len(self.color_samples[gem])
                print(f"  {i}. {gem} ({samples} samples)")
            print(f"  Q. Finish calibration")
            
            choice = input("\nSelect gem type (1-7) or Q: ").strip().upper()
            
            if choice == 'Q':
                break
            
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(gem_types):
                    gem = gem_types[idx]
                    if self._calibrate_gem_type(gem):
                        print(f"✓ Saved {len(self.color_samples[gem])} samples for {gem}")
                    else:
                        print(f"✗ Cancelled {gem} calibration")
                else:
                    print("Invalid selection")
            else:
                print("Invalid input")
        
        return self._save_color_reference()

    def _calibrate_gem_type(self, gem_type: str) -> bool:
        """Calibrate a single gem type."""
        self.current_gem_type = gem_type
        self.selection_start = None
        self.selection_end = None
        
        print(f"\n[CALIBRATE {gem_type.upper()}]")
        print("Click and drag a rectangle around a single gem of this type.")
        print("Press ENTER to save this sample, Q to skip this gem.")
        
        # Capture screenshot
        screenshot_pil = ImageGrab.grab()
        img = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
        
        window_name = f"Calibrate {gem_type} - Drag around a gem, press ENTER to save or Q to skip"
        state = {
            "selecting": False,
            "start": None,
            "end": None,
            "sample_count": 0,
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
                
                # Draw current selection
                if state["start"] is not None and state["end"] is not None:
                    cv2.rectangle(canvas, state["start"], state["end"], (0, 255, 0), 2)
                
                # Draw instructions
                text = f"{gem_type.upper()} | Samples: {state['sample_count']} | Drag a gem area, press ENTER to save or Q to skip"
                cv2.putText(canvas, text, (20, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                
                cv2.imshow(window_name, canvas)
                key = cv2.waitKey(20) & 0xFF
                
                # ENTER: save sample
                if key == 13 and state["start"] is not None and state["end"] is not None:
                    x1, y1 = state["start"]
                    x2, y2 = state["end"]
                    color = self._extract_color(x1, y1, x2, y2)
                    
                    if color:
                        self.color_samples[gem_type].append(color)
                        state["sample_count"] += 1
                        print(f"  ✓ Sample {state['sample_count']}: BGR{color}")
                        state["start"] = None
                        state["end"] = None
                        
                        if state["sample_count"] >= 3:
                            print(f"  (Got 3 samples, you can press Q to move to next gem)")
                    else:
                        print("  ✗ Invalid selection, try again")
                
                # Q: skip this gem
                elif key in (ord('q'), ord('Q')):
                    if state["sample_count"] > 0:
                        return True
                    else:
                        return False
        
        finally:
            cv2.destroyWindow(window_name)

    def _save_color_reference(self) -> bool:
        """Convert samples to color ranges and save."""
        print("\n" + "="*60)
        print("SAVING COLOR REFERENCE")
        print("="*60)
        
        color_reference = {}
        
        for gem_type in sorted(GEM_COLORS.keys()):
            samples = self.color_samples[gem_type]
            
            if not samples:
                print(f"[WARNING] No samples for {gem_type}, using default config")
                color_reference[gem_type] = {
                    "samples": [],
                    "avg_bgr": list(self._get_default_center(gem_type)),
                    "min_bgr": list(GEM_COLORS[gem_type][0]),
                    "max_bgr": list(GEM_COLORS[gem_type][1]),
                }
                continue
            
            # Compute bounds from samples
            samples_arr = np.array(samples, dtype=np.float32)
            avg_bgr = np.mean(samples_arr, axis=0)
            min_bgr = np.min(samples_arr, axis=0)
            max_bgr = np.max(samples_arr, axis=0)
            
            # Expand range by 15% to handle slight variations
            center = avg_bgr
            range_b = (max_bgr[0] - min_bgr[0]) / 2.0 + 10
            range_g = (max_bgr[1] - min_bgr[1]) / 2.0 + 10
            range_r = (max_bgr[2] - min_bgr[2]) / 2.0 + 10
            
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
            
            color_reference[gem_type] = {
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
            with open(self.COLOR_REFERENCE_FILE, "w", encoding="utf-8") as f:
                json.dump(color_reference, f, indent=2)
            print(f"\n✓ Color reference saved to {self.COLOR_REFERENCE_FILE}")
            return True
        except Exception as e:
            print(f"\n✗ Failed to save color reference: {e}")
            return False
    
    def _get_default_center(self, gem_type: str) -> Tuple[float, float, float]:
        """Get center of default BGR range."""
        rgb_min, rgb_max = GEM_COLORS[gem_type]
        return (
            (rgb_min[0] + rgb_max[0]) / 2.0,
            (rgb_min[1] + rgb_max[1]) / 2.0,
            (rgb_min[2] + rgb_max[2]) / 2.0,
        )


if __name__ == "__main__":
    calibrator = ColorCalibrator()
    success = calibrator.calibrate()
    
    if success:
        print("\n✓ Color calibration complete!")
        print("The bot will now use your custom color reference.")
    else:
        print("\n✗ Color calibration cancelled.")
