import random

# The wheel: 53 segments total
WHEEL = ["white"] * 23 + ["black"] * 23 + ["blue"] * 4 + ["orange"] * 2 + ["red"]

COLORS = ("white", "black", "blue", "orange", "red")
SEGMENTS = {c: WHEEL.count(c) for c in COLORS}

# Named groups the player can type instead of listing colours
GROUPS = {
    "all":   COLORS,
    "bonus": ("red", "orange", "blue"),
}

ANSI = {"white": "\033[97m", "black": "\033[30m", "blue": "\033[94m",
        "orange": "\033[93m", "red": "\033[91m"}
RESET = "\033[0m"


def show(color, text=None):
    return f"{ANSI[color]}{text or color.upper()}{RESET}"


def parse_choice(raw):
    """Turn comma-separated input into a validated list of colours.
    Returns (colours, error_message)."""
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
        elif token in SEGMENTS:
            if token not in chosen:
                chosen.append(token)
        else:
            unknown.append(token)

    if unknown:
        return None, "Unknown option(s): " + ", ".join(unknown)
    return chosen, None


total = len(WHEEL)

print(f"Wheel: {total} segments\n")
for color in COLORS:
    print(f"  {color:<7} {SEGMENTS[color]:2} segments   "
          f"win chance {SEGMENTS[color]/total*100:5.2f}%   {show(color, '#####')}")

print("\nOptions: all | bonus | white | black | blue | orange | red")
print("Combine any of them with commas, e.g. 'bonus' or 'red,white' or 'all'\n")

wins = losses = 0

while True:
    raw = input("Your choice: ").strip()
    if raw.lower() == "q":
        break

    chosen, error = parse_choice(raw)
    if error:
        print(f"  {error}")
        continue

    covered = sum(SEGMENTS[c] for c in chosen)
    chance = covered / total * 100
    picks = ", ".join(show(c) for c in chosen)

    print(f"  You picked {len(chosen)} colour(s): {picks}")
    print(f"  Covers {covered}/{total} segments -> {chance:.2f}% win chance")
    if chance == 100.0:
        print(f"  {show('blue', 'NOTE: this covers every segment, so you cannot lose.')}")

    # The wheel spins on its own
    spin = random.choice(WHEEL)

    # Win rule: win if the spin landed on ANY of the chosen colours
    if spin in chosen:
        wins += 1
        print(f"  {show('blue', 'YOU WIN')}  Wheel stopped on {show(spin)}.")
    else:
        losses += 1
        print(f"  {show('red', 'YOU LOSE')}  Wheel stopped on {show(spin)}.")

    played = wins + losses
    print(f"  Score: {wins}W - {losses}L   ({wins/played*100:.1f}% win rate)\n")

print(f"\nFinal: {wins}W - {losses}L out of {wins + losses} rounds.")
