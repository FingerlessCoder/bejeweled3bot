# Configuration for Bejeweled 3 Bot

# Game board dimensions
BOARD_WIDTH = 8
BOARD_HEIGHT = 8

# Gem types and their RGB color ranges
# These colors are calibrated for Bejeweled 3 Steam version
# Range: ((r_min, g_min, b_min), (r_max, g_max, b_max))
# These ranges are BROAD to work with various monitor/display settings
GEM_COLORS = {
    "red": ((120, 0, 0), (255, 150, 150)),  # Red gems (any shade)
    "orange": ((150, 80, 0), (255, 200, 100)),  # Orange gems
    "yellow": ((150, 120, 0), (255, 255, 100)),  # Yellow/gold gems
    "green": ((0, 150, 0), (150, 255, 150)),  # Green/lime gems
    "blue": ((0, 100, 150), (150, 255, 255)),  # Blue/cyan gems
    "purple": ((80, 0, 120), (255, 150, 255)),  # Purple/magenta gems
    "white": ((180, 180, 180), (255, 255, 255)),  # White/bright gems
}

# ===== RESOLUTION CONFIGURATION =====
# Choose your game resolution. The bot works best with FIXED coordinates.
# Your Bejeweled 3 game window resolution from screenshot looks like ~1024x768 or similar
# Options: "800x600", "1024x768", "1280x960", "1920x1200", or use "native" for auto-detect

GAME_RESOLUTION = "644x510"  # ← CHANGE THIS to match your game window!

# Game mode used for calibration/profile routing.
# Supported: "classic", "zen", "lightning"
GAME_MODE = "classic"

GAME_WINDOW_TITLE = "Bejeweled"

# Pre-calibrated board coordinates for common resolutions
# If your resolution isn't here, add it using the calibration tool or use "native"
RESOLUTION_CONFIGS = {
    "644x510": {
        "board_x_offset": 100,
        "board_y_offset": 50,
        "cell_width": 60,
        "cell_height": 57,
    },
    "1024x768": {
        "board_x_offset": 110,
        "board_y_offset": 60,
        "cell_width": 90,
        "cell_height": 90,
    },
    "800x600": {
        "board_x_offset": 85,
        "board_y_offset": 45,
        "cell_width": 70,
        "cell_height": 70,
    },
    "1280x960": {
        "board_x_offset": 140,
        "board_y_offset": 75,
        "cell_width": 110,
        "cell_height": 110,
    },
    "1920x1200": {
        "board_x_offset": 210,
        "board_y_offset": 115,
        "cell_width": 170,
        "cell_height": 170,
    },
}

BOARD_DETECTION_PADDING = 30

# Saved manual calibration for resized windows.
# The detector stores board bounds as normalized client-area ratios so they can
# be reused after the game window is resized.
CALIBRATION_FILE = "board_calibration.json"

# Timing settings (milliseconds)
MOVE_DELAY = 200  # Delay after executing a move

# Gem type ID boundaries (matches vision.py's deterministic mapping)
NORMAL_GEM_COUNT = 7
HYPERCUBE_GEM_ID = 21

# Match detection
MIN_MATCH_LENGTH = 3
MIN_BOARD_COVERAGE = 0.75
# Minimum per-cell confidence (0.0-1.0) required to consider a cell reliable
MIN_CELL_CONFIDENCE = 0.35

# Cascade settings
MAX_CASCADE_DEPTH = 10  # Maximum cascade recursion depth to simulate
CASCADE_DEPTH_BONUS = 50  # Points per cascade level

# Move scoring weights
IMMEDIATE_MATCH_WEIGHT = 10

# Debug settings
DEBUG_MODE = True
SAVE_DEBUG_SCREENSHOTS = True
MAX_DEBUG_SCREENSHOTS = 64
DEBUG_OUTPUT_DIR = "debug_output"
LOG_MOVES = True
LOG_FILE = "bot_moves.log"
