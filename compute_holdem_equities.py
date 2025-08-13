#!/usr/bin/env python3
import os
import random
import time
from typing import List, Optional, Tuple


RANKS_TYPE = "AKQJT98765432"  # for hand-type labels (high to low)
RANKS_DECK = "23456789TJQKA"   # for building the deck (low to high ordering irrelevant)
SUITS = "cdhs"
FULL_DECK_CODES = [f"{r}{s}" for r in RANKS_DECK for s in SUITS]
RANK_CHAR_TO_VALUE = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
    '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
}


def _find_straight_top(ranks: List[int]) -> int:
    vals = sorted(set(ranks))
    if 14 in vals:
        vals = [1] + vals  # Handle wheel straight A-2-3-4-5
    best_top = 0
    run_len = 1
    for i in range(len(vals) - 1):
        if vals[i + 1] - vals[i] == 1:
            run_len += 1
        else:
            run_len = 1
        if run_len >= 5:
            best_top = max(best_top, vals[i + 1])
    return best_top


def _evaluate_7(cards: List[str]) -> Tuple[int, Tuple[int, ...]]:
    ranks = [RANK_CHAR_TO_VALUE[c[0]] for c in cards]
    suits = [c[1] for c in cards]

    counts: dict = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    unique_ranks_desc = sorted(set(ranks), reverse=True)

    # Flush and Straight Flush
    suit_to_ranks: dict = {}
    for r, s in zip(ranks, suits):
        suit_to_ranks.setdefault(s, []).append(r)
    flush_suit = None
    for s, rs in suit_to_ranks.items():
        if len(rs) >= 5:
            flush_suit = s
            break
    if flush_suit is not None:
        rs = suit_to_ranks[flush_suit]
        top_sf = _find_straight_top(rs)
        if top_sf > 0:
            return 8, (top_sf,)

    # Four of a Kind
    quads = [r for r, cnt in counts.items() if cnt == 4]
    if quads:
        quad = max(quads)
        kickers = [r for r in unique_ranks_desc if r != quad]
        return 7, (quad, kickers[0])

    # Full House
    trips = sorted([r for r, cnt in counts.items() if cnt >= 3], reverse=True)
    if trips:
        remaining_pairs = sorted([r for r, cnt in counts.items() if r != trips[0] and cnt >= 2], reverse=True)
        if len(trips) >= 2:
            return 6, (trips[0], trips[1])
        if remaining_pairs:
            return 6, (trips[0], remaining_pairs[0])

    # Flush
    if flush_suit is not None:
        rs = sorted(suit_to_ranks[flush_suit], reverse=True)[:5]
        return 5, tuple(rs)

    # Straight
    top_st = _find_straight_top(unique_ranks_desc)
    if top_st > 0:
        return 4, (top_st,)

    # Three of a Kind
    if trips:
        trip = trips[0]
        kickers = [r for r in unique_ranks_desc if r != trip][:2]
        return 3, (trip, kickers[0], kickers[1])

    # Two Pair
    pairs = sorted([r for r, cnt in counts.items() if cnt >= 2], reverse=True)
    if len(pairs) >= 2:
        high_pair, low_pair = pairs[0], pairs[1]
        kicker_candidates = [r for r in unique_ranks_desc if r != high_pair and r != low_pair]
        kicker = kicker_candidates[0] if kicker_candidates else 0
        return 2, (high_pair, low_pair, kicker)

    # One Pair
    if len(pairs) == 1:
        pair = pairs[0]
        kickers = [r for r in unique_ranks_desc if r != pair][:3]
        while len(kickers) < 3:
            kickers.append(0)
        return 1, (pair, kickers[0], kickers[1], kickers[2])

    # High Card
    top5 = unique_ranks_desc[:5]
    while len(top5) < 5:
        top5.append(0)
    return 0, tuple(top5)


