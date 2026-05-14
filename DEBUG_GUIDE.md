# Bejeweled 3 Bot - Debugging Guide

## Problems Identified

### 1. **Detection Area is Wrong** ❌

**Root cause:** Your code tried to auto-detect the board using color masks (HSV), but this is unreliable.

**What the working bots do:**
- **DillonThyer**: Uses FIXED coordinates (tested and proven)
  - Window size: fixed at 500x500
  - Board coordinates: hardcoded offsets from top-left
  - Cell size: 48.75 × 49 pixels
  
- **Paepod**: Also uses fixed coordinates  
  - Game window: 1024×768
  - Cell padding: 82×82 pixels
  - Uses template matching with PNG files for extra reliability

**How I fixed it:**
✅ Added `WindowManager.setup_window()` - resizes game to 500×500
✅ Added FIXED coordinate system in `config.py`
✅ Changed color detection from HSV to RGB (more reliable for gems)
✅ Removed auto-detection of board region

---

## 2. **Window Management** ❌

**Problem:** Bot didn't ensure game window was:
- Actually focused/in foreground
- Correct size
- In correct position

**Solution:**
```python
# NEW: Call this before running the bot
WindowManager.setup_window()
```

This will:
1. Wait for you to click on the game window (5 seconds)
2. Get the window handle using `win32gui`
3. Resize it to exactly 500×500 pixels
4. Position it at (0, 0)

**Set `REQUIRE_WINDOW_SETUP = True` in config.py** (it's already True)

---

## 3. **Resolution & Window Size** ⚠️

**You need to decide:** Use fixed or variable window size?

### Option A: FIXED 500×500 (RECOMMENDED ✅)
- Easiest to debug
- All coordinates hardcoded and tested
- This is what DillonThyer used successfully
- **Current setup uses this**

**Steps:**
1. Leave `GAME_WINDOW_WIDTH = 500` and `GAME_WINDOW_HEIGHT = 500` in config.py
2. Run bot - it will auto-resize window to 500×500

### Option B: Auto-adjust to any window size ⚠️
- More flexible but complex
- Would need to dynamically calculate cell offsets
- Not recommended for initial debugging

---

## 4. **Gem Color Detection**

**Old approach:** HSV color ranges (too loose, inconsistent)
**New approach:** RGB color sampling at center of each cell (proven)

The RGB ranges in config.py are based on DillonThyer's working implementation:
```python
GEM_COLORS = {
    'red': ((200, 30, 50), (255, 70, 110)),
    'orange': ((240, 215, 100), (255, 255, 150)),
    'yellow': ((230, 170, 10), (255, 255, 90)),
    'green': ((60, 245, 100), (110, 255, 150)),
    'blue': ((0, 100, 200), (80, 220, 255)),
    'purple': ((130, 0, 120), (255, 50, 255)),
    'white': ((240, 240, 240), (255, 255, 255)),
}
```

If detection still fails, you may need to adjust these ranges for your specific display.

---

## Quick Start

### Step 1: Test Detection
```bash
python test_detection.py
```

This will:
1. Prompt you to click on game window
2. Resize window to 500×500
3. Capture screenshot
4. Show what colors it detected
5. Save debug screenshot with grid overlay

✅ If this works, detection is fixed!

### Step 2: Run Full Bot
```bash
python -c "from bejeweled3Bot import BejewelBot; BejewelBot().start(60)"
```

This runs the bot for 60 seconds. 

**Important:** Make sure the game is in the START MENU or an active game state when you run this.

---

## Debugging Checklist

- [ ] **Window size is 500×500** - Check your screen, should be a small window
- [ ] **Window at (0, 0)** - Top-left corner of screen
- [ ] **Game is visible and focused** - Not minimized or behind other windows
- [ ] **Board is fully visible** - All 8×8 gems can be seen
- [ ] **Run test_detection.py first** - Check coverage percentage
  - Should be > 80% cells detected
  - If < 50%, RGB ranges need adjustment
- [ ] **Check debug screenshots** - Look in `debug_output/` folder
  - Should show grid overlay on board
  - Should have letter labels (R, G, B, etc.) on each cell

---

## If Detection Still Fails

### Issue 1: Low coverage in test_detection.py

**Possible causes:**
1. **RGB ranges are wrong for your display**
   - Lighting conditions matter (monitor brightness, room light)
   - Different game versions might have slightly different colors

**Fix:**
1. Run test_detection.py and save the screenshot
2. Use an image editor (Paint, Photoshop) to sample RGB values from actual gems
3. Update config.py with correct ranges

### Issue 2: "Could not find game board"

**Possible causes:**
1. Window is wrong size (not 500×500)
2. Window is not at position (0, 0)
3. Gem colors don't match ANY range (detection fails completely)

**Fix:**
1. Verify window size: open game, check Windows task bar or use win32gui to inspect
2. Verify position: window top-left should be at screen corner (0, 0)
3. If colors still don't match, sample RGB values manually

### Issue 3: Some gems detected as "unknown"

**Normal behavior** - if detection coverage is > 70%, bot should still work
**Fix:** Adjust RGB ranges for the specific colors that are failing

---

## Code Changes Summary

### config.py
- ✅ Changed to RGB color ranges (not HSV)
- ✅ Added FIXED board coordinates
- ✅ Added GAME_WINDOW_WIDTH/HEIGHT configuration

### vision.py
- ✅ Added `WindowManager` class for window setup
- ✅ Rewrote `BoardDetector` to use fixed coordinates
- ✅ Changed from HSV to RGB color sampling
- ✅ Added better debug output

### bejeweled3Bot.py
- ✅ Import `WindowManager`
- ✅ Call `WindowManager.setup_window()` in `start()` method

### NEW FILES
- ✅ `test_detection.py` - standalone test script
- ✅ `DEBUG_GUIDE.md` - this file

---

## Next Steps

1. **Run test_detection.py** to verify detection works
2. If detection coverage > 70%, run the full bot
3. If coverage < 50%, adjust RGB ranges (see debugging section)
4. Once working, you can set `REQUIRE_WINDOW_SETUP = False` to skip window setup (game must already be 500×500 at position 0,0)

Good luck! 🎮

