import random

# The wheel: 53 segments total
WHEEL = ["white"] * 23 + ["black"] * 23 + ["blue"] * 4 + ["orange"] * 2 + ["red"]

COLORS = ("white", "black", "blue", "orange", "red")
ANSI = {"white": "\033[97m", "black": "\033[30m", "blue": "\033[94m",
        "orange": "\033[93m", "red": "\033[91m"}
RESET = "\033[0m"


def show(color, text=None):
    return f"{ANSI[color]}{text or color.upper()}{RESET}"


total = len(WHEEL)
print(f"Wheel: {total} segments\n")
for color in COLORS:
    print(f"  {color:<7} {WHEEL.count(color):2} segments   "
          f"win chance {WHEEL.count(color)/total*100:5.2f}%   {show(color, '#####')}")

wins = losses = 0

while True:
    guess = input("\nChoose a colour (or 'q' to quit): ").strip().lower()

    if guess == "q":
        break

    if guess not in COLORS:
        print("Invalid choice. Pick one of: " + ", ".join(COLORS))
        continue

    spin = random.choice(WHEEL)

    # The win rule: win only if the guess matches the segment colour
    if guess == spin:
        wins += 1
        print(f"{show('blue', 'YOU WIN')}  You chose {show(guess)}, "
              f"wheel stopped on {show(spin)}.")
    else:
        losses += 1
        print(f"{show('red', 'YOU LOSE')}  You chose {show(guess)}, "
              f"wheel stopped on {show(spin)}.")

    played = wins + losses
    print(f"Score: {wins}W - {losses}L   ({wins/played*100:.1f}% win rate)")

print(f"\nFinal: {wins}W - {losses}L out of {wins + losses} rounds.")