def generate_starting_hand_types() -> List[str]:
    types: List[str] = []
    for i, r1 in enumerate(RANKS_TYPE):
        for j, r2 in enumerate(RANKS_TYPE):
            if i == j:
                types.append(f"{r1}{r2}")
            elif i < j:
                types.append(f"{r1}{r2}s")
                types.append(f"{r1}{r2}o")
    return types


def try_pick_hand(available: set, hand_type: str, rng: random.Random) -> Optional[List[str]]:
    # Pair like 'AA'
    if len(hand_type) == 2:
        rank = hand_type[0]
        suits_avail = [s for s in SUITS if f"{rank}{s}" in available]
        if len(suits_avail) < 2:
            return None
        s1, s2 = rng.sample(suits_avail, 2)
        return [f"{rank}{s1}", f"{rank}{s2}"]

    r1, r2, suited_flag = hand_type[0], hand_type[1], hand_type[2]
    if suited_flag == "s":
        candidate_suits = [s for s in SUITS if f"{r1}{s}" in available and f"{r2}{s}" in available]
        if not candidate_suits:
            return None
        s = rng.choice(candidate_suits)
        return [f"{r1}{s}", f"{r2}{s}"]
    else:
        suits_r1 = [s for s in SUITS if f"{r1}{s}" in available]
        suits_r2 = [s for s in SUITS if f"{r2}{s}" in available]
        combos = [(a, b) for a in suits_r1 for b in suits_r2 if a != b]
        if not combos:
            return None
        a, b = rng.choice(combos)
        return [f"{r1}{a}", f"{r2}{b}"]


def simulate_equity_for_pair(hand_type_1: str, hand_type_2: str, num_trials: int, rng: random.Random) -> Tuple[float, float, int]:
    # Returns (equity1, equity2, trials_done)
    wins1 = 0.0
    wins2 = 0.0
    trials_done = 0

    while trials_done < num_trials:
        success = False
        for _ in range(32):  # few attempts to find non-overlapping suit instantiations
            available = set(FULL_DECK_CODES)

            pick1 = try_pick_hand(available, hand_type_1, rng)
            if pick1 is None:
                continue
            for c in pick1:
                available.remove(c)

            pick2 = try_pick_hand(available, hand_type_2, rng)
            if pick2 is None:
                continue
            for c in pick2:
                available.remove(c)

            board = rng.sample(list(available), 5)
            cards1_codes = pick1 + board
            cards2_codes = pick2 + board

            score1 = _evaluate_7(cards1_codes)
            score2 = _evaluate_7(cards2_codes)

            if score1 > score2:
                wins1 += 1.0
            elif score2 > score1:
                wins2 += 1.0
            else:
                wins1 += 0.5
                wins2 += 0.5

            trials_done += 1
            success = True
            break
        if not success:
            # For safety break to avoid infinite loop on impossible combos
            break

    if trials_done == 0:
        return 0.5, 0.5, 0

    equity1 = wins1 / trials_done
    equity2 = wins2 / trials_done
    return equity1, equity2, trials_done


def main():
    sims_per_pair_env = os.environ.get("SIMS_PER_PAIR", "30").strip()
    try:
        sims_per_pair = int(sims_per_pair_env)
    except ValueError:
        sims_per_pair = 100

    output_file = os.environ.get("OUTPUT_FILE", "/workspace/holdem_equities.txt").strip()

    rng = random.Random()
    rng.seed(20250813)

    hand_types = generate_starting_hand_types()

    start = time.time()
    lines_written = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for i, h1 in enumerate(hand_types):
            for j in range(i, len(hand_types)):
                h2 = hand_types[j]
                eq1, eq2, trials = simulate_equity_for_pair(h1, h2, sims_per_pair, rng)
                if trials == 0:
                    continue
                f.write(f"玩家1 | {h1} | {eq1:.4f} | 玩家2 | {h2} | {eq2:.4f}\n")
                lines_written += 1

    elapsed = time.time() - start
    print(f"完成: 写入 {lines_written} 行到 {output_file}，每对 {sims_per_pair} 次模拟，用时 {elapsed:.1f}s")


if __name__ == "__main__":
    main()