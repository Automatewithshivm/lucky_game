"""
53-segment colour wheel.

  player starts with 1000 points
  each selected colour costs 10 points
  if the wheel lands on a selected colour, payout = 10 x multiplier(colour)
  wallet updates after every round; game ends when the wallet can no
  no longer cover a bet

Run:
  python wheel.py                 play interactively
  python wheel.py --edge 8        set house edge target (3/5/8/10)
  python wheel.py --auto          watch 15 auto-rounds
  python wheel.py --sim           ruin + house P&L table
  python wheel.py --verify        check realised edge against target
"""

import random
import sys

import pricing
from pricing import COST_PER_COLOUR, TOTAL

START_WALLET = 1000
MAX_ROUNDS = 500_000

GROUPS = {"all": pricing.COLORS, "bonus": ("red", "orange", "blue")}

ANSI = {"white": "\033[97m", "black": "\033[30m", "blue": "\033[94m",
        "orange": "\033[93m", "red": "\033[91m"}
GREEN, RED, DIM, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[0m"

WHEEL = [c for c in pricing.COLORS for _ in range(pricing.SEGMENTS[c])]


def show(color, text=None):
    return f"{ANSI[color]}{text or color.upper()}{RESET}"


def parse_choice(raw):
    tokens = [t.strip().lower() for t in raw.split(",")]
    tokens = [t for t in tokens if t]
    if not tokens:
        return None, "Please enter at least one option."
    chosen, unknown = [], []
    for token in tokens:
        if token in GROUPS:
            for c in GROUPS[token]:
                if c not in chosen:
                    chosen.append(c)
        elif c_ok(token):
            if token not in chosen:
                chosen.append(token)
        else:
            unknown.append(token)
    if unknown:
        return None, "Unknown option(s): " + ", ".join(unknown)
    return chosen, None


def c_ok(token):
    return token in pricing.SEGMENTS


def print_table(edge_pct):
    print(f"Wheel: {TOTAL} segments   "
          f"house edge target: {pricing.pricing_key(edge_pct)}%   "
          f"sigma={pricing.SIGMA}\n")
    print(f"  {'colour':<8}{'segs':>5}{'hit %':>8}{'min':>6}{'median win':>11}"
          f"{'max win':>9}{'house edge':>12}")
    print("  " + "-" * 59)
    for c in pricing.COLORS:
        n = pricing.SEGMENTS[c]
        if c in pricing.FLAT_DOUBLE:
            med, mx, mn = "2x", "2x", "2x"
        else:
            samples = sorted(pricing.roll(c, edge_pct) for _ in range(4000))
            med, mx, mn = f"{samples[2000]}x", f"{samples[-1]}x", f"{samples[0]}x"
        print(f"  {c:<8}{n:>5}{n/TOTAL*100:>7.2f}%{mn:>6}{med:>11}{mx:>9}"
              f"{pricing.house_edge(c, edge_pct)*100:>11.2f}%")
    print(f"\n  {DIM}RTP = 100% - house edge. Paytable is deterministic and "
          f"published, not biased.{RESET}")
    print(f"  {DIM}Stakes on unselected colours are lost even when you win."
          f"{RESET}\n")


def play(wallet, chosen, edge_pct, log=True):
    """One round. Returns (wallet, won, landed, payout, mult)."""
    pledge = COST_PER_COLOUR * len(chosen)

    if wallet < pledge:
        if log:
            print(f"  {RED}CANNOT AFFORD{RESET}  wallet {wallet} < pledge {pledge}.")
        return wallet, False, None, 0, 0

    wallet -= pledge
    landed = random.choice(WHEEL)

    if landed not in chosen:
        if log:
            print(f"  {RED}LOSE{RESET}   staked {pledge:>6} on {len(chosen)} colour(s)"
                  f"   landed {show(landed)}   -> wallet {wallet}")
        return wallet, False, landed, 0, 0

    mult = pricing.roll(landed, edge_pct)
    payout = COST_PER_COLOUR * mult
    wallet += payout
    if log:
        print(f"  {GREEN}WIN{RESET}    staked {pledge:>6} on {len(chosen)} colour(s)"
              f"   landed {show(landed)} {mult:>4}x -> +{payout}"
              f"   -> wallet {wallet}")
    return wallet, True, landed, payout, mult


def run(strategy, edge_pct, rounds=MAX_ROUNDS, log=False, start=START_WALLET):
    """Play a fixed strategy until the wallet can't cover it, or rounds run out.

    The stop condition must be wallet < this strategy's pledge, not wallet < 10.
    Otherwise a player too poor for a 30-point 'bonus' bet keeps 'playing'
    no-op rounds, which inflates turnover and corrupts the ROI figure.
    """
    pledge = COST_PER_COLOUR * len(strategy)
    wallet = start
    for i in range(1, rounds + 1):
        if wallet < pledge:
            return wallet, i - 1, True
        wallet, won, _, _, _ = play(wallet, strategy, edge_pct, log=log)
        if wallet < pledge:
            return wallet, i, True
    return wallet, rounds, False


def interactive(edge_pct):
    print_table(edge_pct)
    wallet = START_WALLET
    print(f"Wallet: {wallet} points.  Each colour costs {COST_PER_COLOUR} points.")
    print("Options: all | bonus | white | black | blue | orange | red")
    print("Combine with commas, e.g. 'bonus' or 'red,white' or 'all'")
    print("Type 'q' to stop.\n")

    rounds = wins = 0
    while True:
        raw = input("Your choice: ").strip()
        if raw.lower() == "q":
            break

        chosen, error = parse_choice(raw)
        if error:
            print(f"  {error}")
            continue

        pledge = COST_PER_COLOUR * len(chosen)
        covered = sum(pricing.SEGMENTS[c] for c in chosen)
        se = pricing.selection_edge(chosen, edge_pct)

        print(f"  {len(chosen)} colour(s), pledge {pledge}, "
              f"covering {covered}/{TOTAL} segments, "
              f"combined house edge {se*100:.2f}%")

        before = wallet
        wallet, won, _, _, _ = play(wallet, chosen, edge_pct, log=True)
        rounds += 1
        wins += won
        delta = wallet - before
        tag = GREEN if delta > 0 else RED
        print(f"  Wallet {wallet}  ({delta:+d})   "
              f"[{wins}W-{rounds-wins}L over {rounds} rounds]\n")

        if wallet < COST_PER_COLOUR:
            print(f"Wallet {wallet} - cannot fund another bet. GAME OVER.")
            break

    print(f"Final wallet: {wallet}  |  {wins}W - {rounds-wins}L in {rounds} rounds")


def monte_carlo(edge_pct, players=2000):
    import statistics
    print("  'sum edge' adds the individual colour edges, so it is NOT the edge")
    print("  on turnover for multi-colour bets. 'edge/stake' is the real figure.\n")
    print(f"{'selection':<14}{'pledge':>7}{'sum edge':>10}{'edge/stake':>11}"
          f"{'median end':>12}{'mean end':>10}{'% stuck':>9}{'% profit':>10}"
          f"{'HOUSE NET':>15}{'ROI':>8}")
    print("-" * 106)
    for name, strat in [("red", ["red"]), ("orange", ["orange"]),
                        ("blue", ["blue"]), ("white", ["white"]),
                        ("black", ["black"]), ("bonus", list(GROUPS["bonus"])),
                        ("white,black", ["white", "black"]),
                        ("all", list(pricing.COLORS))]:
        pledge = COST_PER_COLOUR * len(strat)
        sum_edge = pricing.selection_edge(strat, edge_pct)
        ev_round = -COST_PER_COLOUR * sum_edge
        edge_stake = ev_round / pledge * 100
        finals, rounds_played = [], []
        for _ in range(players):
            w, r, _ = run(strat, edge_pct, rounds=20000, log=False)
            finals.append(w)
            rounds_played.append(r)
        turnover = sum(rounds_played) * pledge
        house = players * START_WALLET - sum(finals)
        roi = house / turnover * 100 if turnover else 0.0
        stuck = sum(1 for f in finals if f < pledge) / players * 100
        profit = sum(1 for f in finals if f > START_WALLET) / players * 100
        print(f"{name:<14}{pledge:>7}{sum_edge*100:>9.2f}%{edge_stake:>10.2f}%"
              f"{statistics.median(finals):>12,.0f}"
              f"{statistics.mean(finals):>10,.0f}{stuck:>8.1f}%{profit:>9.1f}%"
              f"{house:>15,.0f}{roi:>7.2f}%")


if __name__ == "__main__":
    args = sys.argv[1:]
    edge = 5.0
    for i, a in enumerate(args):
        if a == "--edge" and i + 1 < len(args):
            edge = float(args[i + 1])

    if "--verify" in args:
        pricing.verify(edge)
    elif "--sim" in args:
        monte_carlo(edge)
    elif "--auto" in args:
        for name, strat in [("bonus", list(GROUPS["bonus"])), ("red", ["red"])]:
            print(f"=== auto-play '{name}' "
                  f"(pledge {COST_PER_COLOUR*len(strat)}/round) ===")
            run(strat, edge, rounds=15, log=True)
            print()
    else:
        interactive(edge)
