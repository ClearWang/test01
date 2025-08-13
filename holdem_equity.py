import argparse
import itertools
import math
import os
import random
import sys
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

RankChar = str
SuitChar = str
Card = Tuple[int, str]  # (rank_value 2..14, suit 's','h','d','c')
HandType = str  # e.g., 'AKs', 'AKo', 'AA'


RANKS: List[RankChar] = [
    'A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'
]
RANK_VALUE: Dict[RankChar, int] = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14,
}
SUITS: List[SuitChar] = ['s', 'h', 'd', 'c']

FULL_DECK: List[Card] = [(RANK_VALUE[r], s) for r in reversed(list(RANK_VALUE.keys())) for s in SUITS]
# The above reversed puts ranks 14..2 to match value ordering, but order does not matter for simulation
FULL_DECK_SET: set = set(FULL_DECK)


def generate_all_hand_types() -> List[HandType]:
    hand_types: List[HandType] = []
    for i, r1 in enumerate(RANKS):
        for j, r2 in enumerate(RANKS):
            if i == j:
                hand_types.append(f"{r1}{r2}")
            elif i < j:
                hand_types.append(f"{r1}{r2}s")
            else:
                hand_types.append(f"{r2}{r1}o")
    return hand_types


def is_valid_hand_type(hand_type: str) -> bool:
    if len(hand_type) == 2:
        a, b = hand_type[0], hand_type[1]
        return a in RANK_VALUE and b in RANK_VALUE and a == b
    if len(hand_type) == 3:
        a, b, su = hand_type[0], hand_type[1], hand_type[2]
        if a not in RANK_VALUE or b not in RANK_VALUE:
            return False
        if a == b:
            return False
        return su in ('s', 'o')
    return False


def canonicalize_hand_type(hand_type: str) -> HandType:
    hand_type = hand_type.strip().upper()
    if len(hand_type) == 2:
        a, b = hand_type[0], hand_type[1]
        if a not in RANK_VALUE or b not in RANK_VALUE:
            raise ValueError(f"Invalid hand type: {hand_type}")
        if a != b:
            raise ValueError(f"Invalid pair type: {hand_type}")
        return f"{a}{b}"
    if len(hand_type) != 3:
        raise ValueError(f"Invalid hand type: {hand_type}")
    a, b, su = hand_type[0], hand_type[1], hand_type[2]
    if a not in RANK_VALUE or b not in RANK_VALUE or su not in ('S', 'O', 's', 'o'):
        raise ValueError(f"Invalid hand type: {hand_type}")
    su = su.lower()
    if a == b:
        raise ValueError(f"Invalid suited/off type with same ranks: {hand_type}")
    # Ensure the higher rank is first
    ai = RANKS.index(a)
    bi = RANKS.index(b)
    if ai < bi:
        return f"{a}{b}{su}"
    else:
        return f"{b}{a}{su}"


def combos_for_type(hand_type: HandType, deck_cards: Optional[set] = None) -> List[Tuple[Card, Card]]:
    """
    Return all 2-card combinations (unordered pairs as tuples) that match the given hand type
    and are available in deck_cards. If deck_cards is None, assume a fresh full deck.
    """
    if deck_cards is None:
        deck_cards = FULL_DECK_SET
    hand_type = canonicalize_hand_type(hand_type)
    combos: List[Tuple[Card, Card]] = []
    if len(hand_type) == 2:
        r = RANK_VALUE[hand_type[0]]
        suits_avail = [s for s in SUITS if (r, s) in deck_cards]
        for s1_i in range(len(suits_avail)):
            for s2_i in range(s1_i + 1, len(suits_avail)):
                s1 = suits_avail[s1_i]
                s2 = suits_avail[s2_i]
                combos.append(((r, s1), (r, s2)))
        return combos
    a, b, su = hand_type[0], hand_type[1], hand_type[2]
    ra = RANK_VALUE[a]
    rb = RANK_VALUE[b]
    if su == 's':
        for s in SUITS:
            ca = (ra, s)
            cb = (rb, s)
            if ca in deck_cards and cb in deck_cards:
                # To keep representation consistent, always keep higher-rank card first in tuple
                combos.append(((ra, s), (rb, s)))
    else:  # offsuit
        for sa in SUITS:
            if (ra, sa) not in deck_cards:
                continue
            for sb in SUITS:
                if sa == sb:
                    continue
                cb = (rb, sb)
                if cb in deck_cards:
                    combos.append(((ra, sa), (rb, sb)))
    return combos


def are_disjoint(combo1: Tuple[Card, Card], combo2: Tuple[Card, Card]) -> bool:
    cset1 = set(combo1)
    return (combo2[0] not in cset1) and (combo2[1] not in cset1)


