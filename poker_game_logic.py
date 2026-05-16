"""
Poker Hand Detection utilities for Bejeweled 3 poker mode.
NOT a game logic replacement — only detects and scores poker hand patterns
on a board state. The actual match-3 / cascade logic lives in game_logic.py.

Hand Patterns (actual Poker mode scoring per the game):
- Flush (5 of a kind): 50,000 points
- 4 of a kind: 30,000 points
- Full house (3 of one + 2 of another): 15,000 points
- 3 of a kind: 10,000 points
- 2 pair: 7,500 points
- Spectrum (5 different colors): 5,000 points
- Pair: 2,500 points

IMPORTANT: All public methods automatically normalize special gem IDs
(flame 7-13, star 14-20) back to their base colour (0-6) before
processing.  This means green gems and green-star gems are correctly
grouped together for poker hand detection.
"""

import numpy as np
from typing import List, Tuple, Set
from config import BOARD_WIDTH, BOARD_HEIGHT, NORMAL_GEM_COUNT, \
    STAR_GEM_OFFSET, HYPERCUBE_GEM_ID


class PokerHandDetector:
    """
    Stateless poker hand detection on a board array.
    Does NOT manage board state, cascades, gravity, or move validation.
    """

    POKER_HAND_SCORES = {
        'flush': 50000,
        'four_of_a_kind': 30000,
        'full_house': 15000,
        'three_of_a_kind': 10000,
        'two_pair': 7500,
        'spectrum': 5000,
        'pair': 2500,
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(board: np.ndarray) -> np.ndarray:
        """
        Map special gem IDs back to their base colour so poker detection
        treats, e.g., green (ID 3) and green-star (ID 17) as the same
        colour.
          - Flame gems (7-13) → base colour 0-6
          - Star gems (14-20) → base colour 0-6
          - Hypercube (21)     → unchanged (treated as wildcard)
          - Normal (0-6)       → unchanged
        """
        b = board.copy()
        # Flame: 7..13 → 0..6
        flame = (b >= NORMAL_GEM_COUNT) & (b < STAR_GEM_OFFSET)
        b[flame] = b[flame] - NORMAL_GEM_COUNT
        # Star: 14..20 → 0..6
        star = (b >= STAR_GEM_OFFSET) & (b < HYPERCUBE_GEM_ID)
        b[star] = b[star] - STAR_GEM_OFFSET
        return b

    def score_hand(self, hand_type: str) -> int:
        return self.POKER_HAND_SCORES.get(hand_type, 0)

    def detect_all(self, board: np.ndarray) -> List[Tuple[str, Tuple[Tuple[int, int], ...]]]:
        """
        Detect every poker hand pattern visible on *board*.
        Special gem IDs are normalised to base colours automatically.
        Returns list of (hand_type, cells) sorted by score descending.
        """
        b = self._normalize(board)
        hands = self.detect_connected_groups(b)
        full_houses = self.detect_full_house(b)
        two_pairs = self.detect_two_pair(b)
        spectrums = self.detect_spectrum(b)

        # De-duplicate: compound hands take priority over their component groups.
        compound_cells: Set[Tuple[int, int]] = set()
        result: List[Tuple[str, Tuple[Tuple[int, int], ...]]] = []
        for _, cells in full_houses + two_pairs:
            compound_cells.update(cells)

        for ht, cells in full_houses:
            result.append((ht, cells))
        for ht, cells in two_pairs:
            result.append((ht, cells))
        for ht, cells in spectrums:
            result.append((ht, cells))

        for ht, cells in hands:
            if not set(cells).issubset(compound_cells):
                result.append((ht, cells))

        result.sort(key=lambda x: self.score_hand(x[0]), reverse=True)
        return result

    def get_hypercube_colors(self, board: np.ndarray) -> Set[int]:
        """
        Return set of color IDs that have ≥5 instances on the board
        (after normalising special gems back to base colour).
        These colors CAN form a hypercube (match-5), which acts as a
        wildcard that can substitute for any color in a poker hand.
        """
        b = self._normalize(board)
        return {
            gid for gid in range(NORMAL_GEM_COUNT)
            if np.sum(b == gid) >= 5
        }

    def evaluate_board_potential(self, board: np.ndarray) -> int:
        """
        Score the poker-hand potential of a board (higher = richer setup).

        Special gem IDs are normalised to base colours automatically.
        Considers two evaluations and returns the best:
          1. Normal connected-group detection.
          2. Hypercube-wildcard estimation: if any colour has 5+ gems,
             that colour can form a hypercube that acts as ANY colour.
             This effectively adds +1 to the best non-hypercube colour
             group, potentially upgrading the hand tier.
        """
        if board is None or np.all(board < 0):
            return 0

        b = self._normalize(board)

        # --- 1. Normal detection ---
        hands = self.detect_all(b)
        normal_total = sum(self.score_hand(ht) for ht, _ in hands)

        # --- 2. Hypercube wildcard enhancement ---
        hc_colors = self.get_hypercube_colors(b)
        if not hc_colors:
            return normal_total

        # Count gems per non-hypercube colour
        counts: dict = {}
        for r in range(BOARD_HEIGHT):
            for c in range(BOARD_WIDTH):
                gid = b[r, c]
                if gid >= 0 and gid not in hc_colors:
                    counts[gid] = counts.get(gid, 0) + 1

        # If only hypercube colours exist, the board still has some value
        if not counts:
            return max(normal_total, len(hc_colors) * 100)

        sorted_counts = sorted(counts.values(), reverse=True)
        top = sorted_counts[0]

        # Hypercube acts as wildcard → effectively +1 to the best colour
        top_plus = top + 1

        hyper_best = 0
        if top_plus >= 5:
            hyper_best = self.score_hand('flush')
        elif top_plus >= 4:
            hyper_best = self.score_hand('four_of_a_kind')

        # Full house potential: hypercube can make a 2 into 3 (or 3 into 4)
        # alongside another group of 2+
        if len(sorted_counts) >= 2:
            if sorted_counts[0] >= 3 and sorted_counts[1] >= 2:
                hyper_best = max(hyper_best, self.score_hand('full_house'))
            elif sorted_counts[0] >= 2 and sorted_counts[1] >= 2:
                hyper_best = max(hyper_best, self.score_hand('full_house'))

        return max(normal_total, hyper_best)

    # ------------------------------------------------------------------
    # Connected-group detection  (pairs, 3-of-a-kind, 4-of-a-kind, flush)
    # ------------------------------------------------------------------

    def detect_connected_groups(self, board: np.ndarray
                                ) -> List[Tuple[str, Tuple[Tuple[int, int], ...]]]:
        """Find connected same-colour groups (size ≥ 2) and label their hand type."""
        visited: Set[Tuple[int, int]] = set()
        result = []
        for r in range(BOARD_HEIGHT):
            for c in range(BOARD_WIDTH):
                if (r, c) in visited or board[r, c] < 0:
                    continue
                group = self._flood_fill(board, r, c)
                if len(group) >= 2:
                    visited.update(group)
                    ht = self._classify_group_size(len(group))
                    if ht:
                        result.append((ht, tuple(sorted(group))))
        return result

    def _flood_fill(self, board: np.ndarray, sr: int, sc: int) -> List[Tuple[int, int]]:
        gid = board[sr, sc]
        if gid < 0:
            return []
        group = [(sr, sc)]
        seen = {(sr, sc)}
        q = [(sr, sc)]
        while q:
            r, c = q.pop()
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < BOARD_HEIGHT and 0 <= nc < BOARD_WIDTH \
                   and (nr, nc) not in seen and board[nr, nc] == gid:
                    seen.add((nr, nc))
                    group.append((nr, nc))
                    q.append((nr, nc))
        return group

    @staticmethod
    def _classify_group_size(n: int) -> str:
        if n == 2:
            return 'pair'
        if n == 3:
            return 'three_of_a_kind'
        if n == 4:
            return 'four_of_a_kind'
        if n >= 5:
            return 'flush'
        return ''

    # ------------------------------------------------------------------
    # Compound-hand detection  (full house, two pair)
    # ------------------------------------------------------------------

    def detect_full_house(self, board: np.ndarray
                          ) -> List[Tuple[str, Tuple[Tuple[int, int], ...]]]:
        """Find a group-of-3 adjacent to a group-of-2 of a different colour."""
        groups = self._collect_groups(board, min_size=2)
        result = []
        gids = sorted(groups.keys())
        for i, g1 in enumerate(gids):
            for g2 in gids[i + 1:]:
                for ga in groups[g1]:
                    for gb in groups[g2]:
                        if len(ga) == 3 and len(gb) == 2 and self._adjacent(ga, gb):
                            result.append(('full_house', tuple(ga + gb)))
                        elif len(ga) == 2 and len(gb) == 3 and self._adjacent(ga, gb):
                            result.append(('full_house', tuple(ga + gb)))
        return result

    def detect_two_pair(self, board: np.ndarray
                        ) -> List[Tuple[str, Tuple[Tuple[int, int], ...]]]:
        """Find two size-2 groups of different colours that are adjacent."""
        groups = self._collect_groups(board, min_size=2, max_size=2)
        result = []
        gids = sorted(groups.keys())
        for i, g1 in enumerate(gids):
            for g2 in gids[i + 1:]:
                for ga in groups[g1]:
                    for gb in groups[g2]:
                        if self._adjacent(ga, gb):
                            result.append(('two_pair', tuple(ga + gb)))
        return result

    def _collect_groups(self, board: np.ndarray, min_size: int = 2, max_size: int = 99
                        ) -> dict:
        visited: Set[Tuple[int, int]] = set()
        out: dict = {}
        for r in range(BOARD_HEIGHT):
            for c in range(BOARD_WIDTH):
                if (r, c) in visited or board[r, c] < 0:
                    continue
                group = self._flood_fill(board, r, c)
                if min_size <= len(group) <= max_size:
                    visited.update(group)
                    gid = board[r, c]
                    out.setdefault(gid, []).append(group)
        return out

    @staticmethod
    def _adjacent(a: List[Tuple[int, int]], b: List[Tuple[int, int]]) -> bool:
        for r1, c1 in a:
            for r2, c2 in b:
                if abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1 and (r1, c1) != (r2, c2):
                    return True
        return False

    # ------------------------------------------------------------------
    # Spectrum detection  (5 different colours in a straight line)
    # ------------------------------------------------------------------

    def detect_spectrum(self, board: np.ndarray
                        ) -> List[Tuple[str, Tuple[Tuple[int, int], ...]]]:
        """5 different gem types in a contiguous horizontal or vertical run."""
        result = []
        for r in range(BOARD_HEIGHT):
            for c in range(BOARD_WIDTH - 4):
                cells = [(r, c + i) for i in range(5)]
                vals = [board[r, c + i] for i in range(5)]
                if all(v >= 0 for v in vals) and len(set(vals)) == 5:
                    result.append(('spectrum', tuple(cells)))
        for c in range(BOARD_WIDTH):
            for r in range(BOARD_HEIGHT - 4):
                cells = [(r + i, c) for i in range(5)]
                vals = [board[r + i, c] for i in range(5)]
                if all(v >= 0 for v in vals) and len(set(vals)) == 5:
                    result.append(('spectrum', tuple(cells)))
        return result
