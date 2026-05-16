"""
Configuration for Bejeweled 3 Bot.

Loads settings from config.xml (if it exists), then applies per-mode overrides.
All values are exported as module-level constants — existing `from config import X`
code continues to work unchanged.

If config.xml is missing or a key cannot be parsed, hardcoded defaults are used.
"""

import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, Tuple

# ---------------------------------------------------------------------------
# Hardcoded defaults (used when config.xml is absent or a value is missing)
# ---------------------------------------------------------------------------

_DEFAULTS: Dict[str, Any] = {
    # Game
    "BOARD_WIDTH": 8,
    "BOARD_HEIGHT": 8,
    "resolution": "644x510",
    "mode": "classic",
    "window_title": "Bejeweled",

    # Timing
    "move_delay": 200,
    "wait_for_board_stable": True,
    "max_cascade_depth": 10,
    "cascade_depth_bonus": 50,

    # Detection
    "board_detection_padding": 30,
    "min_board_coverage": 0.75,
    "min_cell_confidence": 0.35,
    "min_match_length": 3,
    "min_board_pixel_dim": 200,
    "max_board_aspect_ratio": 1.5,
    "board_morph_kernel_size": (5, 5),
    "template_morph_kernel_size": (3, 3),
    "hsv_min_saturation": 100,
    "hsv_min_value": 80,

    # Gem template / classification
    "gem_template_size": (96, 96),
    "special_template_size": (64, 64),
    "alpha_mask_threshold": 10,
    "hypercube_std_min": 45,
    "hypercube_std_high": 65,
    "hypercube_color_dev_max": 55,
    "hypercube_brightness_min": 50,
    "hypercube_confidence_base": 0.50,
    "hypercube_confidence_max": 0.90,
    "flame_bot_brightness_min": 50,
    "flame_ratio_min": 1.20,
    "flame_base_conf_min": 0.35,
    "flame_confidence_base": 0.40,
    "flame_confidence_max": 0.70,
    "nearest_distance_max": 360,
    "nearest_confidence_min": 0.25,

    # Scoring
    "immediate_match_weight": 10,

    # Files
    "calibration_file": "board_calibration.json",
    "debug_output_dir": "debug_output",
    "log_file": "bot_moves.log",

    # Debug
    "debug_mode": True,
    "save_debug_screenshots": True,
    "max_debug_screenshots": 64,
    "log_moves": True,

    # Gem colors (BGR ranges per type)
    "GEM_COLORS": {
        "red":    ((120, 0, 0),   (255, 150, 150)),
        "orange": ((150, 80, 0),  (255, 200, 100)),
        "yellow": ((150, 120, 0), (255, 255, 100)),
        "green":  ((0, 150, 0),   (150, 255, 150)),
        "blue":   ((0, 100, 150), (150, 255, 255)),
        "purple": ((80, 0, 120),  (255, 150, 255)),
        "white":  ((180, 180, 180), (255, 255, 255)),
    },

    # Resolution presets
    "RESOLUTION_CONFIGS": {
        "644x510":  {"board_x_offset": 100, "board_y_offset": 50,  "cell_width": 60,  "cell_height": 57},
        "800x600":  {"board_x_offset": 85,  "board_y_offset": 45,  "cell_width": 70,  "cell_height": 70},
        "1024x768": {"board_x_offset": 110, "board_y_offset": 60,  "cell_width": 90,  "cell_height": 90},
        "1280x960": {"board_x_offset": 140, "board_y_offset": 75,  "cell_width": 110, "cell_height": 110},
        "1920x1200": {"board_x_offset": 210, "board_y_offset": 115, "cell_width": 170, "cell_height": 170},
    },
}