def enumerate_disjoint_combo_pairs(t1: HandType, t2: HandType) -> List[Tuple[Tuple[Card, Card], Tuple[Card, Card]]]:
    c1 = combos_for_type(t1, FULL_DECK_SET)
    c2 = combos_for_type(t2, FULL_DECK_SET)
    pairs: List[Tuple[Tuple[Card, Card], Tuple[Card, Card]]] = []
    for a in c1:
        aset = set(a)
        for b in c2:
            if (b[0] not in aset) and (b[1] not in aset):
                pairs.append((a, b))
    return pairs


def draw_random_board(excluded_cards: Sequence[Card], rng: random.Random) -> List[Card]:
    excluded = set(excluded_cards)
    deck = [c for c in FULL_DECK if c not in excluded]
    return rng.sample(deck, 5)


# Hand evaluation
HAND_CATEGORY_RANK = {
    'high_card': 0,
    'one_pair': 1,
    'two_pair': 2,
    'three_of_a_kind': 3,
    'straight': 4,
    'flush': 5,
    'full_house': 6,
    'four_of_a_kind': 7,
    'straight_flush': 8,
}


def evaluate_best_hand(cards7: Sequence[Card]) -> Tuple[int, Tuple[int, ...]]:
    """
    Evaluate 7 cards and return a comparable tuple (category_rank, tiebreakers...)
    Higher tuple is better in lexicographic comparison.
    """
    ranks = [r for (r, s) in cards7]
    suits = [s for (r, s) in cards7]

    rank_counts: Dict[int, int] = Counter(ranks)
    suit_counts: Dict[str, int] = Counter(suits)

    # Utility: get sorted unique ranks desc
    unique_ranks_desc: List[int] = sorted(set(ranks), reverse=True)

    # Helper to detect straight given a set of ranks
    def straight_high_rank(ranks_set: set) -> Optional[int]:
        if 14 in ranks_set:
            ranks_set = set(ranks_set)
            ranks_set.add(1)  # Ace low
        ordered = sorted(ranks_set)
        run = 0
        last = None
        best_high = None
        for r in ordered:
            if last is None or r == last + 1:
                run += 1
            elif r == last:
                pass
            else:
                run = 1
            if run >= 5:
                best_high = r
            last = r
        return best_high

    # Check for straight flush
    straight_flush_high: Optional[int] = None
    for suit, cnt in suit_counts.items():
        if cnt >= 5:
            suit_ranks = {r for (r, s) in cards7 if s == suit}
            sh = straight_high_rank(suit_ranks)
            if sh is not None:
                if straight_flush_high is None or sh > straight_flush_high:
                    straight_flush_high = sh
    if straight_flush_high is not None:
        return HAND_CATEGORY_RANK['straight_flush'], (straight_flush_high,)

    # Four of a kind
    quads = [r for r, c in rank_counts.items() if c == 4]
    if quads:
        quad_rank = max(quads)
        kicker = max([r for r in unique_ranks_desc if r != quad_rank])
        return HAND_CATEGORY_RANK['four_of_a_kind'], (quad_rank, kicker)

    # Full house
    trips = sorted([r for r, c in rank_counts.items() if c == 3], reverse=True)
    pairs = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
    if trips and (len(trips) >= 2 or pairs):
        top_trip = trips[0]
        if len(trips) >= 2:
            second = trips[1]
            return HAND_CATEGORY_RANK['full_house'], (top_trip, second)
        else:
            return HAND_CATEGORY_RANK['full_house'], (top_trip, pairs[0])

    # Flush
    flush_suit: Optional[str] = None
    for suit, cnt in suit_counts.items():
        if cnt >= 5:
            flush_suit = suit
            break
    if flush_suit is not None:
        flush_cards = sorted([r for (r, s) in cards7 if s == flush_suit], reverse=True)
        top5 = tuple(flush_cards[:5])
        return HAND_CATEGORY_RANK['flush'], top5

    # Straight
    sh = straight_high_rank(set(ranks))
    if sh is not None:
        return HAND_CATEGORY_RANK['straight'], (sh,)

    # Three of a kind
    if trips:
        trip = trips[0]
        kickers = [r for r in unique_ranks_desc if r != trip]
        return HAND_CATEGORY_RANK['three_of_a_kind'], (trip, kickers[0], kickers[1])

    # Two pair
    if len(pairs) >= 2:
        high_pair = pairs[0]
        low_pair = pairs[1]
        kicker = max([r for r in unique_ranks_desc if r != high_pair and r != low_pair])
        return HAND_CATEGORY_RANK['two_pair'], (high_pair, low_pair, kicker)

    # One pair
    if len(pairs) == 1:
        pair = pairs[0]
        kickers = [r for r in unique_ranks_desc if r != pair]
        return HAND_CATEGORY_RANK['one_pair'], (pair, kickers[0], kickers[1], kickers[2])

    # High card
    top5 = tuple(unique_ranks_desc[:5])
    return HAND_CATEGORY_RANK['high_card'], top5


