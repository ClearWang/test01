#include <bits/stdc++.h>
using namespace std;

// Short-Deck (6+ Hold'em) equity calculator for two players across all starting hand categories.
// Rules implemented:
// - Deck ranks: 6,7,8,9,T,J,Q,K,A (9 ranks), 4 suits
// - Hand ranking order (Short-Deck common): Straight Flush > Four of a Kind > Flush > Full House > Straight > Three of a Kind > Two Pair > One Pair > High Card
// - A can be used low to make A-6-7-8-9 straight (treated as 9-high straight)
// - Flush beats Full House
//
// Output format per line: "牌型1 vs 牌型2 | 牌型1赢率 牌型2赢率"
// Where rates are decimals in [0,1] with 6 decimal places, ties split 0.5 to each.

struct RNG {
    std::mt19937_64 eng;
    RNG() : eng(std::random_device{}()) {}
    uint64_t next() { return eng(); }
    size_t uniform_index(size_t n) {
        std::uniform_int_distribution<size_t> dist(0, n - 1);
        return dist(eng);
    }
    double uniform01() {
        std::uniform_real_distribution<double> dist(0.0, 1.0);
        return dist(eng);
    }
};

// Card encoding: id in [0, 35]
// rankIndex = id / 4 -> 0..8 == [6,7,8,9,T,J,Q,K,A]
// suit = id % 4 -> 0..3
static inline int rank_index_of(int cardId) { return cardId / 4; }
static inline int suit_of(int cardId) { return cardId % 4; }
static inline char rank_char(int r) {
    static const char ranks[9] = {'6','7','8','9','T','J','Q','K','A'};
    return ranks[r];
}

struct HandValue {
    uint64_t value;
};

// Helper: return highest straight top rank index (0..8) present in mask, or -1 if none
// mask: bit i set if rank i present. A-6 straight special case: bits {8,3,2,1,0}
static inline int highest_straight_top_from_mask(uint16_t mask) {
    // Normal straights: top from 8 to 4
    for (int top = 8; top >= 4; --top) {
        uint16_t need = 0;
        for (int k = 0; k < 5; ++k) need |= (1u << (top - k));
        if ((mask & need) == need) return top;
    }
    // A-6-7-8-9 -> treat as top=3 (9-high)
    uint16_t needA6 = (1u << 8) | (1u << 3) | (1u << 2) | (1u << 1) | (1u << 0);
    if ((mask & needA6) == needA6) return 3;
    return -1;
}