# Alias keys that map to exported UPPER_CASE constant names
_KEY_ALIAS: Dict[str, str] = {
    "resolution": "GAME_RESOLUTION",
    "mode": "GAME_MODE",
    "window_title": "GAME_WINDOW_TITLE",
    "move_delay": "MOVE_DELAY",
    "wait_for_board_stable": "WAIT_FOR_BOARD_STABLE",
    "max_cascade_depth": "MAX_CASCADE_DEPTH",
    "cascade_depth_bonus": "CASCADE_DEPTH_BONUS",
    "board_detection_padding": "BOARD_DETECTION_PADDING",
    "min_board_coverage": "MIN_BOARD_COVERAGE",
    "min_cell_confidence": "MIN_CELL_CONFIDENCE",
    "min_match_length": "MIN_MATCH_LENGTH",
    "min_board_pixel_dim": "MIN_BOARD_PIXEL_DIM",
    "max_board_aspect_ratio": "MAX_BOARD_ASPECT_RATIO",
    "board_morph_kernel_size": "BOARD_MORPH_KERNEL_SIZE",
    "template_morph_kernel_size": "TEMPLATE_MORPH_KERNEL_SIZE",
    "hsv_min_saturation": "HSV_MIN_SATURATION",
    "hsv_min_value": "HSV_MIN_VALUE",
    "gem_template_size": "GEM_TEMPLATE_SIZE",
    "special_template_size": "SPECIAL_TEMPLATE_SIZE",
    "alpha_mask_threshold": "ALPHA_MASK_THRESHOLD",
    "hypercube_std_min": "HYPERCUBE_STD_MIN",
    "hypercube_std_high": "HYPERCUBE_STD_HIGH",
    "hypercube_color_dev_max": "HYPERCUBE_COLOR_DEV_MAX",
    "hypercube_brightness_min": "HYPERCUBE_BRIGHTNESS_MIN",
    "hypercube_confidence_base": "HYPERCUBE_CONFIDENCE_BASE",
    "hypercube_confidence_max": "HYPERCUBE_CONFIDENCE_MAX",
    "flame_bot_brightness_min": "FLAME_BOT_BRIGHTNESS_MIN",
    "flame_ratio_min": "FLAME_RATIO_MIN",
    "flame_base_conf_min": "FLAME_BASE_CONF_MIN",
    "flame_confidence_base": "FLAME_CONFIDENCE_BASE",
    "flame_confidence_max": "FLAME_CONFIDENCE_MAX",
    "nearest_distance_max": "NEAREST_DISTANCE_MAX",
    "nearest_confidence_min": "NEAREST_CONFIDENCE_MIN",
    "immediate_match_weight": "IMMEDIATE_MATCH_WEIGHT",
    "calibration_file": "CALIBRATION_FILE",
    "debug_output_dir": "DEBUG_OUTPUT_DIR",
    "log_file": "LOG_FILE",
    "debug_mode": "DEBUG_MODE",
    "save_debug_screenshots": "SAVE_DEBUG_SCREENSHOTS",
    "max_debug_screenshots": "MAX_DEBUG_SCREENSHOTS",
    "log_moves": "LOG_MOVES",
}


# ---------------------------------------------------------------------------
# XML parser helpers
# ---------------------------------------------------------------------------

def _parse_bool(text: str) -> bool:
    return text.strip().lower() in ("true", "1", "yes")


def _parse_tuple(text: str) -> tuple:
    """Parse 'a,b,c' → (a, b, c) with auto type detection."""
    parts = [p.strip() for p in text.split(",")]
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            try:
                result.append(float(p))
            except ValueError:
                result.append(p)
    return tuple(result)


def _parse_value(text: str):
    """Auto-detect type of a text value from XML."""
    t = text.strip()
    if t.lower() in ("true", "false", "1", "0", "yes", "no"):
        return _parse_bool(t)
    try:
        return int(t)
    except ValueError:
        try:
            return float(t)
        except ValueError:
            pass
    if "," in t:
        return _parse_tuple(t)
    return t


