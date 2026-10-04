import random

# ---------------------------------------------------------------- settings
START_WALLET = 1000
COST_PER_COLOUR = 10

# Multiplier applied to the round's TOTAL pledge.
#   (min, max) -- white/black are a flat 2x ("he wins the double")
#   blue/orange/red are randomised up to the stated cap
MULTIPLIER = {
    "white":  (2, 2),
    "black":  (2, 2),
    "blue":   (1, 100),
    "orange": (1, 200),
    "red":    (1, 500),
}

COLORS = ("white", "black", "blue", "orange", "red")
WHEEL = ["white"] * 23 + ["black"] * 23 + ["blue"] * 4 + ["orange"] * 2 + ["red"]
GROUPS = {"all": COLORS, "bonus": ("red", "orange", "blue")}

MAX_ROUNDS = 500_000  # safety net; see note in the write-up about termination

ANSI = {"white": "\033[97m", "black": "\033[30m", "blue": "\033[94m",
        "orange": "\033[93m", "red": "\033[91m"}
RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"


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
        elif token in MULTIPLIER:
            if token not in chosen:
                chosen.append(token)
        else:
            unknown.append(token)
    if unknown:
        return None, "Unknown option(s): " + ", ".join(unknown)
    return chosen, None


def roll_multiplier(colour):
    lo, hi = MULTIPLIER[colour]
    return random.randint(lo, hi)


def play(wallet, chosen, log=True):
    """One round. Returns (wallet, won, landed_colour, payout)."""
    pledge = COST_PER_COLOUR * len(chosen)

    if wallet < pledge:
        if log:
            print(f"  {RED}BROKE{RESET}  wallet {wallet} < pledge {pledge}. Game over.")
        return wallet, False, None, 0

    wallet -= pledge
    landed = random.choice(WHEEL)

    if landed not in chosen:
        if log:
            print(f"  {RED}LOSE{RESET}   pledged {pledge:>6}  landed {show(landed)}"
                  f"  -> wallet {wallet}")
        return wallet, False, landed, 0

    mult = roll_multiplier(landed)
    # Multiplier applies ONLY to the 10 points staked on the colour that landed.
    # Stakes on the other selected colours are lost even on a win.
    payout = COST_PER_COLOUR * mult
    wallet += payout
    if log:
        print(f"  {GREEN}WIN{RESET}    staked {pledge:>6} on {len(chosen)} colour(s)"
              f"  landed {show(landed)}  {mult:>3}x -> +{payout}  -> wallet {wallet}")
    return wallet, True, landed, payout


def run(strategy, rounds=MAX_ROUNDS, log=False, start=START_WALLET):
    wallet = start
    for i in range(1, rounds + 1):
        wallet, won, _, _ = play(wallet, strategy, log=log)
        if wallet <= 0:
            return wallet, i, True
    return wallet, rounds, False


# ---------------------------------------------------------------- interactive
def interactive():
    wallet = START_WALLET
    print(f"Wallet: {wallet} points.  Each colour costs {COST_PER_COLOUR} points.\n")
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
        covered = sum(WHEEL.count(c) for c in chosen)

        print(f"  Picked {len(chosen)} colour(s), pledge {pledge} points, "
              f"covering {covered}/53 segments")

        before = wallet
        wallet, won, _, _ = play(wallet, chosen, log=True)
        rounds += 1
        wins += won
        delta = wallet - before
        colour = GREEN if delta > 0 else RED
        print(f"  Wallet {wallet}  ({delta:+d})   "
              f"[{wins}W-{rounds-wins}L over {rounds} rounds]\n")

        if wallet <= 0:
            print("Wallet hit 0. GAME OVER.")
            break

    print(f"Final wallet: {wallet}  |  {wins}W - {rounds-wins}L in {rounds} rounds")


# ---------------------------------------------------------------- monte carlo
def monte_carlo():
    print(f"\n{'strategy':<18}{'bust rate':>11}{'median wallet':>16}"
          f"{'mean wallet':>14}{'median rounds':>15}")
    print("-" * 74)

    for name, strat in [("red", ["red"]), ("orange", ["orange"]), ("blue", ["blue"]),
                        ("white", ["white"]), ("black", ["black"]),
                        ("bonus", list(GROUPS["bonus"])), ("all", list(GROUPS["all"]))]:
        trials = 4000
        wallets, busts, rounds_played = [], 0, []
        for _ in range(trials):
            w, r, bust = run(strat, rounds=20000, log=False)
            wallets.append(w)
            rounds_played.append(r)
            busts += bust
        wallets.sort()
        median = wallets[trials // 2]
        mean = sum(wallets) / trials
        print(f"{name:<18}{busts/trials*100:>10.2f}%{median:>16,}"
              f"{mean:>14,.0f}{sorted(rounds_played)[trials//2]:>15,}")


if __name__ == "__main__":
    import sys
    if "--sim" in sys.argv:
        monte_carlo()
    elif "--auto" in sys.argv:
        for name, strat in [("bonus", list(GROUPS["bonus"])), ("white", ["white"])]:
            print(f"=== auto-play '{name}' (pledge "
                  f"{COST_PER_COLOUR*len(strat)}/round) ===")
            run(strat, rounds=15, log=True)
            print()
    else:
        interactive()
