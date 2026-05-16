"""
Vision module for Bejeweled 3 bot.
Handles screenshot capture, gem detection, and board state extraction.
Uses AUTO-DETECTION of board region (works with any game resolution).
"""

import cv2
import json
import numpy as np
from PIL import ImageGrab
import win32gui  # type: ignore[import-not-found]
import time
import glob
from config import (
    BOARD_WIDTH,
    BOARD_HEIGHT,
    GEM_COLORS,
    BOARD_DETECTION_PADDING,
    GAME_WINDOW_TITLE,
    GAME_RESOLUTION,
    RESOLUTION_CONFIGS,
    DEBUG_MODE,
    DEBUG_OUTPUT_DIR,
    SAVE_DEBUG_SCREENSHOTS,
    MAX_DEBUG_SCREENSHOTS,
    MIN_BOARD_COVERAGE,
    CALIBRATION_FILE,
    GEM_TEMPLATE_SIZE,
    SPECIAL_TEMPLATE_SIZE,
    ALPHA_MASK_THRESHOLD,
    HYPERCUBE_STD_MIN,
    HYPERCUBE_STD_HIGH,
    HYPERCUBE_COLOR_DEV_MAX,
    HYPERCUBE_BRIGHTNESS_MIN,
    HYPERCUBE_CONFIDENCE_BASE,
    HYPERCUBE_CONFIDENCE_MAX,
    FLAME_BOT_BRIGHTNESS_MIN,
    FLAME_RATIO_MIN,
    FLAME_BASE_CONF_MIN,
    FLAME_CONFIDENCE_BASE,
    FLAME_CONFIDENCE_MAX,
    NEAREST_DISTANCE_MAX,
    NEAREST_CONFIDENCE_MIN,
    MIN_BOARD_PIXEL_DIM,
    MAX_BOARD_ASPECT_RATIO,
    BOARD_MORPH_KERNEL_SIZE,
    TEMPLATE_MORPH_KERNEL_SIZE,
    HSV_MIN_SATURATION,
    HSV_MIN_VALUE,
)
import os
from typing import Tuple, Optional