def _load_config_xml(path: str) -> Dict[str, Any]:
    """Load flat config dict from config.xml (before mode overrides)."""
    config: Dict[str, Any] = {}

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except (ET.ParseError, FileNotFoundError, OSError):
        return config

    # --- Simple tags (text content → parsed value) ---
    SIMPLE_TAGS = {
        "board_width", "board_height", "resolution", "mode", "window_title",
        "move_delay", "wait_for_board_stable", "max_cascade_depth", "cascade_depth_bonus",
        "board_detection_padding", "min_board_coverage", "min_cell_confidence",
        "min_match_length", "min_board_pixel_dim", "max_board_aspect_ratio",
        "board_morph_kernel_size", "template_morph_kernel_size",
        "hsv_min_saturation", "hsv_min_value",
        "gem_template_size", "special_template_size", "alpha_mask_threshold",
        "hypercube_std_min", "hypercube_std_high", "hypercube_color_dev_max",
        "hypercube_brightness_min", "hypercube_confidence_base", "hypercube_confidence_max",
        "flame_bot_brightness_min", "flame_ratio_min", "flame_base_conf_min",
        "flame_confidence_base", "flame_confidence_max",
        "nearest_distance_max", "nearest_confidence_min",
        "immediate_match_weight",
        "calibration_file", "debug_output_dir", "log_file",
        "debug_mode", "save_debug_screenshots", "max_debug_screenshots", "log_moves",
    }

    for tag in SIMPLE_TAGS:
        elem = root.find(tag)
        if elem is not None and elem.text:
            config[tag] = _parse_value(elem.text)

    # --- Gem colors ---
    gem_colors_elem = root.find("gem_colors")
    if gem_colors_elem is not None:
        gem_colors = {}
        for gem in gem_colors_elem.findall("gem"):
            name = gem.get("name")
            min_str = gem.get("min", "")
            max_str = gem.get("max", "")
            if name and min_str and max_str:
                try:
                    mn = tuple(int(x.strip()) for x in min_str.split(","))
                    mx = tuple(int(x.strip()) for x in max_str.split(","))
                    gem_colors[name] = (mn, mx)
                except (ValueError, TypeError):
                    pass
        if gem_colors:
            config["GEM_COLORS"] = gem_colors

    # --- Resolution presets ---
    presets_elem = root.find("resolution_presets")
    if presets_elem is not None:
        presets: Dict[str, dict] = {}
        for preset in presets_elem.findall("preset"):
            name = preset.get("name")
            if name:
                try:
                    presets[name] = {
                        "board_x_offset": int(preset.get("x_offset", 0)),
                        "board_y_offset": int(preset.get("y_offset", 0)),
                        "cell_width": int(preset.get("cell_w", 0)),
                        "cell_height": int(preset.get("cell_h", 0)),
                    }
                except (ValueError, TypeError):
                    pass
        if presets:
            config["RESOLUTION_CONFIGS"] = presets

    # --- Mode-specific overrides ---
    mode_name = config.get("mode", _DEFAULTS.get("mode", "classic"))
    for mode_elem in root.findall("mode"):
        if mode_elem.get("name") == mode_name:
            for child in mode_elem:
                if child.text:
                    config[child.tag] = _parse_value(child.text)
            break

    return config


# ---------------------------------------------------------------------------
# Build the final configuration and expose runtime mode switcher
# ---------------------------------------------------------------------------

_xml_path = os.path.join(os.path.dirname(__file__), "config.xml")
_xml_root_cache: Any = None  # cache the parsed XML tree for fast mode switches


def _apply_config(xml_config: Dict[str, Any]) -> None:
    """Update module globals from a config dict (used at init and mode-switch)."""
    global BOARD_WIDTH, BOARD_HEIGHT, GEM_COLORS, RESOLUTION_CONFIGS
    global NORMAL_GEM_COUNT, FLAME_GEM_COUNT, STAR_GEM_OFFSET, HYPERCUBE_GEM_ID

    cfg = dict(_DEFAULTS)
    for k, v in xml_config.items():
        cfg[k] = v

    BOARD_WIDTH = cfg.get("BOARD_WIDTH", _DEFAULTS["BOARD_WIDTH"])
    BOARD_HEIGHT = cfg.get("BOARD_HEIGHT", _DEFAULTS["BOARD_HEIGHT"])
    GEM_COLORS = cfg.get("GEM_COLORS", _DEFAULTS["GEM_COLORS"])
    RESOLUTION_CONFIGS = cfg.get("RESOLUTION_CONFIGS", _DEFAULTS["RESOLUTION_CONFIGS"])
    NORMAL_GEM_COUNT = 7
    FLAME_GEM_COUNT = 7
    STAR_GEM_OFFSET = 14
    HYPERCUBE_GEM_ID = 21

    for xml_key, const_name in _KEY_ALIAS.items():
        if xml_key in cfg:
            globals()[const_name] = cfg[xml_key]
        elif const_name not in globals():
            globals()[const_name] = _DEFAULTS.get(xml_key)


