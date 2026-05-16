"""
Poker AI Player for Bejeweled 3 poker mode.

Uses GameLogic (classic match-3/cascade) for the base game and
PokerHandDetector as a strategic overlay to prefer moves that build
toward higher poker hands (pairs → full houses → flushes).

Scoring model (poker mode):
  total = hand_improvement * HAND_IMPROVEMENT_WEIGHT   # hand-type upgrade (primary)
        + cascade_score * CASCADE_WEIGHT               # cascade is tiebreaker only
        + board_potential * LOOKAHEAD_DISCOUNT          # follow-up valid-move count
        + board_poker_score * 0.05                       # board-level poker potential
"""

import numpy as np
from collections import Counter
from typing import Tuple, Optional, List
from game_logic import GameLogic
from poker_game_logic import PokerHandDetector
from config import NORMAL_GEM_COUNT


class PokerAIPlayer:
    """
    AI player for poker mode.
    Delegates match-3/cascade to GameLogic, then adds a poker-hand bonus
    so the AI favours moves that build high-value patterns.
    """

    LOOKAHEAD_DISCOUNT = 0.3        # weight of follow-up valid-move count
    POKER_BONUS_WEIGHT = 4.0        # how much to favour poker hand value (greedy)
    TARGET_MULTIPLIER = 3.0         # extra multiplier when a move REACHES/EXCEEDS the target hand

    # Hand-improvement scoring weights (primary signal in poker mode)
    HAND_IMPROVEMENT_WEIGHT = 10.0  # amplify hand-type upgrade (pair→three_oak = +7500*10)
    CASCADE_WEIGHT = 0.001          # cascade score is a tiebreaker only

    # Map gem ID (0-6) → lowercase single char for debug display.
    # Must match vision.py's sorted(GEM_COLORS.keys()) order:
    #   0=blue, 1=green, 2=orange, 3=purple, 4=red, 5=white, 6=yellow
    _ID_TO_CHAR = ['b', 'g', 'o', 'p', 'r', 'w', 'y']

    @staticmethod
    def _id_to_char(gem_id: int) -> str:
        """Convert a gem ID to a single lowercase character for debug display."""
        if 0 <= gem_id < len(PokerAIPlayer._ID_TO_CHAR):
            return PokerAIPlayer._ID_TO_CHAR[gem_id]
        return '?'

    def __init__(self, board: np.ndarray = None):
        self.logic = GameLogic(board)
        self.detector = PokerHandDetector()
        self.move_history: List[Tuple] = []
        self.score_history: List[int] = []
        self.hand_history: List[List[Tuple]] = []
        self._last_board: Optional[np.ndarray] = None     # memory
        self._last_poker_value: int = 0                   # memory

        # ---- Poker hand tracking (5 cards per hand) ----
        self._cards_colors: List[int] = []      # gem IDs of the 5 cards in this hand
        self._cards_hypercube: List[bool] = []  # parallel: True if the move created a hypercube
        self._move_count_in_hand: int = 0       # 0..5, resets after hand evaluation
        self._hands_completed: int = 0
        self._total_matches: int = 0

    # ------------------------------------------------------------------
    # Public API  (matches AIPlayer interface)
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_hand(cards: List[int]) -> str:
        """
        Classify the 5-card poker hand from a list of gem colour IDs.
        Returns hand type string (same keys as POKER_HAND_SCORES).
        """
        if not cards:
            return 'none'
        counts = Counter(cards)
        values = sorted(counts.values(), reverse=True)
        top = values[0] if values else 0
        if top >= 5:
            return 'flush'
        if top >= 4:
            return 'four_of_a_kind'
        if len(values) >= 2 and values[0] >= 3 and values[1] >= 2:
            return 'full_house'
        if top >= 3:
            return 'three_of_a_kind'
        if len(values) >= 2 and values[0] >= 2 and values[1] >= 2:
            return 'two_pair'
        if top >= 2:
            return 'pair'
        if len(cards) >= 5 and len(set(cards)) == 5:
            return 'spectrum'
        return 'none'

    def _simulate_matched_color(self, board: np.ndarray,
                                move: Tuple) -> Tuple[Optional[int], bool]:
        """
        Simulate *move* on a normalised board and return:
          (colour_id, creates_hypercube)  or  (None, False).
        `creates_hypercube` is True when the match shape is 5+ in a row
        (which would create a hypercube special gem in the actual game).
        """
        norm = PokerHandDetector._normalize(board)
        self.logic.set_board(norm)
        if not self.logic._is_valid_move(move):
            return None, False
        (r1, c1), (r2, c2) = move
        test = norm.copy()
        test[r1, c1], test[r2, c2] = test[r2, c2], test[r1, c1]
        matches = self.logic._find_all_matches(test)
        if matches:
            r, c = matches[0]
            gid = test[r, c]
            if 0 <= gid < NORMAL_GEM_COUNT:
                # Check if this match shape creates a hypercube (5+ in a row)
                shape = self.logic._analyze_match_shape(matches)
                return int(gid), (shape == 'hypercube')
        return None, False

    def _hand_improvement_score(self, matched_color: Optional[int]) -> int:
        """
        How much does adding *matched_color* to the current hand improve it?

        Returns the point-value difference between the new hand type and the
        current hand type (e.g. pair→three_of_a_kind = 10000 - 2500 = 7500).

        When the current hand is empty (0 cards), every colour gives the same
        improvement (none→pair = 2500), so this acts as a flat bonus — the
        tiebreaker signal (cascade + board potential) decides the first moves.
        When the current hand has 1+ cards, this strongly biases toward
        colours that upgrade the hand type.
        """
        if matched_color is None:
            return 0
        current_type = self._classify_hand(self._cards_colors)
        current_score = self.detector.score_hand(current_type)
        new_cards = self._cards_colors + [matched_color]
        new_type = self._classify_hand(new_cards)
        new_score = self.detector.score_hand(new_type)
        return new_score - current_score

    def get_ranked_moves(self, board: np.ndarray, top_n: int = 10) -> list:
        """
        Rank all valid moves by:
          cascade_score + follow-up potential + target-aware poker hand bonus.

        Strategy (greedy / plan-first):
           1. Normalise special gem IDs → base colours so star-gem moves
              don't get the (huge) star cascade bonus and don't pollute
              poker hand detection.
           2. Identify the best poker hand achievable from the CURRENT board
              (the "target") using hypercube-wildcard evaluation.
           3. For each move, evaluate the resulting board's poker potential
              (also with hypercube wildcards).
           4. If a move REACHES or EXCEEDS the target, apply TARGET_MULTIPLIER
              (3× the poker bonus) — strongly incentivises completing the hand.

        Returns list of (move, total_score) sorted descending.
        """
        # ---- Phase 0: Normalise special gems to base colours ----
        normalised = PokerHandDetector._normalize(board)
        self.logic.set_board(normalised)
        valid_moves = self.logic.find_valid_moves()
        if not valid_moves:
            return []

        # ---- Phase 1: Identify the target hand from the current board ----
        target_value = self.detector.evaluate_board_potential(board)

        # ---- Phase 2: Score each move ----
        move_scores = []
        for move in valid_moves:
            # ---------- a. Base cascade (on normalised board = no star bonus) ----------
            score, raw_final = self.logic.simulate_move(move)

            # ---------- b. Fill empty cells with random gems ----------
            rng = np.random.RandomState(42)
            filled = raw_final.copy()
            empty_mask = filled < 0
            if empty_mask.any():
                filled[empty_mask] = rng.randint(
                    0, NORMAL_GEM_COUNT, size=empty_mask.sum(), dtype=np.int8
                )

            # ---------- c. Classic follow-up potential ----------
            followup = self.logic.evaluate_board_potential(filled)

            # ---------- d. Poker value (hypercube-aware, normalised internally) ----------
            poker_val = self.detector.evaluate_board_potential(filled)

            # ---------- e. Greedy target-aware poker score ----------
            if target_value > 0 and poker_val >= target_value:
                poker_score = int(poker_val * self.TARGET_MULTIPLIER)
            elif poker_val > 0:
                poker_score = int(poker_val * self.POKER_BONUS_WEIGHT)
            else:
                poker_score = 0

            # ---------- f. Hand-improvement score (PRIMARY signal) ----------
            matched_color, _ = self._simulate_matched_color(board, move)
            hand_improvement = self._hand_improvement_score(matched_color)

            # ---------- g. Total (hand improvement dominates) ----------
            # Hand improvement is the primary signal (×10).
            # Cascade score is a tiebreaker (×0.001).
            # Board-level poker potential is a minor tiebreaker (×0.05).
            total = (hand_improvement * self.HAND_IMPROVEMENT_WEIGHT
                     + score * self.CASCADE_WEIGHT
                     + int(followup * self.LOOKAHEAD_DISCOUNT)
                     + poker_score * 0.05)
            move_scores.append((move, total))

        move_scores.sort(key=lambda x: x[1], reverse=True)
        return move_scores[:top_n]

    def track_move(self, board: np.ndarray,
                    move: Tuple[Tuple[int, int], Tuple[int, int]]) -> None:
        """
        Track a move's contribution to the current poker hand.

        Simulates what colour gem the move matches, appends it to the
        running 5-card hand, prints debug output, and resets when the
        hand is complete (5 moves).

        This is called by the bot controller AFTER it selects a move
        from the ranked list, ensuring hand tracking works during
        normal gameplay (not just via select_best_move).
        """
        matched_color, is_hypercube = self._simulate_matched_color(board, move)
        if matched_color is not None:
            self._cards_colors.append(matched_color)
            self._cards_hypercube.append(is_hypercube)
            self._move_count_in_hand += 1
            self._total_matches += 1

        # ---- Debug: print current hand ----
        hand_name = self._classify_hand(self._cards_colors)
        cards_abbr = ','.join(
            f"{self._id_to_char(c)}_h" if h else self._id_to_char(c)
            for c, h in zip(self._cards_colors, self._cards_hypercube)
        )
        print(f"  [Hand] Match {self._total_matches} | "
              f"Cards: [{cards_abbr}] | "
              f"Current: {hand_name} ({self.detector.score_hand(hand_name)} pts) | "
              f"Next eval in {5 - self._move_count_in_hand} moves")

        # ---- Hand complete? ----
        if self._move_count_in_hand >= 5:
            hand_score = self.detector.score_hand(hand_name)
            print(f"  [Hand] ** HAND COMPLETE ** {hand_name} = {hand_score} pts | "
                  f"Stack: [{cards_abbr}]")
            self._hands_completed += 1
            self.hand_history.append([(hand_name, tuple(self._cards_colors))])
            self._cards_colors = []
            self._cards_hypercube = []
            self._move_count_in_hand = 0

        # Memory: store current board + poker value for next iteration
        self._last_board = board.copy()
        self._last_poker_value = self.detector.evaluate_board_potential(board)


