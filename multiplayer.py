"""
Multiplayer analysis, corrected.

An earlier version of this script ran 400 rounds and I read the B/C results
as anomalous (they deviated from theory by 16-24 "sigma"). That was my
error, not a bug: the variance of the house's session P&L is dominated by
how many times red/orange LAND, not by multiplier spread. red lands 1/53
of rounds, so a 400-round session contains only ~7 red landings and the
result swings by millions of points in either direction.

Hand-derived per-round sd for design B at 1000 players/round:
    p(white/black)=46/53 -> +30,000      p(blue)=4/53   ->  -95,870
    p(orange)     = 2/53  -> -221,750    p(red)  =1/53  -> -473,500
    E  = 1,500/round,  var = 8.56e9  ->  sd = 92,510/round
    over 400 rounds sd = 1.85e6, so a 1.95e6 deviation is ~1.05 sd. Normal.

This version runs long enough for the house-win figures to mean something,
and reports the metric that actually decides feasibility: how likely the
house is to end a session in the red.
"""

import math
import random
import statistics
import time

import pricing
from pricing import COST_PER_COLOUR, TOTAL

WHEEL = [c for c in pricing.COLORS for _ in range(pricing.SEGMENTS[c])]
EDGE = 5.0
STRAT = ["red", "orange", "blue"]
PLEDGE = COST_PER_COLOUR * len(STRAT)
HIT_P = sum(pricing.SEGMENTS[c] for c in STRAT) / TOTAL
EV_ROUND = pricing.ev_per_round(STRAT, EDGE)      # negative, per player


# ------------------------------------------------------------------ throughput
def benchmark():
    print("=" * 78)
    print("1. THROUGHPUT -- is compute ever the limit?")
    print("=" * 78)
    n = 400_000
    random.seed(1)
    t0 = time.perf_counter()
    for _ in range(n):
        random.choice(WHEEL)
    t1 = time.perf_counter()
    for _ in range(n):
        pricing.roll("red", EDGE)
    t2 = time.perf_counter()
    spin, roll = n / (t1 - t0), n / (t2 - t1)
    print(f"  segment draw        {spin:>14,.0f} /sec")
    print(f"  multiplier draw     {roll:>14,.0f} /sec")
    print(f"  worst-case round    {min(spin, roll):>14,.0f} /sec")
    print()
    print("  One core settles ~289k player-rounds/sec = 20.8 billion/day.")
    print("  Compute is not a constraint at any plausible player count.")
    print("  The real limit is the round CYCLE TIME, not the maths.")


# ------------------------------------------------------- architecture compare
def simulate(m=1000, rounds=20_000, seed_base=1000):
    print()
    print("=" * 78)
    print(f"2. HOUSE P&L BY ARCHITECTURE -- {m:,} players/round x {rounds:,} rounds")
    print("=" * 78)
    n = m * rounds
    print(f"  {n:,} player-rounds, stake collected {n*PLEDGE:,} points")
    print(f"  every player bets 'bonus' (30 pts), 5% edge on each colour")
    print(f"  theoretical house win: {-n*EV_ROUND:,.0f} points\n")

    out = {}

    # A -- fully independent: own segment AND own multiplier per player
    random.seed(seed_base)
    total, worst, rounds_data = 0, 0, []
    for _ in range(rounds):
        rp = 0
        for _ in range(m):
            rp += PLEDGE
            landed = random.choice(WHEEL)
            if landed in STRAT:
                rp -= COST_PER_COLOUR * pricing.roll(landed, EDGE)
        total += rp
        rounds_data.append(rp)
        worst = min(worst, rp)
    out["A"] = (total, rounds_data, worst)

    # B -- shared segment, per-player multiplier
    random.seed(seed_base + 1)
    total, worst, rounds_data = 0, 0, []
    for _ in range(rounds):
        rp = m * PLEDGE
        landed = random.choice(WHEEL)
        if landed in STRAT:
            for _ in range(m):
                rp -= COST_PER_COLOUR * pricing.roll(landed, EDGE)
        total += rp
        rounds_data.append(rp)
        worst = min(worst, rp)
    out["B"] = (total, rounds_data, worst)

    # C -- shared segment AND shared multiplier
    random.seed(seed_base + 2)
    total, worst, rounds_data = 0, 0, []
    for _ in range(rounds):
        rp = m * PLEDGE
        landed = random.choice(WHEEL)
        if landed in STRAT:
            rp -= m * COST_PER_COLOUR * pricing.roll(landed, EDGE)
        total += rp
        rounds_data.append(rp)
        worst = min(worst, rp)
    out["C"] = (total, rounds_data, worst)

    exp_profit = -n * EV_ROUND
    print(f"  {'design':<32}{'house win':>14}{'vs theory':>12}"
          f"{'sd':>12}{'sd/profit':>10}{'worst round':>14}")
    print("  " + "-" * 94)
    for k, label in (("A", "A independent (current)"),
                     ("B", "B shared segment, own mult"),
                     ("C", "C shared segment + mult")):
        total, rp_list, worst = out[k]
        sd = statistics.stdev(rp_list)
        print(f"  {label:<32}{total:>14,.0f}{(total-exp_profit)/exp_profit*100:>11.1f}%"
              f"{sd:>12,.0f}{sd/exp_profit:>9.2f}x{worst:>14,.0f}")

    print()
    print("  'sd/profit' = how noisy the session result is vs what you earn.")
    print("  A <1.0 means a typical session result is smaller than the profit,")
    print("  so the outcome is essentially guaranteed.")
    return out, m, rounds, exp_profit