def set_mode(mode_name: str) -> None:
    """
    Switch the active game mode at runtime.

    Re-loads config.xml, applies global defaults for the new mode value,
    then overlays the corresponding ``<mode name="...">`` block.

    Call this when the user selects a different game mode so that
    mode-specific overrides (debug_mode, wait_for_board_stable, etc.)
    take effect immediately.
    """
    global _xml_root_cache

    path = _xml_path
    try:
        if _xml_root_cache is None:
            tree = ET.parse(path)
            _xml_root_cache = tree.getroot()
        root = _xml_root_cache
    except (ET.ParseError, FileNotFoundError, OSError):
        # XML unavailable — just update the mode variable
        globals()["GAME_MODE"] = mode_name
        return

    # Start from the raw XML (global defaults only — no mode block yet)
    raw: Dict[str, Any] = {}
    _TAGS = {
        "board_width", "board_height", "resolution", "mode", "window_title",
        "move_delay", "wait_for_board_stable", "max_cascade_depth", "cascade_depth_bonus",
        "board_detection_padding", "min_board_coverage", "min_cell_confidence",
        "min_match_length", "min_board_pixel_dim", "max_board_aspect_ratio",
        "board_morph_kernel_size", "template_morph_kernel_size",
        "hsv_min_saturation", "hsv_min_value",
        "gem_template_size", "special_template_size", "alpha_mask_threshold",
        "hypercube_std_min", "hypercube_std_high", "hypercube_color_dev_max",
        "hypercube_brightness_min", "hypercube_confidence_base", "hypercube_confidence_max",
        "flame_bot_brightness_min", "flame_ratio_min", "flame_base_conf_min",
        "flame_confidence_base", "flame_confidence_max",
        "nearest_distance_max", "nearest_confidence_min",
        "immediate_match_weight",
        "calibration_file", "debug_output_dir", "log_file",
        "debug_mode", "save_debug_screenshots", "max_debug_screenshots", "log_moves",
    }
    for tag in _TAGS:
        elem = root.find(tag)
        if elem is not None and elem.text:
            raw[tag] = _parse_value(elem.text)

    raw["mode"] = mode_name  # override the mode value

    # Apply the mode-specific override block
    for mode_elem in root.findall("mode"):
        if mode_elem.get("name") == mode_name:
            for child in mode_elem:
                if child.text:
                    raw[child.tag] = _parse_value(child.text)
            break

    _apply_config(raw)


def save_setting(tag_name: str, value) -> bool:
    """
    Persist a single setting to ``config.xml`` so it survives restarts
    and is picked up by :func:`set_mode` the next time the game mode changes.

    1. Updates (or creates) the root-level ``<tag_name>`` element.
    2. If the current game mode overrides this tag, also updates the
       ``<mode>`` block so the override isn't stale.

    The runtime module global is **not** updated by this function — the
    caller is responsible for that, e.g.::

        cfg.DEBUG_MODE = False
        cfg.save_setting("debug_mode", cfg.DEBUG_MODE)

    Returns ``True`` on success, ``False`` if the XML file could not be
    read or written.
    """
    path = _xml_path
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except (ET.ParseError, FileNotFoundError, OSError):
        return False

    # Convert Python value to the string form that _parse_value can read back
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (int, float)):
        text = str(value)
    else:
        text = str(value)

    # 1. Update or create the root-level element
    elem = root.find(tag_name)
    if elem is None:
        elem = ET.SubElement(root, tag_name)
    elem.text = text

    # 2. If the current game mode overrides this tag, keep that in sync too
    current_mode = globals().get("GAME_MODE", str(_DEFAULTS.get("mode", "classic")))
    for mode_elem in root.findall("mode"):
        if mode_elem.get("name") == current_mode:
            override = mode_elem.find(tag_name)
            if override is not None:
                override.text = text
            break

    # Pretty-print (Python 3.9+)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass

    tree.write(path, encoding="utf-8", xml_declaration=True)
    return True


# ----- Initial load -----
_xml_config = _load_config_xml(_xml_path)
_apply_config(_xml_config)