// Evaluate best 5-card hand from 7 cards under short-deck rules
static inline HandValue evaluate7(const array<int,7>& cards) {
    int rankCount[9] = {0};
    int suitCount[4] = {0};
    uint16_t rankMask = 0;
    uint16_t suitRankMask[4] = {0,0,0,0};

    for (int i = 0; i < 7; ++i) {
        int c = cards[i];
        int r = rank_index_of(c);
        int s = suit_of(c);
        ++rankCount[r];
        ++suitCount[s];
        rankMask |= (1u << r);
        suitRankMask[s] |= (1u << r);
    }

    auto make_value = [](int category,
                         const vector<int>& tiebreakRanksDesc) -> HandValue {
        // category: 8..0 (higher is better)
        // Pack into 64-bit: [category][r1][r2][r3][r4][r5]
        uint64_t v = static_cast<uint64_t>(category) << 32;
        int shift = 28;
        for (size_t i = 0; i < tiebreakRanksDesc.size() && i < 7; ++i) {
            v |= (static_cast<uint64_t>(tiebreakRanksDesc[i] & 0xF) << shift);
            shift -= 4;
        }
        return {v};
    };

    // Straight Flush
    for (int s = 0; s < 4; ++s) {
        if (suitCount[s] >= 5) {
            int top = highest_straight_top_from_mask(suitRankMask[s]);
            if (top != -1) {
                // tiebreak by top
                return make_value(8, {top});
            }
        }
    }

    // Four of a Kind
    int fourRank = -1;
    for (int r = 8; r >= 0; --r) if (rankCount[r] == 4) { fourRank = r; break; }
    if (fourRank != -1) {
        // Highest kicker
        int kicker = -1;
        for (int r = 8; r >= 0; --r) if (r != fourRank && rankCount[r] > 0) { kicker = r; break; }
        return make_value(7, {fourRank, kicker});
    }

    // Flush (beats Full House in Short-Deck)
    int flushSuit = -1;
    for (int s = 0; s < 4; ++s) if (suitCount[s] >= 5) { flushSuit = s; break; }
    if (flushSuit != -1) {
        // pick top 5 ranks in this suit
        vector<int> ranks;
        ranks.reserve(5);
        for (int r = 8; r >= 0; --r) if (suitRankMask[flushSuit] & (1u << r)) ranks.push_back(r);
        if (ranks.size() > 5) ranks.resize(5);
        return make_value(6, ranks);
    }

    // Full House
    int triple1 = -1, triple2 = -1;
    for (int r = 8; r >= 0; --r) if (rankCount[r] >= 3) { if (triple1 == -1) triple1 = r; else if (triple2 == -1) triple2 = r; }
    if (triple1 != -1) {
        int pairRank = -1;
        // If second triple exists, it serves as pair
        if (triple2 != -1) pairRank = triple2; else {
            for (int r = 8; r >= 0; --r) if (r != triple1 && rankCount[r] >= 2) { pairRank = r; break; }
        }
        if (pairRank != -1) {
            return make_value(5, {triple1, pairRank});
        }
    }

    // Straight
    {
        int top = highest_straight_top_from_mask(rankMask);
        if (top != -1) return make_value(3, {top});
    }

    // Three of a Kind
    if (triple1 != -1) {
        vector<int> kickers;
        for (int r = 8; r >= 0; --r) if (r != triple1 && rankCount[r] > 0) kickers.push_back(r);
        if (kickers.size() > 2) kickers.resize(2);
        vector<int> tb = {triple1};
        tb.insert(tb.end(), kickers.begin(), kickers.end());
        return make_value(4, tb);
    }

    // Two Pair
    int pair1 = -1, pair2 = -1;
    for (int r = 8; r >= 0; --r) if (rankCount[r] >= 2) { if (pair1 == -1) pair1 = r; else if (pair2 == -1) pair2 = r; }
    if (pair1 != -1 && pair2 != -1) {
        int kicker = -1;
        for (int r = 8; r >= 0; --r) if (r != pair1 && r != pair2 && rankCount[r] > 0) { kicker = r; break; }
        return make_value(2, {pair1, pair2, kicker});
    }

    // One Pair
    if (pair1 != -1) {
        vector<int> kickers;
        for (int r = 8; r >= 0; --r) if (r != pair1 && rankCount[r] > 0) kickers.push_back(r);
        if (kickers.size() > 3) kickers.resize(3);
        vector<int> tb = {pair1};
        tb.insert(tb.end(), kickers.begin(), kickers.end());
        return make_value(1, tb);
    }

    // High Card
    {
        vector<int> highs;
        for (int r = 8; r >= 0; --r) if (rankCount[r] > 0) highs.push_back(r);
        if (highs.size() > 5) highs.resize(5);
        return make_value(0, highs);
    }
}

struct Category {
    // type: 0 pair, 1 suited, 2 offsuit
    int type;
    int hi; // rank index of high char (for non-pair)
    int lo; // rank index of low char (for non-pair)
    string label; // e.g. "AKs", "AKo", "AA"
};

