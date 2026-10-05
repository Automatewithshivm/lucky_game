"""
Risk metrics that actually decide feasibility, computed analytically.

multiplayer.py measured the sd of the PER-ROUND house P&L. To judge a
session you need the sd of the CUMULATIVE P&L, which is per-round sd x
sqrt(rounds), compared against the profit earned over those rounds.

Per-player P&L distribution (house perspective), player bets 'bonus' (30):
    land white/black (46/53): +30
    land c in {blue,orange,red}:  30 - 10 * multiplier_c

E[P] and E[P^2] are computed from the exact CDF, so the variance below is
not a Monte Carlo estimate.
"""

import math

import pricing
from pricing import COST_PER_COLOUR, TOTAL

EDGE = 5.0
STRAT = ["red", "orange", "blue"]
PLEDGE = COST_PER_COLOUR * len(STRAT)
EV = -pricing.ev_per_round(STRAT, EDGE)        # house win per player-round


def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def multiplier_second_moment(colour, edge_pct=EDGE):
    """E[m^2] for clamp(round(exp(mu + sigma Z)), floor, cap)."""
    mu = pricing.mu_for(colour, edge_pct)
    cap, floor = pricing.CAPS[colour], pricing.MIN_MULT[colour]
    s, lo_edge = pricing.SIGMA, math.log(floor + 0.5)
    hi_edge = math.log(cap - 0.5)
    total = floor * floor * phi((lo_edge - mu) / s)
    for k in range(floor + 1, cap):
        hi = phi((math.log(k + 0.5) - mu) / s)
        lo = phi((math.log(k - 0.5) - mu) / s)
        total += k * k * (hi - lo)
    total += cap * cap * (1.0 - phi((hi_edge - mu) / s))
    return total


def player_pnl_moments():
    """E[P] and E[P^2] for one player betting 'bonus'."""
    mean = var_acc = 0.0
    second = 0.0
    for c in pricing.COLORS:
        p = pricing.SEGMENTS[c] / TOTAL
        if c in pricing.FLAT_DOUBLE:
            m1, m2 = 2.0, 4.0
        else:
            m1 = pricing.target_mean(c, EDGE)          # exact by construction
            m2 = multiplier_second_moment(c)
        # P = PLEDGE - COST*m  when the colour lands, else +PLEDGE
        if c in STRAT:
            p1 = PLEDGE - COST_PER_COLOUR * m1
            p2 = (PLEDGE - COST_PER_COLOUR) ** 2 \
                - 2 * (PLEDGE - COST_PER_COLOUR) * COST_PER_COLOUR * m1 \
                + COST_PER_COLOUR ** 2 * m2
        else:
            p1 = p2 = PLEDGE
        mean += p * p1
        second += p * p2
    return mean, second


def main():
    mean, second = player_pnl_moments()
    var_player = second - mean * mean
    print("=" * 74)
    print("PER-PLAYER (one 'bonus' bet of 30 points)")
    print("=" * 74)
    print(f"  E[house win]        {mean:>10.4f} points")
    print(f"  E[P^2]              {second:>10.2f}")
    print(f"  Var                 {var_player:>10.2f}   sd {math.sqrt(var_player):.3f}")
    print(f"  95% of rounds       house wins between "
          f"{mean - 1.96*math.sqrt(var_player):.1f} and "
          f"{mean + 1.96*math.sqrt(var_player):.1f}")

    print()
    print("  sanity: player-rounds to expect one red-at-cap wipeout")
    # in design A/B each player independently rolls, so a single player
    # hitting the red cap is the unit of tail risk
    p_red_cap = pricing.SEGMENTS["red"] / TOTAL * (
        1 - phi((math.log(499.5) - pricing.mu_for("red", EDGE)) / pricing.SIGMA))
    print(f"    P(one player hits red at the 500x cap) = {p_red_cap:.6f}")
    print(f"    -> one every {1/p_red_cap:,.0f} player-rounds")
    print(f"    that single player costs "
          f"{COST_PER_COLOUR*pricing.CAPS['red'] - PLEDGE:,} points")

    print()
    print("=" * 74)
    print("SESSION RISK BY ARCHITECTURE (1000 players/round, 'bonus' bet)")
    print("=" * 74)
    print("  E[profit] per round = 1000 x 1.5 = 1,500 points")
    print()
    print(f"  {'rounds':>8}{'E[profit]':>14}{'A sd':>12}{'B sd':>14}{'C sd':>14}")
    print("  " + "-" * 62)

    # per-round sd measured in multiplayer.py at 1000 players/round
    sd_round = {"A": 4_803.0, "B": 87_336.0, "C": 143_694.0}
    for rounds in (1_000, 5_000, 20_000, 100_000):
        profit = rounds * 1_500
        row = {k: v * math.sqrt(rounds) for k, v in sd_round.items()}
        print(f"  {rounds:>8,}{profit:>14,.0f}{row['A']:>12,.0f}"
              f"{row['B']:>14,.0f}{row['C']:>14,.0f}")

    print()
    print("  P(house ends the session in the RED)")
    print()
    print(f"  {'rounds':>8}{'A':>10}{'B':>10}{'C':>10}      (profit / sd)")
    print("  " + "-" * 46)
    for rounds in (1_000, 5_000, 20_000, 100_000):
        profit = rounds * 1_500
        cells = []
        for k in ("A", "B", "C"):
            z = profit / (sd_round[k] * math.sqrt(rounds))
            # P(Z < -z)
            loss = 0.5 * math.erfc(z / math.sqrt(2))
            cells.append(f"{loss*100:>9.3f}%")
        zA = profit / (sd_round["A"] * math.sqrt(rounds))
        print(f"  {rounds:>8,}{cells[0]}{cells[1]}{cells[2]}   "
              f"A: {zA:.1f} sd of margin")

    print()
    print("=" * 74)
    print("DESIGN C: PROFIT WIPED BY ONE CAP EVENT (corrected)")
    print("=" * 74)
    p_event = pricing.SEGMENTS["red"] / TOTAL * (
        1 - phi((math.log(499.5) - pricing.mu_for("red", EDGE)) / pricing.SIGMA))
    print(f"  P(red lands AND multiplier = 500x) = {p_event:.6f} "
          f"= 1 in {1/p_event:,.0f} rounds")
    print()
    print(f"  {'players':>9}{'stake in':>13}{'paid out':>14}{'round loss':>14}"
          f"{'profit in that span':>21}{'loss as % of it':>18}")
    print("  " + "-" * 79)
    for players in (10, 100, 1000, 10000):
        taken = players * PLEDGE
        loss = players * COST_PER_COLOUR * pricing.CAPS["red"] - taken
        span_profit = (1 / p_event) * mean * players
        print(f"  {players:>9,}{taken:>13,}{taken+loss:>14,}{loss:>14,}"
              f"{span_profit:>21,.0f}{loss/span_profit*100:>17.1f}%")
    print()
    print(f"  At a live pace of 80 rounds/hour: one cap event every "
          f"{1/p_event/80:,.0f} hours")
    print("  The percentage is player-count independent; the absolute reserve is not.")


if __name__ == "__main__":
    main()