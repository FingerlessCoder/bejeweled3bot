# Bejeweled 3 AI Bot

An intelligent bot that plays Bejeweled 3 using computer vision and greedy move selection AI.

## Project Structure

```
bejeweled3Bot/
├── bejeweled3Bot.py      # Main entry point and bot controller
├── config.py              # Configuration constants and settings
├── vision.py              # Board detection and gem recognition
├── game_logic.py          # Move validation and cascade simulation
├── ai_player.py           # AI move selection strategy
├── debug.py               # Logging and visualization utilities
├── test_bot.py            # Test suite for components
└── README.md              # This file
```

## Architecture

### 1. **Vision System** (`vision.py`)
- Captures screenshots of the game window
- Detects game board region
- Identifies gem colors using HSV color space analysis
- Converts pixel coordinates to logical board state (8×8 array)

### 2. **Game Logic** (`game_logic.py`)
- Finds valid moves (swaps that create matches)
- Detects matches (3+ consecutive gems)
- Simulates gravity and cascades recursively
- Calculates move scores based on immediate matches + cascades

### 3. **AI Player** (`ai_player.py`)
- Uses greedy best-move selection
- Evaluates all valid moves using the game logic
- Picks highest-scoring move
- Tracks move history and statistics

### 4. **Bot Controller** (`bejeweled3Bot.py`)
- Main game loop: capture → detect board → select move → execute
- Converts logical moves to screen coordinates
- Controls mouse/drag actions via pyautogui
- Manages timing between moves

## Installation

### Prerequisites
- Python 3.8 or later
- Bejeweled 3 (browser or desktop version)

### Setup

1. **Clone/Download the files** to a directory:
   ```
   c:\Users\Wilso\Downloads\
   ```

2. **Install dependencies**:
   ```bash
   pip install pillow pyautogui opencv-python numpy
   ```

3. **Test the bot**:
   ```bash
   python test_bot.py
   ```

## Usage

### Quick Start

1. **Open Bejeweled 3** in your browser or launch the desktop app
2. **Focus the game window** (it should be active/in foreground)
3. **Run the bot**:
   ```bash
   python bejeweled3Bot.py
   ```

4. **Select mode**:
   - `1` - Auto mode: Bot plays continuously for specified duration
   - `2` - Interactive mode: Press SPACE to make moves, 'q' to quit
   - `3` - Test mode: Test vision system only

### Auto Mode

```bash
python bejeweled3Bot.py
# Select: 1
# Enter duration: 300 (seconds)
```

The bot will play for 5 minutes (300 seconds). Press Ctrl+C to stop.

### Interactive Mode

```bash
python bejeweled3Bot.py
# Select: 2
```

Controls:
- **SPACE** - Make one move
- **V** - Show board visualization
- **Q** - Quit

### Test Mode

```bash
python bejeweled3Bot.py
# Select: 3
```

Tests vision system without executing moves.

## Configuration

Edit `config.py` to customize:

### Board Detection
- `GEM_COLORS` - HSV color ranges for each gem type
- `BOARD_PADDING` - Margin around detected board

### Timing
- `MOVE_DELAY` - Delay after each move (milliseconds)
- `SCREENSHOT_DELAY` - Delay before capturing (milliseconds)
- `MAX_CASCADE_DEPTH` - How deep to simulate cascades

### Scoring
- `IMMEDIATE_MATCH_WEIGHT` - Points per matched gem
- `CASCADE_DEPTH_BONUS` - Bonus for cascade depth
- `CASCADE_BONUS_WEIGHT` - Cascade multiplier

### Debug
- `DEBUG_MODE` - Enable debug output
- `SAVE_DEBUG_SCREENSHOTS` - Save annotated screenshots for debugging
- `LOG_MOVES` - Log all moves to file

## How It Works

### Game Loop

1. **Capture** - Take screenshot of game window
2. **Detect** - Find board region and identify gem colors
3. **Find Valid Moves** - Try all adjacent swaps; keep those that create matches
4. **Evaluate** - Score each valid move (immediate matches + cascade score)
5. **Select** - Pick highest-scoring move
6. **Execute** - Move mouse and drag to perform swap
7. **Wait** - Delay before next iteration (let game update)
8. **Repeat**

### Move Scoring

```
Score(move) = (immediate_matches × 10) + cascade_bonus

Where:
- immediate_matches = number of gems matched in first swap
- cascade_bonus = (cascade_depth × 50) from resulting cascades
```

The bot greedily selects the move with highest score.

### Cascade Simulation

After a move, the bot:
1. Removes matched gems
2. Applies gravity (shift gems down)
3. Recursively checks for new matches
4. Accumulates score from all cascade levels
5. Stops when no more matches found (or max depth reached)

## Debugging

### Visual Output

When `DEBUG_MODE = True`:
- Console shows board state as ASCII grid
- Valid moves are listed
- Selected move is highlighted

### Saved Screenshots

Debug screenshots are saved to `debug_output/` with:
- Green box showing detected board region
- Grid lines showing cell divisions
- Labeled board state in console

### Logging

All moves logged to `bot_moves.log`:
```
Move 1: (3,2) <-> (3,3), Score: 45
Move 2: (5,1) <-> (6,1), Score: 120
...
```

## Limitations & Future Improvements

### Current Limitations
1. **Color Detection** - May fail with unusual lighting or UI scaling
2. **Cascade Accuracy** - Simulates gravity but may not match actual game fills (fills are random)
3. **Special Gems** - Ignores power gems, bombs, lightning gems (treats as normal)
4. **Game Variants** - Optimized for Classic mode; may need tuning for Blitz/other modes
5. **Window Detection** - Requires game window to be clearly visible

### Possible Improvements
1. **Lookahead** - Add 2-3 move lookahead with minimax evaluation
2. **Special Gems** - Detect and score power gems specially
3. **Pattern Learning** - Train neural network on gameplay data
4. **Cascade Prediction** - Account for probabilistic gem fills
5. **Mode Detection** - Auto-detect game mode and adapt strategy
6. **OCR** - Read score/goal text to optimize strategy per mode

## Troubleshooting

### "Could not find game board in screenshot"
- Make sure Bejeweled 3 window is visible and focused
- Adjust `BOARD_PADDING` in config if board is partially hidden
- Check that game is at normal zoom level (not zoomed in/out)

### "No valid moves available"
- Normal in rare board states
- Bot will retry with new screenshot
- If persistent, may indicate vision detection issue

### Moves execute but don't match what bot intended
- Vision detection may be inaccurate
- Check `debug_output/` screenshots to verify board state
- Adjust HSV color ranges for your specific Bejeweled version
- Increase `MOVE_DELAY` if game is too fast

### Bot moves very slowly
- Reduce `MOVE_DELAY` in config
- Check if `DEBUG_MODE` is slowing things down
- Disable `SAVE_DEBUG_SCREENSHOTS` for faster operation

## Performance

Typical performance on modern hardware:
- **Board detection**: 100-200ms per iteration
- **Move selection**: 50-100ms (depends on valid moves)
- **Move execution**: 300-500ms (depends on MOVE_DELAY)
- **Total cycle time**: ~500-800ms per move

## License

This project is for educational purposes.

## Support

For issues or questions:
1. Check debug output in console
2. Review saved screenshots in `debug_output/`
3. Check bot logs in `bot_moves.log`
4. Verify game window is properly visible and focused