def compare_7cards(a7: Sequence[Card], b7: Sequence[Card]) -> int:
    ra = evaluate_best_hand(a7)
    rb = evaluate_best_hand(b7)
    if ra > rb:
        return 1
    if rb > ra:
        return -1
    return 0


def simulate_matchup(
    t1: HandType,
    t2: HandType,
    trials: int,
    seed: Optional[int] = None,
) -> Tuple[HandType, HandType, float, float]:
    rng = random.Random(seed)
    pairs = enumerate_disjoint_combo_pairs(t1, t2)
    if not pairs:
        # No legal disjoint combo pairs (should rarely happen); treat as 0.5 each
        return t1, t2, 0.5, 0.5

    wins1 = 0
    wins2 = 0
    ties = 0
    for _ in range(trials):
        a, b = rng.choice(pairs)
        excluded = [a[0], a[1], b[0], b[1]]
        board = draw_random_board(excluded, rng)
        res = compare_7cards([a[0], a[1]] + board, [b[0], b[1]] + board)
        if res > 0:
            wins1 += 1
        elif res < 0:
            wins2 += 1
        else:
            ties += 1
    total = float(trials)
    eq1 = (wins1 + 0.5 * ties) / total
    eq2 = (wins2 + 0.5 * ties) / total
    return t1, t2, eq1, eq2


def parse_hand_types_arg(text: str) -> List[HandType]:
    parts = [p.strip() for p in text.split(',') if p.strip()]
    if not parts:
        return []
    out: List[HandType] = []
    for p in parts:
        out.append(canonicalize_hand_type(p))
    return out


def chunked(iterable: Iterable, size: int) -> Iterable[List]:
    chunk: List = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            '计算两位玩家德州扑克牌力（起手牌类型对阵）Monte Carlo 胜率并写入文本文件。\n'
            '输出格式：玩家1 | 牌型 | 盈率 | 玩家2 | 牌型 | 赢率'
        )
    )
    parser.add_argument('--all', action='store_true', help='对 169 x 169 所有起手牌类型进行计算')
    parser.add_argument('--player1-hands', type=str, default='', help='玩家1 起手牌类型列表（逗号分隔），例如 AKs,QQ,72o')
    parser.add_argument('--player2-hands', type=str, default='', help='玩家2 起手牌类型列表（逗号分隔），例如 AKo,JJ')
    parser.add_argument('--trials-per-matchup', type=int, default=500, help='每个对阵的 Monte Carlo 抽样次数（越大越准确，越慢）')
    parser.add_argument('--output', type=str, default='/workspace/equities.txt', help='输出文本路径')
    parser.add_argument('--seed', type=int, default=42, help='随机种子（用于复现）')
    parser.add_argument('--processes', type=int, default=1, help='并行进程数，1 表示单进程')

    args = parser.parse_args(argv)

    if args.all:
        p1_types = generate_all_hand_types()
        p2_types = generate_all_hand_types()
    else:
        p1_types = parse_hand_types_arg(args.player1_hands) if args.player1_hands else generate_all_hand_types()
        p2_types = parse_hand_types_arg(args.player2_hands) if args.player2_hands else generate_all_hand_types()

    # Build task list
    tasks: List[Tuple[HandType, HandType]] = []
    for t1 in p1_types:
        for t2 in p2_types:
            tasks.append((t1, t2))

    # Ensure output directory exists
    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    rng_master = random.Random(args.seed)

    # Worker function for local or multiprocessing
    def worker(pair: Tuple[HandType, HandType]) -> Tuple[HandType, HandType, float, float]:
        t1, t2 = pair
        # Derive a per-matchup seed
        local_seed = (hash((t1, t2)) ^ args.seed) & 0xFFFFFFFF
        return simulate_matchup(t1, t2, args.trials_per_matchup, seed=local_seed)

    results: List[Tuple[HandType, HandType, float, float]] = []

    if args.processes and args.processes > 1:
        try:
            import multiprocessing as mp
            with mp.get_context('spawn').Pool(processes=args.processes) as pool:
                for batch in chunked(tasks, 256):
                    results.extend(pool.map(worker, batch))
        except Exception as e:
            print(f"并行执行失败，回退到单进程: {e}", file=sys.stderr)
            for pair in tasks:
                results.append(worker(pair))
    else:
        for pair in tasks:
            results.append(worker(pair))

    # Write output
    with open(args.output, 'w', encoding='utf-8') as f:
        for t1, t2, e1, e2 in results:
            f.write(f"玩家1 | {t1} | {e1:.6f} | 玩家2 | {t2} | {e2:.6f}\n")

    print(f"已写入 {len(results)} 行到 {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())