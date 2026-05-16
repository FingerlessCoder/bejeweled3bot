# Poker Mode Profile

## Overview

Poker Mode is a specialized game profile for Bejeweled 3 that uses poker hand patterns instead of traditional gem matching. The bot detects and scores poker hands, using a strategic 2-ply lookahead algorithm to maximize hand scoring potential.

## Hand Patterns & Scoring

Poker Mode recognizes 6 distinct hand types, each worth different points:

| Hand Type | Pattern | Points | Description |
|-----------|---------|--------|-------------|
| **Flush** | 5 of a kind | 750 | Five gems of the same color in a connected group |
| **4 of a Kind** | 4 matching gems | 500 | Four gems of the same color in a connected group |
| **Full House** | 3 + 2 pattern | 350 | Three gems of one color + two gems of another color, adjacent groups |
| **2 Pair** | 2 + 2 pattern | 150 | Two pairs of different colors, adjacent groups |
| **Spectrum** | 5 different colors | 100 | Five gems in a row/column with all different colors |
| **Pair** | 2 matching gems | 50 | Two gems of the same color |

## Board Calibration

Poker Mode uses a dedicated calibration profile optimized for poker gameplay:

```json
"poker": {
  "normalized_board_region": {
    "left": 0.35,
    "top": 0.12,
    "right": 0.95,
    "bottom": 0.88
  }
}
```

### Calibration Area Notes
- **Wider Left-Right Coverage**: Captures full poker board width (35%-95% of window)
- **Centered Vertical**: Focuses on active game area (12%-88% of window height)
- **Optimized for 5-move patterns**: Board region selected to best detect connected gem groups up to 5 gems

If your poker game window is positioned differently, run the calibration tool:
```bash
python calibrate_colors.py
```

And select "poker" mode when prompted.

## Algorithm Strategy

### Move Selection (2-Ply Lookahead)

The Poker AI Player uses a two-stage evaluation:

1. **Immediate Move Evaluation**
   - Simulates the swap and all resulting cascades
   - Scores all hands created by the move
   - Sums up total immediate points

2. **Follow-up Potential Evaluation**
   - Analyzes the resulting board state
   - Counts valid follow-up moves available
   - Weights follow-up potential at 50% (`LOOKAHEAD_DISCOUNT = 0.5`)

3. **Total Score Calculation**
   ```
   total_score = immediate_hand_score + (follow_up_potential × 0.5)
   ```

### Hand Detection Logic

The algorithm uses **connected group analysis**:

1. **Connectivity Scan**: Finds all gems connected horizontally or vertically
2. **Group Analysis**: Evaluates each connected group as a potential poker hand
3. **Multi-Hand Detection**: Can identify multiple hands on a single board (e.g., one flush + one pair)
4. **Full House/2-Pair Detection**: Looks for adjacent groups of matching sizes

## File Structure

New poker-specific files created:

- **`poker_game_logic.py`** - Core poker hand detection and cascade simulation
  - `PokerGameLogic` class with hand pattern detection
  - Poker hand scoring (flush, full house, etc.)
  - Board cascade simulation with hand tracking
  - Gravity and gem removal mechanics

- **`poker_ai_player.py`** - AI strategy engine
  - `PokerAIPlayer` class with 2-ply lookahead
  - Move ranking and selection
  - Board opportunity analysis
  - Move history and statistics tracking

## Configuration

To enable poker mode, edit `config.py`:

```python
GAME_MODE = "poker"  # Switch from "classic", "zen", "lightning" to "poker"
```

## Usage Example

```python
from poker_ai_player import PokerAIPlayer
import numpy as np

# Initialize AI with board state
board = np.array(...)  # Your board state
ai = PokerAIPlayer(board)

# Get best move
best_move = ai.select_best_move(board)
if best_move:
    (r1, c1), (r2, c2) = best_move
    print(f"Swap ({r1},{c1}) with ({r2},{c2})")

# View statistics
stats = ai.get_move_stats()
print(f"Total moves: {stats['total_moves']}")
print(f"Average score: {stats['avg_score']}")
print(f"Hands made: {stats['hand_counts']}")

# Analyze board opportunities
opportunities = ai.analyze_board_opportunities(board)
print(f"Available flushes: {opportunities['flush']}")
print(f"Available full houses: {opportunities['full_house']}")
```

## Key Differences from Classic Mode

| Aspect | Classic Mode | Poker Mode |
|--------|--------------|-----------|
| **Match Detection** | 3+ consecutive gems | Connected groups (2-5 gems) |
| **Scoring** | Match length based | Hand type based (50-750 pts) |
| **Special Gems** | Flame, Star, Hypercube | Not specifically tracked |
| **Cascade Logic** | Standard Bejeweled rules | Poker hand pattern cascades |
| **AI Strategy** | Generic greedy scoring | Poker-optimized lookahead |
| **Board Region** | Classic coordinates | Poker-optimized calibration |

## Troubleshooting

### Hand detection not working
- Verify `GAME_MODE = "poker"` in config.py
- Check board calibration: run `calibrate_colors.py` and select poker profile
- Ensure gem colors are properly detected in your game window

### Low scores
- Poker mode requires intentional strategic placement (2-ply lookahead)
- Ensure the AI is looking ahead to follow-up opportunities
- Check that the board is large enough for hand patterns (8×8 minimum)

### Cascades not triggering
- Verify that gravity is being applied (`_apply_gravity` called in cascade)
- Check that matched cells are removed before gravity
- Ensure at least 2+ gems of same color are connected for hand detection

## Advanced Customization

### Adjust Hand Scores

Edit `poker_game_logic.py`:
```python
POKER_HAND_SCORES = {
    'flush': 750,          # Modify these values
    'four_of_a_kind': 500,
    'full_house': 350,
    ...
}
```

### Adjust AI Look-ahead Weight

Edit `poker_ai_player.py`:
```python
LOOKAHEAD_DISCOUNT = 0.5  # Higher = more weight to follow-up moves (0.0-1.0)
```

### Change Board Detection Range

Edit `board_calibration.json` poker profile or run calibration tool for custom regions.