static vector<Category> build_all_categories() {
    vector<Category> cats;
    // Pairs first from AA down to 66
    for (int r = 8; r >= 0; --r) {
        string s;
        s.push_back(rank_char(r));
        s.push_back(rank_char(r));
        cats.push_back({0, r, r, s});
    }
    // Non-pairs: from AK down to 76, include suited and offsuit
    for (int hi = 8; hi >= 0; --hi) {
        for (int lo = hi - 1; lo >= 0; --lo) {
            string s1; s1.push_back(rank_char(hi)); s1.push_back(rank_char(lo)); s1.push_back('s');
            string s2; s2.push_back(rank_char(hi)); s2.push_back(rank_char(lo)); s2.push_back('o');
            cats.push_back({1, hi, lo, s1});
            cats.push_back({2, hi, lo, s2});
        }
    }
    return cats;
}

// Build list of all 36 card ids
static inline void build_full_deck(array<int,36>& deck) {
    for (int i = 0; i < 36; ++i) deck[i] = i;
}

// Given category and excluded cards set, enumerate all 2-card combos matching the category
static vector<array<int,2>> enumerate_combos_for_category(const Category& cat, const array<bool,36>& excluded) {
    vector<array<int,2>> res;
    // Collect available cards by rank and suit
    vector<int> byRank[9];
    bool has[9][4];
    memset(has, 0, sizeof(has));
    for (int id = 0; id < 36; ++id) if (!excluded[id]) {
        int r = rank_index_of(id), s = suit_of(id);
        byRank[r].push_back(id);
        has[r][s] = true;
    }

    if (cat.type == 0) {
        // Pair: need two different suits of same rank
        int r = cat.hi;
        // gather suits available
        vector<int> suitCards;
        for (int s = 0; s < 4; ++s) if (has[r][s]) suitCards.push_back(r * 4 + s);
        int n = (int)suitCards.size();
        for (int i = 0; i < n; ++i) for (int j = i + 1; j < n; ++j) {
            int a = suitCards[i], b = suitCards[j];
            if (a > b) swap(a, b);
            res.push_back({a, b});
        }
        return res;
    }

    int hi = cat.hi, lo = cat.lo;
    if (cat.type == 1) {
        // Suited: same suit for hi and lo
        for (int s = 0; s < 4; ++s) {
            int a = hi * 4 + s;
            int b = lo * 4 + s;
            if (!excluded[a] && !excluded[b]) {
                int x = a, y = b; if (x > y) swap(x, y);
                res.push_back({x, y});
            }
        }
        return res;
    }
    // Offsuit: suits different
    for (int sa = 0; sa < 4; ++sa) {
        int a = hi * 4 + sa; if (excluded[a]) continue;
        for (int sb = 0; sb < 4; ++sb) if (sb != sa) {
            int b = lo * 4 + sb; if (excluded[b]) continue;
            int x = a, y = b; if (x > y) swap(x, y);
            res.push_back({x, y});
        }
    }
    // Remove duplicates if any
    sort(res.begin(), res.end());
    res.erase(unique(res.begin(), res.end()), res.end());
    return res;
}

// Select a p1 combo with probability proportional to S(p1) (# of valid p2 combos given p1)
static int weighted_index_by_counts(const vector<int>& weights, RNG& rng) {
    long long sum = 0;
    for (int w : weights) sum += w;
    if (sum <= 0) return -1;
    std::uniform_int_distribution<long long> dist(1, sum);
    long long r = dist(rng.eng);
    long long acc = 0;
    for (size_t i = 0; i < weights.size(); ++i) {
        acc += weights[i];
        if (r <= acc) return (int)i;
    }
    return (int)weights.size() - 1;
}

static inline void pick_random_board(const array<bool,36>& excluded, array<int,5>& boardOut, RNG& rng) {
    int remaining[36];
    int m = 0;
    for (int id = 0; id < 36; ++id) if (!excluded[id]) remaining[m++] = id;
    // sample 5 without replacement by partial Fisher-Yates
    for (int i = 0; i < 5; ++i) {
        int j = i + (int)(rng.uniform_index((size_t)(m - i)));
        std::swap(remaining[i], remaining[j]);
        boardOut[i] = remaining[i];
    }
}

static inline int compare_values(const HandValue& a, const HandValue& b) {
    if (a.value < b.value) return -1;
    if (a.value > b.value) return 1;
    return 0;
}