class WindowManager:
    """Handle game window setup and focus."""

    @staticmethod
    def _find_window_handle() -> Optional[int]:
        """Find the Bejeweled window handle by title."""
        handles = []

        def _collect(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if GAME_WINDOW_TITLE in title:
                handles.append(hwnd)

        try:
            win32gui.EnumWindows(_collect, None)
        except Exception:
            return None

        return handles[0] if handles else None

    @staticmethod
    def get_game_window_client_rect() -> Optional[Tuple[int, int, int, int]]:
        """Return the game client area in screen coordinates."""
        hwnd = WindowManager._find_window_handle()
        if hwnd is None:
            return None

        try:
            client_left, client_top, client_right, client_bottom = (
                win32gui.GetClientRect(hwnd)
            )
            top_left = win32gui.ClientToScreen(hwnd, (client_left, client_top))
            bottom_right = win32gui.ClientToScreen(hwnd, (client_right, client_bottom))

            x = top_left[0]
            y = top_left[1]
            w = bottom_right[0] - top_left[0]
            h = bottom_right[1] - top_left[1]
            return (x, y, w, h)
        except Exception:
            return None

    @staticmethod
    def setup_window():
        """
        Focus the game window.
        No longer forces 500x500 - lets game run at native resolution.
        """
        print("[SETUP] Please CLICK on the Bejeweled game window...")
        print("[SETUP] Game can be any resolution (800x600, 1024x768, 1920x1200, etc.)")
        time.sleep(5)

        try:
            bwindow = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(bwindow)
            print(f"[SETUP] Window found: {title}")

            # Get window dimensions
            client_rect = WindowManager.get_game_window_client_rect()
            if client_rect is not None:
                _, _, width, height = client_rect
                print(f"[SETUP] Client area size: {width}x{height}")
            else:
                rect = win32gui.GetWindowRect(bwindow)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                print(f"[SETUP] Window size: {width}x{height}")

            return True
        except Exception as e:
            print(f"[ERROR] Failed to setup window: {e}")
            return False


class BoardDetector:
    """Detects game board using AUTO-DETECTION (works with any resolution)."""

    def __init__(self):
        self.gem_type_map = {}
        self._initialize_gem_types()
        # Must define special_sample_dir before loading templates
        self.special_sample_dir = os.path.join(
            os.path.dirname(__file__), "special_templates"
        )
        os.makedirs(self.special_sample_dir, exist_ok=True)
        self.gem_templates = self._load_gem_templates()
        self.special_templates = self._load_special_templates()
        self.board_calibration = self._load_board_calibration()
        self.color_reference = self._load_color_reference()
        self.last_board = None
        self.board_region = None
        self.cell_width: float = 0.0
        self.cell_height: float = 0.0
        self.last_coverage: float = 0.0
        self.debug_screenshot_count: int = 0
        self.last_confidences = np.zeros((BOARD_HEIGHT, BOARD_WIDTH), dtype=float)
        self.special_sample_count = 0
        self.max_special_samples = 200

    def _get_calibration_profile(self, mode_override: str = "") -> str:
        """Map runtime game mode to a calibration profile key.
        Uses config module directly so runtime changes (e.g. from menu) take effect."""
        import config as _cfg
        mode = mode_override if mode_override else str(_cfg.GAME_MODE).strip().lower()
        if mode in ("classic", "zen"):
            return "classic"
        if mode in ("lightning", "ice_storm", "icestorm", "butterfly"):
            return "lightning"
        return mode if mode else "classic"

    def _initialize_gem_types(self):
        """Create mapping of gem colors to IDs, including special gems."""
        self.special_gem_types = [
            "blue_flame",
            "green_flame",
            "orange_flame",
            "purple_flame",
            "red_flame",
            "white_flame",
            "yellow_flame",
            "blue_star",
            "green_star",
            "orange_star",
            "purple_star",
            "red_star",
            "white_star",
            "yellow_star",
            "hypercube",
        ]
        all_gems = sorted(GEM_COLORS.keys()) + self.special_gem_types
        for idx, gem_type in enumerate(all_gems):
            self.gem_type_map[gem_type] = idx
        self.normal_gem_count = len(GEM_COLORS)

    def _get_color_center(self, gem_type: str) -> Tuple[float, float, float]:
        """Return the midpoint BGR of a gem's configured range.

        GEM_COLORS stores ranges as (R, G, B) — convert to BGR for OpenCV.
        """
        if self.color_reference and gem_type in self.color_reference:
            avg = self.color_reference[gem_type].get("avg_bgr", [0, 0, 0])
            return tuple(float(x) for x in avg)
        rgb_min, rgb_max = GEM_COLORS[gem_type]
        return (
            (rgb_min[2] + rgb_max[2]) / 2.0,  # B
            (rgb_min[1] + rgb_max[1]) / 2.0,  # G
            (rgb_min[0] + rgb_max[0]) / 2.0,  # R
        )

    def _load_gem_templates(self) -> dict:
        """Load bundled webp gem art as template references."""
        templates = {}
        template_files = glob.glob(
            os.path.join(os.path.dirname(__file__), "Bejeweled_3_*.webp")
        )
        template_size = GEM_TEMPLATE_SIZE

        for filepath in template_files:
            basename = os.path.splitext(os.path.basename(filepath))[0]
            gem_name = basename.replace("Bejeweled_3_", "").lower()
            # Accept any bundled webp template (including special gems like flame/star)

            image = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
            if image is None or image.ndim != 3 or image.shape[2] < 4:
                continue

            alpha = image[:, :, 3]
            mask = alpha > ALPHA_MASK_THRESHOLD
            if not np.any(mask):
                continue

            # Store a compact template for fast per-cell matching.
            template_bgr = cv2.resize(
                image[:, :, :3], template_size, interpolation=cv2.INTER_AREA
            )
            template_mask = (
                cv2.resize(
                    mask.astype(np.uint8),
                    template_size,
                    interpolation=cv2.INTER_NEAREST,
                )
                > 0
            )
            templates[gem_name] = {
                "bgr": template_bgr,
                "mask": template_mask,
                "size": (template_bgr.shape[1], template_bgr.shape[0]),
            }

        if templates:
            print(f"[DEBUG] Loaded {len(templates)} gem webp templates")
        else:
            print(
                "[WARNING] No webp gem templates loaded; falling back to color reference"
            )

        return templates

    def _load_special_templates(self) -> dict:
        """Load JPG special gem templates, resize to standard size, improve masks."""
        TEMPLATE_SIZE = SPECIAL_TEMPLATE_SIZE
        templates = {}
        for filepath in glob.glob(os.path.join(self.special_sample_dir, "*.jpg")):
            basename = os.path.splitext(os.path.basename(filepath))[0]
            gem_name = basename.replace("Bejeweled_3_", "").lower()
            image = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
            if image is None or image.ndim < 2:
                continue

            bgr = (
                image[:, :, :3]
                if image.ndim == 3
                else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            )

            # Generate mask via Otsu threshold on grayscale.
            # This cleanly separates the bright gem from its darker background,
            # giving ~30–50% mask coverage (vs 75–99% with the old corner-based approach).
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            _, otsu_mask = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            # Clean up: remove speckles, fill small holes
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, TEMPLATE_MORPH_KERNEL_SIZE)
            cleaned = cv2.morphologyEx(otsu_mask, cv2.MORPH_OPEN, kernel)
            cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

            # Keep only the largest connected component (the gem body)
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
                cleaned, connectivity=8
            )
            if num_labels > 1:
                sizes = stats[1:, cv2.CC_STAT_AREA]
                largest_label = np.argmax(sizes) + 1
                mask = labels == largest_label
            else:
                # Fallback: circular centre region
                h, w = bgr.shape[:2]
                cy, cx = h // 2, w // 2
                Y, X = np.ogrid[:h, :w]
                radius = min(h, w) * 0.35
                mask = (X - cx) ** 2 + (Y - cy) ** 2 <= radius ** 2

            # Resize template and mask to standard size
            resized_bgr = cv2.resize(
                bgr, TEMPLATE_SIZE, interpolation=cv2.INTER_AREA
            )
            resized_mask = cv2.resize(
                mask.astype(np.uint8), TEMPLATE_SIZE, interpolation=cv2.INTER_NEAREST
            ) > 0

            templates[gem_name] = {
                "bgr": resized_bgr,
                "mask": resized_mask,
                "size": TEMPLATE_SIZE,
            }

        if templates:
            print(
                f"[DEBUG] Loaded {len(templates)} special gem templates ({TEMPLATE_SIZE[0]}x{TEMPLATE_SIZE[1]})"
            )
        return templates

    def _classify_cell_by_template(self, cell_region: np.ndarray) -> Tuple[str, float]:
        """Classify a cell using bundled gem art templates."""
        if not self.gem_templates and not self.special_templates:
            return "unknown", 0.0

        best_match = "unknown"
        best_score = float("inf")

        # Try special templates first so special gems take priority
        for gem_type, template in self.special_templates.items():
            template_bgr = template["bgr"]
            template_mask = template["mask"]
            target_size = template["size"]

            if cell_region.shape[0] < 2 or cell_region.shape[1] < 2:
                continue

            # INTER_LINEAR produces better quality when upscaling the cell to match template size
            resized_cell = cv2.resize(
                cell_region, target_size, interpolation=cv2.INTER_LINEAR
            )
            diff = np.abs(resized_cell.astype(np.int16) - template_bgr.astype(np.int16))
            masked_diff = diff[template_mask]

            if masked_diff.size == 0:
                continue

            score = float(np.mean(masked_diff))
            if score < best_score:
                best_score = score
                best_match = gem_type

        # Try normal gem templates
        for gem_type, template in self.gem_templates.items():
            template_bgr = template["bgr"]
            template_mask = template["mask"]
            target_size = template["size"]

            if cell_region.shape[0] < 2 or cell_region.shape[1] < 2:
                continue

            resized_cell = cv2.resize(
                cell_region, target_size, interpolation=cv2.INTER_LINEAR
            )
            diff = np.abs(resized_cell.astype(np.int16) - template_bgr.astype(np.int16))
            masked_diff = diff[template_mask]

            if masked_diff.size == 0:
                continue

            score = float(np.mean(masked_diff))
            if score < best_score:
                best_score = score
                best_match = gem_type

        if best_match == "unknown":
            return "unknown", 0.0

        is_special = best_match in self.special_gem_types
        confidence = max(0.0, min(1.0, 1.0 - (best_score / 140.0)))
        threshold = 0.30 if is_special else 0.35
        if confidence < threshold:
            return "unknown", confidence

        return best_match, confidence

    def _classify_by_statistics(self, cell_region: np.ndarray) -> Tuple[str, float]:
        """Very conservative statistical fallback — hypercube only.

        Analyses the centre 50 % of the cell to avoid edge/background noise.
        Hypercube's multi-colour swirled pattern gives extremely high
        per-channel variance and a near-neutral average across the centre,
        which no normal / flame / star gem matches (they all have a dominant
        single colour).

        Returns (gem_type_string, confidence) or ("unknown", 0.0).
        """
        h, w = cell_region.shape[:2]
        if h < 8 or w < 8:
            return "unknown", 0.0

        # Analyse only the centre 50% (hypercube swirl fills the core)
        cy, cx = h // 2, w // 2
        crop = cell_region[cy - h // 4 : cy + h // 4, cx - w // 4 : cx + w // 4]
        if crop.size < 100:
            return "unknown", 0.0

        b = crop[:, :, 0].astype(np.float32)
        g = crop[:, :, 1].astype(np.float32)
        r = crop[:, :, 2].astype(np.float32)

        b_std = float(np.std(b))
        g_std = float(np.std(g))
        r_std = float(np.std(r))
        mean_std = (b_std + g_std + r_std) / 3.0

        if mean_std < HYPERCUBE_STD_MIN:
            return "unknown", 0.0

        b_mean = float(np.mean(b))
        g_mean = float(np.mean(g))
        r_mean = float(np.mean(r))
        mean_brightness = (b_mean + g_mean + r_mean) / 3.0

        # Very dark centre → likely empty space or obstacle
        if mean_brightness < HYPERCUBE_BRIGHTNESS_MIN:
            return "unknown", 0.0

        # Deviation from gray — hypercube centre is near-neutral
        color_dev = abs(b_mean - mean_brightness) + abs(g_mean - mean_brightness) + abs(r_mean - mean_brightness)

        # === Hypercube === (high variance + near-neutral colour)
        if mean_std > HYPERCUBE_STD_HIGH and color_dev < HYPERCUBE_COLOR_DEV_MAX:
            conf = min(HYPERCUBE_CONFIDENCE_MAX, HYPERCUBE_CONFIDENCE_BASE + (mean_std - HYPERCUBE_STD_HIGH) / 100.0)
            return "hypercube", conf

        return "unknown", 0.0

    def _classify_flame_by_stats(self, cell_region: np.ndarray) -> Tuple[str, float]:
        """Conservative flame detection using top/bottom brightness asymmetry.

        Flame gems have a bright animated flame overlay concentrated at the
        TOP of the cell, which makes the top half distinctly brighter and more
        yellow than the bottom.  Normal gems have a glossy highlight near the
        centre but lack this strong top/bottom asymmetry.

        Returns (gem_type_string, confidence) or ("unknown", 0.0).
        """
        h, w = cell_region.shape[:2]
        if h < 8 or w < 8:
            return "unknown", 0.0

        # Top 25 % vs bottom 25 %
        top = cell_region[0 : h // 4, :, :].astype(np.float32)
        bot = cell_region[3 * h // 4 :, :, :].astype(np.float32)
        if top.size < 50 or bot.size < 50:
            return "unknown", 0.0

        top_bright = float(np.mean(top))
        bot_bright = float(np.mean(bot))

        # If bottom is too dark, we're looking at background, not the gem base
        if bot_bright < FLAME_BOT_BRIGHTNESS_MIN:
            return "unknown", 0.0

        # Skip if bottom is actually brighter (definitely not a flame)
        if top_bright <= bot_bright:
            return "unknown", 0.0

        ratio = top_bright / max(bot_bright, 1.0)

        # Ratio must be significant — normal gem highlights are not this strong
        if ratio < FLAME_RATIO_MIN:
            return "unknown", 0.0

        # The extra brightness on top must have a yellow-ish cast (flame colour)
        # In BGR: yellow is high G and R, low B.  The flame adds R+G.
        top_b = float(np.mean(top[:, :, 0]))
        top_g = float(np.mean(top[:, :, 1]))
        top_r = float(np.mean(top[:, :, 2]))

        # Yellow flame: R and G dominate over B in the top region
        if top_r < top_b * 1.1 and top_g < top_b * 1.1:
            return "unknown", 0.0

        # Classify base colour from the bottom half (unobscured by flame)
        avg_b_bot = int(np.mean(bot[:, :, 0]))
        avg_g_bot = int(np.mean(bot[:, :, 1]))
        avg_r_bot = int(np.mean(bot[:, :, 2]))
        base_color, base_conf = self._classify_bgr_pixel(avg_b_bot, avg_g_bot, avg_r_bot)
        if base_conf < FLAME_BASE_CONF_MIN or base_color == "unknown":
            return "unknown", 0.0

        confidence = min(FLAME_CONFIDENCE_MAX, FLAME_CONFIDENCE_BASE + (ratio - FLAME_RATIO_MIN) * 0.8)
        return f"{base_color}_flame", confidence

    def _save_special_sample(self, cell_region: np.ndarray, hint: Optional[str] = None):
        """Save a cropped cell image for later template creation.

        Avoid capturing too many samples in one run.
        """
        try:
            if self.special_sample_count >= self.max_special_samples:
                return

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            hint_tag = f"_{hint}" if hint else ""
            filename = (
                f"sample{hint_tag}_{timestamp}_{self.special_sample_count:04d}.png"
            )
            filepath = os.path.join(self.special_sample_dir, filename)

            # Convert BGR to RGB for saving via cv2 (cv2.imwrite expects BGR)
            cv2.imwrite(filepath, cell_region)
            self.special_sample_count += 1
            if self.special_sample_count % 10 == 0:
                print(
                    f"[DEBUG] Saved {self.special_sample_count} special gem samples so far"
                )
        except Exception as e:
            print(f"[WARNING] Failed to save special sample: {e}")

    def _classify_bgr_pixel(self, b: int, g: int, r: int) -> Tuple[str, float]:
        """Classify a BGR pixel by exact range match or nearest configured color."""
        # Use learned color reference if available, otherwise use config defaults
        color_ranges = {}
        if self.color_reference:
            for gem_type, data in self.color_reference.items():
                min_bgr = data.get("min_bgr", [0, 0, 0])
                max_bgr = data.get("max_bgr", [255, 255, 255])
                color_ranges[gem_type] = (tuple(min_bgr), tuple(max_bgr))
        else:
            # GEM_COLORS stores (R, G, B) — swap to (B, G, R) for OpenCV
            color_ranges = {}
            for gem_type, (rgb_min, rgb_max) in GEM_COLORS.items():
                bgr_min = (rgb_min[2], rgb_min[1], rgb_min[0])
                bgr_max = (rgb_max[2], rgb_max[1], rgb_max[0])
                color_ranges[gem_type] = (bgr_min, bgr_max)

        best_match = "unknown"
        best_score = float("inf")

        for gem_type, (bgr_min, bgr_max) in color_ranges.items():
            b_min, g_min, r_min = bgr_min
            b_max, g_max, r_max = bgr_max

            if b_min <= b <= b_max and g_min <= g <= g_max and r_min <= r <= r_max:
                center_b, center_g, center_r = self._get_color_center(gem_type)
                distance = abs(b - center_b) + abs(g - center_g) + abs(r - center_r)
                if distance < best_score:
                    best_score = distance
                    best_match = gem_type

        if best_match != "unknown":
            return best_match, 1.0

        nearest_match = "unknown"
        nearest_distance = float("inf")
        for gem_type in color_ranges.keys():
            center_b, center_g, center_r = self._get_color_center(gem_type)
            distance = abs(b - center_b) + abs(g - center_g) + abs(r - center_r)
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_match = gem_type

        # The board gems are highly saturated. Pixels far away from any gem center
        # are usually board chrome or effects, so keep a conservative fallback limit.
        if nearest_distance <= NEAREST_DISTANCE_MAX:
            confidence = max(NEAREST_CONFIDENCE_MIN, 1.0 - (nearest_distance / NEAREST_DISTANCE_MAX))
            return nearest_match, confidence

        return "unknown", 0.0

    def capture_screenshot(self) -> Optional[np.ndarray]:
        """Capture full screenshot of game window."""
        try:
            # Capture entire screen
            screenshot_pil = ImageGrab.grab()
            img_array = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
            return img_array
        except Exception as e:
            print(f"[ERROR] Screenshot capture failed: {e}")
            return None

    def _load_board_calibration(self) -> Optional[dict]:
        """Load a saved normalized board calibration if available."""
        if not os.path.exists(CALIBRATION_FILE):
            return None

        try:
            with open(CALIBRATION_FILE, "r", encoding="utf-8") as handle:
                calibration = json.load(handle)

            profile_key = self._get_calibration_profile()
            required_keys = ("left", "top", "right", "bottom")

            # v2 format: { profiles: { <profile>: { normalized_board_region: ... } } }
            profiles = calibration.get("profiles")
            if isinstance(profiles, dict):
                profile_entry = profiles.get(profile_key)
                if not isinstance(profile_entry, dict):
                    return None
                region = profile_entry.get("normalized_board_region", {})
                if not all(key in region for key in required_keys):
                    return None
                return {
                    "version": calibration.get("version", 2),
                    "window_title": calibration.get("window_title", GAME_WINDOW_TITLE),
                    "profile": profile_key,
                    "normalized_board_region": region,
                    "saved_at": profile_entry.get("saved_at"),
                }

            # Backward compatibility: v1 format with single normalized region.
            region = calibration.get("normalized_board_region", {})
            if not all(key in region for key in required_keys):
                return None
            return calibration
        except Exception as e:
            print(f"[WARNING] Could not load board calibration: {e}")
            return None

    def _load_color_reference(self) -> Optional[dict]:
        """Load learned color reference if available."""
        color_ref_file = "color_reference.json"
        if not os.path.exists(color_ref_file):
            return None

        try:
            with open(color_ref_file, "r", encoding="utf-8") as f:
                color_ref = json.load(f)
            print("[ DEBUG] Loaded custom color reference from color_reference.json")
            return color_ref
        except Exception as e:
            print(f"[WARNING] Could not load color reference: {e}")
            return None

    def _save_board_calibration(
        self, normalized_region: dict, profile_override: str = ""
    ) -> bool:
        """Persist the normalized board region to disk."""
        profile_key = self._get_calibration_profile(profile_override)
        saved_at = time.strftime("%Y-%m-%d %H:%M:%S")

        payload = {
            "version": 2,
            "window_title": GAME_WINDOW_TITLE,
            "profiles": {
                profile_key: {
                    "normalized_board_region": normalized_region,
                    "saved_at": saved_at,
                }
            },
        }

        # Merge with existing file to preserve other mode profiles.
        if os.path.exists(CALIBRATION_FILE):
            try:
                with open(CALIBRATION_FILE, "r", encoding="utf-8") as handle:
                    existing = json.load(handle)
                if isinstance(existing, dict):
                    existing_profiles = existing.get("profiles")
                    if isinstance(existing_profiles, dict):
                        existing_profiles.update(payload["profiles"])
                        payload["profiles"] = existing_profiles
                        payload["window_title"] = existing.get(
                            "window_title", GAME_WINDOW_TITLE
                        )
                    else:
                        # Upgrade legacy single-profile file into profile map.
                        legacy_region = existing.get("normalized_board_region")
                        if isinstance(legacy_region, dict):
                            payload["profiles"].setdefault(
                                "classic",
                                {
                                    "normalized_board_region": legacy_region,
                                    "saved_at": existing.get("saved_at"),
                                },
                            )
                            payload["profiles"][profile_key] = {
                                "normalized_board_region": normalized_region,
                                "saved_at": saved_at,
                            }
            except Exception as e:
                print(f"[WARN] Failed to merge calibration profile: {e}")

        try:
            with open(CALIBRATION_FILE, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            self.board_calibration = {
                "version": payload.get("version", 2),
                "window_title": payload.get("window_title", GAME_WINDOW_TITLE),
                "profile": profile_key,
                "normalized_board_region": normalized_region,
                "saved_at": saved_at,
            }
            print(
                f"[CALIBRATION] Saved board calibration profile '{profile_key}' to {CALIBRATION_FILE}"
            )
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save calibration: {e}")
            return False

    def _get_calibrated_board_region(self) -> Optional[Tuple[int, int, int, int]]:
        """Convert the saved normalized calibration into screen coordinates."""
        if not self.board_calibration:
            return None

        client_rect = WindowManager.get_game_window_client_rect()
        if client_rect is None:
            return None

        client_x, client_y, client_w, client_h = client_rect
        if client_w <= 0 or client_h <= 0:
            return None

        region = self.board_calibration.get("normalized_board_region", {})
        left = float(region["left"])
        top = float(region["top"])
        right = float(region["right"])
        bottom = float(region["bottom"])

        x = int(client_x + left * client_w)
        y = int(client_y + top * client_h)
        w = int((right - left) * client_w)
        h = int((bottom - top) * client_h)

        if w <= 0 or h <= 0:
            return None

        return (x, y, w, h)

    def calibrate_board_region(self) -> bool:
        """Let the user drag-select the board area and save it as normalized coordinates."""
        profile_key = self._get_calibration_profile()
        print(f"[CALIBRATION] Calibrating board for '{profile_key}' mode profile")

        screenshot = self.capture_screenshot()
        if screenshot is None:
            return False

        client_rect = WindowManager.get_game_window_client_rect()
        if client_rect is None:
            print("[ERROR] Could not find the Bejeweled window client area")
            return False

        client_x, client_y, client_w, client_h = client_rect
        print(f"[CALIBRATION] Drag a rectangle around the full 8x8 board.")
        print(f"[CALIBRATION] This will be saved to the '{profile_key}' profile.")
        print("[CALIBRATION] Press ENTER or S to save, R to reset, or ESC/Q to cancel.")

        window_name = "Bejeweled Board Calibration"
        state = {
            "dragging": False,
            "start": None,
            "end": None,
            "selection": None,
        }

        def _redraw() -> np.ndarray:
            canvas = screenshot.copy()
            if state["start"] is not None and state["end"] is not None:
                cv2.rectangle(canvas, state["start"], state["end"], (0, 255, 0), 2)
            cv2.putText(
                canvas,
                "Drag board area, then press S/ENTER to save",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )
            cv2.putText(
                canvas,
                "R reset | ESC/Q cancel",
                (20, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )
            return canvas

        def _on_mouse(event, x, y, _flags, _param):
            if event == cv2.EVENT_LBUTTONDOWN:
                state["dragging"] = True
                state["start"] = (x, y)
                state["end"] = (x, y)
            elif event == cv2.EVENT_MOUSEMOVE and state["dragging"]:
                state["end"] = (x, y)
            elif event == cv2.EVENT_LBUTTONUP and state["dragging"]:
                state["dragging"] = False
                state["end"] = (x, y)
                x1 = min(state["start"][0], state["end"][0])
                y1 = min(state["start"][1], state["end"][1])
                x2 = max(state["start"][0], state["end"][0])
                y2 = max(state["start"][1], state["end"][1])
                state["selection"] = (x1, y1, x2, y2)

        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window_name, _on_mouse)

        try:
            while True:
                cv2.imshow(window_name, _redraw())
                key = cv2.waitKey(20) & 0xFF

                if key in (13, ord("s")) and state["selection"] is not None:
                    x1, y1, x2, y2 = state["selection"]
                    left = max(0.0, min(1.0, (x1 - client_x) / client_w))
                    top = max(0.0, min(1.0, (y1 - client_y) / client_h))
                    right = max(0.0, min(1.0, (x2 - client_x) / client_w))
                    bottom = max(0.0, min(1.0, (y2 - client_y) / client_h))

                    if right <= left or bottom <= top:
                        print(
                            "[CALIBRATION] Invalid selection. Drag a larger rectangle."
                        )
                        continue

                    normalized_region = {
                        "left": left,
                        "top": top,
                        "right": right,
                        "bottom": bottom,
                    }
                    if self._save_board_calibration(normalized_region):
                        self.board_region = self._get_calibrated_board_region()
                        return True

                elif key in (ord("r"),):
                    state["start"] = None
                    state["end"] = None
                    state["selection"] = None

                elif key in (27, ord("q")):
                    return False
        finally:
            cv2.destroyWindow(window_name)

    def find_board_region(
        self, screenshot: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Auto-detect the board region using gem color detection.

        Returns:
            (x, y, width, height) of the board region, or None if not found
        """
        # Convert to HSV for color-based detection
        hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)

        # Create mask for gem colors specifically
        # Gems are highly saturated, but we also need to filter by HUE ranges
        mask = np.zeros((hsv.shape[0], hsv.shape[1]), dtype=np.uint8)

        # Look for each gem color's hue range with high saturation
                # Red: 0-10, 170-180
        red_mask1 = cv2.inRange(hsv, np.array([0, HSV_MIN_SATURATION, HSV_MIN_VALUE]), np.array([10, 255, 255]))
        red_mask2 = cv2.inRange(
            hsv, np.array([170, HSV_MIN_SATURATION, HSV_MIN_VALUE]), np.array([180, 255, 255])
        )
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)

        # Orange/Yellow: 10-40
        orange_mask = cv2.inRange(
            hsv, np.array([10, HSV_MIN_SATURATION, HSV_MIN_VALUE]), np.array([40, 255, 255])
        )

        # Green: 40-90
        green_mask = cv2.inRange(hsv, np.array([40, HSV_MIN_SATURATION, HSV_MIN_VALUE]), np.array([90, 255, 255]))

        # Blue: 100-140
        blue_mask = cv2.inRange(
            hsv, np.array([100, HSV_MIN_SATURATION, HSV_MIN_VALUE]), np.array([140, 255, 255])
        )

        # Purple: 140-180
        purple_mask = cv2.inRange(
            hsv, np.array([140, HSV_MIN_SATURATION, HSV_MIN_VALUE]), np.array([170, 255, 255])
        )

        # Combine all gem color masks
        mask = cv2.bitwise_or(red_mask, orange_mask)
        mask = cv2.bitwise_or(mask, green_mask)
        mask = cv2.bitwise_or(mask, blue_mask)
        mask = cv2.bitwise_or(mask, purple_mask)

        # Apply morphological operations to clean up mask
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, BOARD_MORPH_KERNEL_SIZE)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            print("[ERROR] No gem regions found in screenshot")
            return None

        # Find the largest contour (should be the board area)
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)

        # Filter: board should be roughly square (8x8 gems)
        # Width and height should be similar
        if w < MIN_BOARD_PIXEL_DIM or h < MIN_BOARD_PIXEL_DIM:
            print(f"[WARNING] Detected region too small: {w}x{h}")
            return None

        aspect_ratio = max(w, h) / min(w, h)
        if aspect_ratio > MAX_BOARD_ASPECT_RATIO:
            print(f"[WARNING] Detected region has bad aspect ratio: {aspect_ratio:.2f}")
            # Don't fail - might still work

        # Add padding to ensure full board is captured
        padding = BOARD_DETECTION_PADDING
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(screenshot.shape[1] - x, w + 2 * padding)
        h = min(screenshot.shape[0] - y, h + 2 * padding)

        print(f"[DEBUG] Detected board region: x={x}, y={y}, w={w}, h={h}")

        return (x, y, w, h)

    def _detect_cell_gem(
        self,
        img: np.ndarray,
        cell_left: float,
        cell_top: float,
        cell_width: float,
        cell_height: float,
        row: Optional[int] = None,
        col: Optional[int] = None,
    ) -> tuple:
        """Compute average RGB across the cell and classify the gem.

        Returns: (gem_name, confidence)
        """
        x_start = max(0, int(cell_left))
        y_start = max(0, int(cell_top))
        x_end = min(img.shape[1], int(cell_left + cell_width))
        y_end = min(img.shape[0], int(cell_top + cell_height))

        if x_start >= x_end or y_start >= y_end:
            return "unknown", 0.0

        cell_region = img[y_start:y_end, x_start:x_end]
        if cell_region.size == 0:
            return "unknown", 0.0

        # 0. Hypercube pre-check (before template matching — hypercube's multi-colour
        #    pattern can false-match to star templates at low resolution)
        hyper_match, hyper_conf = self._classify_by_statistics(cell_region)
        if hyper_match != "unknown":
            return hyper_match, hyper_conf

        # 1. Template matching (catches normal gems, star gems, sometimes flame/star)
        template_match, template_confidence = self._classify_cell_by_template(
            cell_region
        )
        if template_match != "unknown":
            return template_match, template_confidence

        # 2. Flame-specific fallback (flame animation makes static template matching
        #    unreliable; top-brightness asymmetry is a robust alternative)
        flame_match, flame_conf = self._classify_flame_by_stats(cell_region)
        if flame_match != "unknown":
            return flame_match, flame_conf

        # 3. Compute the mean BGR across the cell (colour fallback for normal gems)
        avg_b = int(np.mean(cell_region[:, :, 0]))
        avg_g = int(np.mean(cell_region[:, :, 1]))
        avg_r = int(np.mean(cell_region[:, :, 2]))

        gem_type, confidence = self._classify_bgr_pixel(avg_b, avg_g, avg_r)

        # If low confidence (possible special gem/effect), save sample for offline template building
        if confidence < 0.45 and self.special_sample_count < self.max_special_samples:
            hint = f"r{row}_c{col}" if row is not None and col is not None else None
            self._save_special_sample(cell_region, hint=hint)

        return gem_type, confidence

    def _get_board_region(self, screenshot: np.ndarray) -> Optional[Tuple]:
        """
        Determine board region using (in order of preference):
        1. Saved manual calibration
        2. Pre-calibrated resolution config
        3. Auto-detection

        Sets self.board_region, self.cell_width, self.cell_height on success.
        Returns (board_x, board_y, width, height) or None if no region found.
        """
        # 1. Saved manual calibration (survives window resizes)
        region = self._get_calibrated_board_region()
        if region is not None:
            if DEBUG_MODE:
                print("[DEBUG] Using saved board calibration")
            board_x_offset, board_y_offset, w, h = region
            cell_width = w / BOARD_WIDTH
            cell_height = h / BOARD_HEIGHT
            self.board_region = region
            self.cell_width = cell_width
            self.cell_height = cell_height
            return region

        # 2. Pre-calibrated coordinates for known resolution
        if GAME_RESOLUTION in RESOLUTION_CONFIGS:
            cfg = RESOLUTION_CONFIGS[GAME_RESOLUTION]
            board_x_offset = cfg["board_x_offset"]
            board_y_offset = cfg["board_y_offset"]
            cell_width = cfg["cell_width"]
            cell_height = cfg["cell_height"]

            print(f"[DEBUG] Using pre-calibrated coords for {GAME_RESOLUTION}")
            w = BOARD_WIDTH * cell_width
            h = BOARD_HEIGHT * cell_height
            region = (board_x_offset, board_y_offset, w, h)
            self.board_region = region
            self.cell_width = cell_width
            self.cell_height = cell_height
            return region

        # 3. Auto-detect board region
        print(f"[DEBUG] Resolution '{GAME_RESOLUTION}' not pre-calibrated, auto-detecting...")
        region = self.find_board_region(screenshot)
        if region is None:
            print("[ERROR] Could not find game board in screenshot")
            return None

        board_x_offset, board_y_offset, w, h = region
        cell_width = w / BOARD_WIDTH
        cell_height = h / BOARD_HEIGHT
        self.board_region = region
        self.cell_width = cell_width
        self.cell_height = cell_height
        return region

    def _scan_board_cells(self, board_img: np.ndarray) -> np.ndarray:
        """Iterate all cells, classify gems, return 8x8 board array.

        Also populates self.last_confidences and returns the board.
        """
        board = np.zeros((BOARD_HEIGHT, BOARD_WIDTH), dtype=np.int8)
        for row in range(BOARD_HEIGHT):
            for col in range(BOARD_WIDTH):
                cell_left = col * self.cell_width
                cell_top = row * self.cell_height
                gem_color, conf = self._detect_cell_gem(
                    board_img, cell_left, cell_top,
                    self.cell_width, self.cell_height,
                    row=row, col=col,
                )
                gem_id = self.gem_type_map.get(gem_color, -1)
                board[row, col] = gem_id
                self.last_confidences[row, col] = float(conf)
        return board

    def get_board_state(self) -> Optional[np.ndarray]:
        """
        Detect board state using either:
        1. Saved manual calibration for resized windows
        2. Pre-calibrated coordinates for known resolutions
        3. Auto-detection if resolution unknown

        Returns:
            8x8 numpy array of gem type IDs, or None if failed
        """
        screenshot = self.capture_screenshot()
        if screenshot is None:
            return None

        try:
            # Phase 1: Determine board region
            region = self._get_board_region(screenshot)
            if region is None:
                return None

            # Phase 2: Extract board image
            rx, ry, rw, rh = region
            board_img = screenshot[ry: ry + int(rh), rx: rx + int(rw)]

            # Phase 3: Scan all cells to populate board
            board = self._scan_board_cells(board_img)
            detected_cells = int(np.sum(board >= 0))
            self.last_board = board
            self.last_coverage = detected_cells / float(BOARD_WIDTH * BOARD_HEIGHT)

            # Phase 4: Coverage check
            if self.last_coverage < MIN_BOARD_COVERAGE:
                print(
                    f"[WARNING] Low board coverage: {detected_cells}/{BOARD_WIDTH * BOARD_HEIGHT} cells ({self.last_coverage:.1%})"
                )
                return None

            # Phase 5: Debug
            if DEBUG_MODE:
                self._save_debug_screenshot(screenshot, region, board)

            return board

        except Exception as e:
            print(f"[ERROR] Board detection failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _save_debug_screenshot(
        self,
        screenshot: np.ndarray,
        region: Tuple[int, int, int, int],
        board: np.ndarray,
    ):
        """Save screenshot with grid overlay for debugging."""
        if not SAVE_DEBUG_SCREENSHOTS:
            return

        if self.debug_screenshot_count >= MAX_DEBUG_SCREENSHOTS:
            return

        os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)

        img_debug: np.ndarray = screenshot.copy()
        x, y, w, h = region

        # Draw board boundary
        cv2.rectangle(img_debug, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # Draw grid
        for row in range(BOARD_HEIGHT + 1):
            grid_y = int(y + row * self.cell_height)
            cv2.line(img_debug, (x, grid_y), (x + w, grid_y), (0, 200, 0), 1)  # type: ignore[arg-type]

        for col in range(BOARD_WIDTH + 1):
            grid_x = int(x + col * self.cell_width)
            cv2.line(img_debug, (grid_x, y), (grid_x, y + h), (0, 200, 0), 1)  # type: ignore[arg-type]

        # Add text labels for gem positions
        for row in range(BOARD_HEIGHT):
            for col in range(BOARD_WIDTH):
                cell_x = int(x + col * self.cell_width + self.cell_width / 2)
                cell_y = int(y + row * self.cell_height + self.cell_height / 2)

                gem_id = board[row, col]
                # Get color name from ID
                gem_color = (
                    list(self.gem_type_map.keys())[gem_id] if gem_id >= 0 else "?"
                )

                cv2.circle(img_debug, (cell_x, cell_y), 5, (255, 0, 0), -1)  # type: ignore[arg-type]
                cv2.putText(
                    img_debug,
                    gem_color[:1].upper(),
                    (cell_x - 8, cell_y + 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (0, 0, 255),
                    1,
                )  # type: ignore[arg-type]

            # Add a concise board summary on the image so gem verification is easy.
            summary_text = f"Coverage: {self.last_coverage:.1%} | Saved: {self.debug_screenshot_count + 1}/{MAX_DEBUG_SCREENSHOTS}"
            cv2.putText(
                img_debug,
                summary_text,
                (20, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 0),
                3,
            )  # type: ignore[arg-type]
            cv2.putText(
                img_debug,
                summary_text,
                (20, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                1,
            )  # type: ignore[arg-type]

        # Save with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(DEBUG_OUTPUT_DIR, f"board_debug_{timestamp}.png")
        cv2.imwrite(filepath, img_debug)
        self.debug_screenshot_count += 1
        print(f"[DEBUG] Screenshot saved: {filepath}")
