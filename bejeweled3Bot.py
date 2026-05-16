"""
Main bot controller for Bejeweled 3.
Orchestrates vision, game logic, and AI player.
"""

import ctypes
from ctypes import wintypes
import pyautogui
import time
import threading
import config as cfg
from vision import BoardDetector
from ai_player import AIPlayer
from debug import BotLogger, BoardVisualizer
from config import MOVE_DELAY, DEBUG_MODE, LOG_MOVES, BOARD_WIDTH, BOARD_HEIGHT, HYPERCUBE_GEM_ID, STAR_GEM_OFFSET
from config import MIN_CELL_CONFIDENCE

# ADDED: Remove default pyautogui pause to speed up hardware execution
pyautogui.PAUSE = 0.0


HOTKEY_ID_TOGGLE_PAUSE = 1
HOTKEY_ID_QUIT = 2
HOTKEY_ID_STEP = 3
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
VK_SPACE = 0x20
VK_Q = 0x51


class BejewelBot:
    """Main bot controller."""

    def __init__(self):
        self.detector = BoardDetector()
        # Load appropriate AI player based on game mode
        if cfg.GAME_MODE == "poker":
            from poker_ai_player import PokerAIPlayer
            self.ai_player = PokerAIPlayer()
        else:
            self.ai_player = AIPlayer()
        self.logger = BotLogger() if LOG_MOVES else None
        self.move_count = 0
        self.last_move_time = 0
        self.game_active = False
        self.paused = False
        self.stop_requested = False
        self._hotkey_thread = None
        self._hotkey_thread_id = None
        self.last_move = None
        self.repeat_count = 0
        self.last_board_signature = None
        self.board_move_blacklist = {}
        self._global_blacklist = {}  # move -> remaining turns to skip

    def _board_signature(self, board) -> bytes:
        """Create a compact signature for the current board state."""
        return board.tobytes()

    def _hotkey_listener(self):
        """Pump Windows messages and react to global hotkey presses."""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._hotkey_thread_id = kernel32.GetCurrentThreadId()

        if not user32.RegisterHotKey(None, HOTKEY_ID_TOGGLE_PAUSE, 0, VK_SPACE):
            print("[BOT] Failed to register SPACE hotkey")
            return

        if not user32.RegisterHotKey(None, HOTKEY_ID_QUIT, 0, VK_Q):
            print("[BOT] Failed to register Q hotkey")
            user32.UnregisterHotKey(None, HOTKEY_ID_TOGGLE_PAUSE)
            return

        msg = wintypes.MSG()
        try:
            while self.game_active and not self.stop_requested:
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0 or result == -1:
                    break

                if msg.message == WM_HOTKEY:
                    if msg.wParam == HOTKEY_ID_TOGGLE_PAUSE:
                        self.paused = not self.paused
                        state = "paused" if self.paused else "resumed"
                        print(f"[BOT] {state.capitalize()} via SPACE hotkey")
                    elif msg.wParam == HOTKEY_ID_QUIT:
                        self.stop_requested = True
                        self.game_active = False
                        print("[BOT] Stop requested via Q hotkey")
                        break

                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID_TOGGLE_PAUSE)
            user32.UnregisterHotKey(None, HOTKEY_ID_QUIT)

    def _stop_hotkey_listener(self):
        """Wake the hotkey thread so it can exit cleanly."""
        if self._hotkey_thread_id is None:
            return

        try:
            ctypes.windll.user32.PostThreadMessageW(
                self._hotkey_thread_id, WM_QUIT, 0, 0
            )
        except Exception:
            pass

    def start(self, duration_seconds: int = 0):
        """
        Start the bot for specified duration.

        Args:
            duration_seconds: How long to run the bot (0 = unlimited)
        """
        if duration_seconds > 0:
            print(f"[BOT] Starting Bejeweled 3 Bot for {duration_seconds} seconds")
        else:
            print("[BOT] Starting Bejeweled 3 Bot (no time limit)")
            print("[BOT] Press Q to quit, SPACE to pause/resume")
        print("[BOT] Make sure the game window is focused and visible!")
        print("[BOT] Game can be any resolution (800x600, 1024x768, 1920x1200, etc.)")
        print("[BOT] Auto mode controls: SPACE pause/resume, Q quit")

        time.sleep(2)

        start_time = time.time()
        self.game_active = True
        self.paused = False
        self.stop_requested = False

        self._hotkey_thread = threading.Thread(
            target=self._hotkey_listener, daemon=True
        )
        self._hotkey_thread.start()

        try:
            while True:
                if (
                    duration_seconds > 0
                    and time.time() - start_time >= duration_seconds
                ):
                    print(f"[BOT] Duration limit of {duration_seconds}s reached")
                    break
                if not self.game_active:
                    break

                if self.paused:
                    while self.paused and self.game_active and not self.stop_requested:
                        time.sleep(0.1)
                    continue

                # Game loop iteration
                success = self._game_iteration()

                if not success:
                    print("[BOT] Game iteration failed, retrying...")
                    time.sleep(1)
                    continue

                # Check elapsed time
                if duration_seconds > 0:
                    elapsed = time.time() - start_time
                    print(f"[BOT] Elapsed: {elapsed:.1f}s / {duration_seconds}s")
                else:
                    elapsed = time.time() - start_time
                    print(f"[BOT] Elapsed: {elapsed:.1f}s (no limit)")

        except KeyboardInterrupt:
            print("\n[BOT] Bot interrupted by user")
        finally:
            self._stop_hotkey_listener()
            self._end_session()

    def _wait_for_board_stable(self, max_wait: float = 12.0) -> bool:
        """
        Poll until the board region pixels stabilise (cascades done).
        Uses bbox capture (only board region, not full screen) for speed.
        Returns True if stable, False if timed out.
        """
        import numpy as np
        from PIL import ImageGrab

        stable_count = 0
        required_stable = 6
        prev_region = None
        deadline = time.time() + max_wait

        region = self.detector.board_region
        if region is None:
            return False

        rx, ry, rw, rh = (int(x) for x in region)
        if rw <= 0 or rh <= 0:
            return False
        # Shrink for faster diff
        small_w, small_h = max(1, rw // 4), max(1, rh // 4)

        while time.time() < deadline:
            # Grab only the board region — vastly faster than full screen
            pil = ImageGrab.grab(bbox=(rx, ry, rx + rw, ry + rh))
            crop = np.array(pil.convert("L"))  # single-channel grayscale
            small = crop[::4, ::4]  # 1/4 scale, no interpolation needed

            if prev_region is not None:
                diff = np.mean(np.abs(small.astype(np.int16) - prev_region.astype(np.int16)))
                if diff < 3.0:
                    stable_count += 1
                    if stable_count >= required_stable:
                        return True
                else:
                    stable_count = 0

            prev_region = small
            time.sleep(0.05)

        print("[BOT] Board stability timeout — proceeding anyway")
        return False

    def _wait_for_board_detectable(self, max_wait: float = 18.0) -> bool:
        """
        Wait until get_board_state() returns a valid, recognizable board.

        Handles two poker-mode scenarios where the board region is visible
        but doesn't contain normal gems:
          1. Hand evaluation animation — plays after every 5th match (~3-5s)
          2. Skull coin flip — board goes dark unpredictably (~3-5s)

        Normal (non-poker) moves return immediately on first check since
        the board is already detectable after cascade settling.

        Returns True if board became detectable, False if timed out.
        """
        import numpy as np

        deadline = time.time() + max_wait
        last_report = 0.0
        attempt = 0

        while time.time() < deadline:
            attempt += 1

            board = self.detector.get_board_state()
            if board is not None and board.shape == (BOARD_HEIGHT, BOARD_WIDTH):
                # Require at least 50 % coverage to consider the board "detectable"
                valid_ratio = float(np.sum(board >= 0)) / float(board.size)
                if valid_ratio >= 0.50:
                    if attempt > 1:
                        elapsed = time.time() - (deadline - max_wait)
                        print(f"[BOT] Board became detectable after {elapsed:.1f}s")
                    return True

            elapsed = time.time() - (deadline - max_wait)
            if elapsed - last_report >= 3.0:
                remaining = deadline - time.time()
                print(f"[BOT] Board not detectable — waiting ({elapsed:.0f}s / {max_wait:.0f}s)...")
                last_report = elapsed

            time.sleep(0.5)

        print(f"[BOT] Board detectability timeout ({max_wait:.0f}s) — proceeding anyway")
        return False

    def _game_iteration(self) -> bool:
        """
        Single iteration of the game loop.
        Returns True if successful, False if error.
        """
        # 1. Capture board state
        board = self.detector.get_board_state()
        if board is None:
            print("[BOT] Failed to detect board state")
            return False

        # Validate board
        if board.shape != (BOARD_HEIGHT, BOARD_WIDTH):
            print(f"[BOT] Invalid board shape: {board.shape}")
            return False

        board_signature = self._board_signature(board)

        # Debug: print board state for visual validation
        if DEBUG_MODE:
            from debug import BoardVisualizer
            BoardVisualizer.print_board_detailed(
                board,
                self.detector.last_confidences,
                self.detector.gem_type_map,
            )

        # If the board is identical to the previous frame, the last move likely
        # failed to progress the board. Blacklist it so we try a different move.
        if self.last_board_signature == board_signature and self.last_move is not None:
            blacklist = self.board_move_blacklist.setdefault(board_signature, set())
            if self.last_move not in blacklist:
                blacklist.add(self.last_move)
                print(
                    f"[BOT] Board did not change after {self.last_move}; skipping that move"
                )
        self.last_board_signature = board_signature

        # 2. AI selects best move(s)
        ranked_moves = self.ai_player.get_ranked_moves(board, top_n=5)
        if not ranked_moves:
            print("[BOT] No valid moves found")
            return False

        blacklist = self.board_move_blacklist.setdefault(board_signature, set())

        # Only skip flame gems (7..13) in non-poker modes.
        # Poker mode has no special gems — vision might misclassify normal gems as flame,
        # which would incorrectly block every move involving that cell.
        special_gem_ids = set()
        if cfg.GAME_MODE != "poker":
            for r in range(BOARD_HEIGHT):
                for c in range(BOARD_WIDTH):
                    gid = board[r, c]
                    if self.detector.normal_gem_count <= gid < STAR_GEM_OFFSET:
                        special_gem_ids.add((r, c))

        # Decay global blacklist ticks
        expired = [m for m, t in self._global_blacklist.items() if t <= 0]
        for m in expired:
            del self._global_blacklist[m]
        self._global_blacklist = {m: t - 1 for m, t in self._global_blacklist.items() if t > 0}

        move = None
        selected_score = None
        for candidate_move, score in ranked_moves:
            if candidate_move in blacklist:
                continue
            if candidate_move in self._global_blacklist:
                print(f"[BOT] Globally blacklisted {candidate_move}, skipping")
                continue
            # Skip moves that touch low-confidence cells (possible special/effects)
            try:
                (ra, ca), (rb, cb) = candidate_move
                conf_a = float(self.detector.last_confidences[ra, ca])
                conf_b = float(self.detector.last_confidences[rb, cb])
                if conf_a < MIN_CELL_CONFIDENCE or conf_b < MIN_CELL_CONFIDENCE:
                    print(
                        f"[BOT] Skipping move {candidate_move} due to low confidence cells ({conf_a:.2f},{conf_b:.2f})"
                    )
                    continue
            except Exception:
                # If confidences unavailable, do not skip
                pass
            # Skip moves that involve special gems (flame, star, hypercube)
            if special_gem_ids:
                (ra, ca), (rb, cb) = candidate_move
                if (ra, ca) in special_gem_ids or (rb, cb) in special_gem_ids:
                    print(
                        f"[BOT] Skipping move {candidate_move} - involves a special gem"
                    )
                    continue
            if candidate_move == self.last_move:
                self.repeat_count += 1
                if self.repeat_count >= 3:
                    print(
                        f"[BOT] WARNING: Move {self.last_move} repeated {self.repeat_count} times, skipping to next best"
                    )
                    self.repeat_count = 0
                    blacklist.add(candidate_move)
                    continue  # Skip this move, try next
            else:
                self.repeat_count = 0

            move = candidate_move
            selected_score = score
            (r1, c1), (r2, c2) = move
            if cfg.GAME_MODE == "poker":
                print(f"[AI] Selected move: ({r1},{c1}) <-> ({r2},{c2})")
            else:
                print(f"[AI] Selected move: ({r1},{c1}) <-> ({r2},{c2}), Score: {score}")
            break

        if move is None:
            print(
                "[BOT] All top moves were already tried for this board, clearing retry list and re-evaluating"
            )
            blacklist.clear()
            fallback_move, fallback_score = ranked_moves[0]
            move = fallback_move
            selected_score = fallback_score
            (r1, c1), (r2, c2) = move
            if cfg.GAME_MODE == "poker":
                print(
                    f"[AI] Selected move: ({r1},{c1}) <-> ({r2},{c2})"
                )
            else:
                print(
                    f"[AI] Selected move: ({r1},{c1}) <-> ({r2},{c2}), Score: {selected_score}"
                )

        # Track this move
        self.last_move = move

        # Globally blacklist this move for 3 turns to force exploration
        # (skipped in poker mode — the AI needs freedom to chain same-color moves)
        if cfg.GAME_MODE != "poker":
            self._global_blacklist[move] = 3

        # 3. Debug output
        if DEBUG_MODE:
            coverage = self.detector.last_coverage * 100.0
            print(f"[BOT] Board coverage: {coverage:.1f}%")

        # 4. Save board state before executing (for later change detection)
        board_before = board.copy()
        board_before_sig = board_signature

        # 5. Execute move
        success = self._execute_move(move)
        if not success:
            print("[BOT] Failed to execute move")
            return False

        # 6. Wait for cascades to settle before the next iteration when enabled.
        if cfg.WAIT_FOR_BOARD_STABLE:
            self._wait_for_board_stable()

        # 7. Poker mode: handle hand evaluation animation (every 5 matches ~3-5s)
        #    and skull coin flip (board goes dark unpredictably).
        #    _wait_for_board_detectable returns immediately on normal moves
        #    since the board is already detectable.
        if cfg.GAME_MODE == "poker":
            self._wait_for_board_detectable(max_wait=18.0)

        # 8. Verify the board actually changed — if not, the move was invalid.
        board_after = self.detector.get_board_state()
        if board_after is not None:
            if self._board_signature(board_after) == board_before_sig:
                print(f"[BOT] Move {move} did not change the board — invalid, skipping")
                blacklist.add(move)
                return False

        # 9. Hand tracking (only after confirmed successful move)
        if cfg.GAME_MODE == "poker":
            self.ai_player.track_move(board_before, move)

        # 10. Log move
        self.move_count += 1
        if self.logger:
            self.logger.log_move(
                self.move_count,
                move,
                selected_score if selected_score is not None else 0,
                board_before,
            )

        return True

    def _execute_move(self, move: tuple) -> bool:
        """
        Execute a move by converting board coordinates to screen coordinates.

        Returns True if successful.
        """
        (r1, c1), (r2, c2) = move

        try:
            if self.detector.board_region is None:
                print("[ERROR] Board region not set")
                return False

            x, y, w, h = self.detector.board_region

            cell_width = w // BOARD_WIDTH
            cell_height = h // BOARD_HEIGHT

            x1 = x + c1 * cell_width + cell_width // 2
            y1 = y + r1 * cell_height + cell_height // 2

            x2 = x + c2 * cell_width + cell_width // 2
            y2 = y + r2 * cell_height + cell_height // 2

            print(f"[BOT] Executing move: ({r1},{c1}) -> ({r2},{c2})")

            # Optimised mouse execution: zero duration for instant movement
            pyautogui.moveTo(x1, y1, duration=0.0)
            pyautogui.dragTo(x2, y2, duration=0.05, button="left")

            time.sleep(0.1)  # Brief pause for swap to register; cascade wait is in _game_iteration

            # Move cursor off the board region so it doesn't obstruct the
            # subsequent screenshot / board detection.
            # Position: just above the board's top edge, horizontally centred.
            # Avoid screen corners (PyAutoGUI fail-safe triggers there).
            cursor_off_x = x + w // 2
            cursor_off_y = max(1, y - 30)
            pyautogui.moveTo(cursor_off_x, cursor_off_y, duration=0.0)
            return True

        except Exception as e:
            print(f"[ERROR] Failed to execute move: {e}")
            return False

    def _end_session(self):
        """End bot session."""
        print("\n" + "=" * 60)
        print("BOT SESSION ENDED")
        print(f"Total moves: {self.move_count}")
        print("=" * 60)

    def step_mode(self):
        """
        Step mode: SPACE executes one move, Q quits.
        Same hotkey system as auto mode, but moves one at a time.
        """
        print("[BOT] Entering step mode")
        print("[BOT] Controls: SPACE = one move, Q = quit")

        self.game_active = True
        self.paused = False
        self.stop_requested = False
        self._step_requested = False

        def _step_listener():
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            tid = kernel32.GetCurrentThreadId()

            if not user32.RegisterHotKey(None, HOTKEY_ID_STEP, 0, VK_SPACE):
                return
            if not user32.RegisterHotKey(None, HOTKEY_ID_QUIT, 0, VK_Q):
                user32.UnregisterHotKey(None, HOTKEY_ID_STEP)
                return

            msg = wintypes.MSG()
            try:
                while self.game_active and not self.stop_requested:
                    r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                    if r in (0, -1):
                        break
                    if msg.message == WM_HOTKEY:
                        if msg.wParam == HOTKEY_ID_STEP:
                            self._step_requested = True
                        elif msg.wParam == HOTKEY_ID_QUIT:
                            self.stop_requested = True
                            self.game_active = False
                            break
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
            finally:
                user32.UnregisterHotKey(None, HOTKEY_ID_STEP)
                user32.UnregisterHotKey(None, HOTKEY_ID_QUIT)

        thread = threading.Thread(target=_step_listener, daemon=True)
        thread.start()

        try:
            while self.game_active and not self.stop_requested:
                if self._step_requested:
                    self._step_requested = False
                    self._game_iteration()
                time.sleep(0.05)
        finally:
            self._stop_hotkey_listener()
            self._end_session()


def _select_game_mode() -> str:
    """Prompt user to pick game mode and update config."""
    gm = input("Select game mode (1=Classic/Zen, 2=Lightning/Ice Storm/Butterfly, 3=Poker): ").strip()
    if gm == "2":
        selected = "lightning"
    elif gm == "3":
        selected = "poker"
    else:
        selected = "classic"
    import config as cfg

    cfg.GAME_MODE = selected
    print(f"[CONFIG] Game mode set to '{selected}'")
    return selected


def main():
    """Main entry point."""
    print("Bejeweled 3 Bot")
    print("=" * 60)

    mode = (
        input("Select mode (1=Auto, 2=Step, 3=Test, 4=Calibrate board): ")
        .strip()
        .lower()
    )

    # Calibrate: ask game mode FIRST, before any window interaction
    if mode in ("4", "calibrate"):
        _select_game_mode()
        from vision import WindowManager, BoardDetector

        detector = BoardDetector()
        WindowManager.setup_window()
        detector.calibrate_board_region()
        return

    # Everything else: set game mode then create bot
    if mode in ("1", "auto", "2", "step", "3", "test"):
        _select_game_mode()

    bot = BejewelBot()

    if mode in ("1", "auto", ""):
        duration = input("Duration in seconds (ENTER for unlimited): ").strip()
        duration = int(duration) if duration.isdigit() else 0
        bot.start(duration)

    elif mode in ("2", "step"):
        bot.step_mode()

    elif mode in ("3", "test"):
        print("[TEST] Testing vision system...")
        board = bot.detector.get_board_state()
        if board is not None:
            print("[TEST] Board detected successfully!")
            BoardVisualizer.print_board_detailed(
                board,
                bot.detector.last_confidences,
                bot.detector.gem_type_map,
            )
        else:
            print("[TEST] Failed to detect board")

    else:
        print("Invalid mode")


if __name__ == "__main__":
    main()