struct Outcome { long long win1 = 0, win2 = 0, tie = 0; };

Outcome simulate_pair(const Category& c1, const Category& c2, int iters, RNG& rng) {
    Outcome out;
    // Precompute p1 combos from full deck and their S (valid p2 count given p1)
    array<bool,36> none{}; none.fill(false);
    vector<array<int,2>> p1Combos = enumerate_combos_for_category(c1, none);
    if (p1Combos.empty()) return out;

    vector<int> p1Weights;
    p1Weights.reserve(p1Combos.size());
    for (auto& h1 : p1Combos) {
        array<bool,36> ex = none;
        ex[h1[0]] = true; ex[h1[1]] = true;
        vector<array<int,2>> p2Combos = enumerate_combos_for_category(c2, ex);
        p1Weights.push_back((int)p2Combos.size());
    }
    long long sumW = 0; for (int w : p1Weights) sumW += w;
    if (sumW == 0) return out; // impossible matchup

    array<int,7> cards;
    array<int,5> board;

    for (int it = 0; it < iters; ++it) {
        // Choose p1 combo with weight S
        int idx1 = weighted_index_by_counts(p1Weights, rng);
        if (idx1 < 0) break;
        auto h1 = p1Combos[idx1];

        // Build excluded for p2
        array<bool,36> ex{}; ex.fill(false);
        ex[h1[0]] = true; ex[h1[1]] = true;
        vector<array<int,2>> p2Combos = enumerate_combos_for_category(c2, ex);
        if (p2Combos.empty()) { --it; continue; }
        int idx2 = (int)rng.uniform_index(p2Combos.size());
        auto h2 = p2Combos[idx2];

        // Exclude 4 hole cards
        array<bool,36> exAll{}; exAll.fill(false);
        exAll[h1[0]] = exAll[h1[1]] = exAll[h2[0]] = exAll[h2[1]] = true;
        // Random board of 5
        pick_random_board(exAll, board, rng);

        // Build 7-card arrays and evaluate
        cards[0] = h1[0]; cards[1] = h1[1];
        for (int i = 0; i < 5; ++i) cards[2 + i] = board[i];
        HandValue v1 = evaluate7(cards);
        cards[0] = h2[0]; cards[1] = h2[1];
        for (int i = 0; i < 5; ++i) cards[2 + i] = board[i];
        HandValue v2 = evaluate7(cards);

        int cmp = compare_values(v1, v2);
        if (cmp > 0) ++out.win1; else if (cmp < 0) ++out.win2; else ++out.tie;
    }
    return out;
}

int main(int argc, char** argv) {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int itersPerPair = 200; // default
    if (argc >= 2) {
        int x = atoi(argv[1]);
        if (x > 0) itersPerPair = x;
    }

    string outPath = "/workspace/shortdeck_equities.txt";
    ofstream ofs(outPath);
    if (!ofs) {
        cerr << "无法写入文件: " << outPath << "\n";
        return 1;
    }

    RNG rng;
    vector<Category> cats = build_all_categories();


    // For each pair of categories
    for (size_t i = 0; i < cats.size(); ++i) {
        for (size_t j = 0; j < cats.size(); ++j) {
            Outcome oc = simulate_pair(cats[i], cats[j], itersPerPair, rng);
            double total = (double)(oc.win1 + oc.win2 + oc.tie);
            double eq1 = 0.0, eq2 = 0.0;
            if (total > 0) {
                eq1 = ((double)oc.win1 + 0.5 * (double)oc.tie) / total;
                eq2 = ((double)oc.win2 + 0.5 * (double)oc.tie) / total;
            }
            ofs.setf(std::ios::fixed); ofs << setprecision(6);
            ofs << cats[i].label << " vs " << cats[j].label << " | " << eq1 << " " << eq2 << "\n";
        }
        ofs.flush();
    }

    ofs.close();
    cout << "结果已写入: " << outPath << "\n";
    return 0;
}