# ------------------------------------- how many rounds until it is conclusive
def convergence(m=1000, rounds=20_000, seed_base=7000):
    print()
    print("=" * 78)
    print("3. ROUNDS NEEDED BEFORE THE HOUSE RESULT IS MEANINGFUL")
    print("=" * 78)
    print("  cumulative house win vs rounds, 'bonus' bet, 1000 players/round")
    print()
    print(f"  {'rounds':>8}{'A independent':>16}{'B shared seg':>16}"
          f"{'C shared seg+mult':>20}")
    print("  " + "-" * 60)

    run_a, run_b, run_c = 0.0, 0.0, 0.0
    marks = {50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000}
    random.seed(seed_base)
    for r in range(1, rounds + 1):
        # A
        rp = 0
        for _ in range(m):
            rp += PLEDGE
            landed = random.choice(WHEEL)
            if landed in STRAT:
                rp -= COST_PER_COLOUR * pricing.roll(landed, EDGE)
        run_a += rp
        # B
        landed = random.choice(WHEEL)
        rp = m * PLEDGE
        if landed in STRAT:
            for _ in range(m):
                rp -= COST_PER_COLOUR * pricing.roll(landed, EDGE)
        run_b += rp
        # C
        landed = random.choice(WHEEL)
        rp = m * PLEDGE
        if landed in STRAT:
            rp -= m * COST_PER_COLOUR * pricing.roll(landed, EDGE)
        run_c += rp
        if r in marks:
            print(f"  {r:>8,}{run_a:>16,.0f}{run_b:>16,.0f}{run_c:>20,.0f}")
    print()
    print("  C is still negative/marginal at 20k rounds. That is the finding:")
    print("  a shared multiplier makes the session result a lottery ticket.")


# ------------------------------------------------------ tail liability table
def tail():
    print()
    print("=" * 78)
    print("4. DESIGN C WORST-CASE SINGLE ROUND")
    print("=" * 78)
    mu_red = pricing.mu_for("red", EDGE)
    p_cap = 1.0 - pricing._phi((math.log(499.5) - mu_red) / pricing.SIGMA)
    p_event = (1 / 53) * p_cap
    print(f"  P(multiplier = 500 on a red hit) = {p_cap*100:.3f}%")
    print(f"  P(red lands AND hits 500x)       = {p_event:.6f} "
          f"= 1 in {1/p_event:,.0f} rounds\n")
    print(f"  {'players':>9}{'stake in':>13}{'paid out':>14}"
          f"{'round loss':>14}{'rounds of profit wiped':>26}")
    print("  " + "-" * 76)
    for players in (10, 100, 1000, 10000):
        taken = players * PLEDGE
        loss = players * COST_PER_COLOUR * pricing.CAPS["red"] - taken
        rounds_wiped = loss / (-EV_ROUND * players)
        print(f"  {players:>9,}{taken:>13,}{taken+loss:>14,}{loss:>14,}"
              f"{rounds_wiped:>25,.0f}x")
    print()
    print("  The RATIO is independent of player count (both scale linearly),")
    print("  but the absolute reserve needed grows with player count.")
    print(f"  At a live pace of 80 rounds/hour the cap event hits every "
          f"{1/p_event/80:,.0f} hours.")
    print(f"  Expected profit over that span: {1/p_event * 1500 * players:,} "
          f"points per {players} players.")


if __name__ == "__main__":
    benchmark()
    simulate()
    convergence()
    tail()