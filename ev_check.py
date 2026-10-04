import random, statistics

random.seed(7)

WHEEL = ["white"] * 23 + ["black"] * 23 + ["blue"] * 4 + ["orange"] * 2 + ["red"]
N = len(WHEEL)
COST = 10
CAPS = {"white": (2, 2), "black": (2, 2), "blue": (1, 100),
        "orange": (1, 200), "red": (1, 500)}


def mult(c):
    lo, hi = CAPS[c]
    return random.randint(lo, hi)


def sim(strat, rounds, start=1000):
    s = set(strat)
    pledge = COST * len(strat)
    w = start
    for r in range(1, rounds + 1):
        if w < pledge:
            return w, r, True
        w -= pledge
        landed = random.choice(WHEEL)
        if landed in s:
            w += COST * mult(landed)   # multiplier applies to that colour's 10 pts only
        if w <= 0:
            return w, r, True
    return w, rounds, False


STRATS = [
    ("red", ["red"]),
    ("orange", ["orange"]),
    ("blue", ["blue"]),
    ("white", ["white"]),
    ("black", ["black"]),
    ("bonus", ["red", "orange", "blue"]),
    ("white,black", ["white", "black"]),
    ("all", ["white", "black", "blue", "orange", "red"]),
]

hdr = ("strategy", "pledge", "EV/round", "EV/pt", "bust%", "median wallet")
print(f"{hdr[0]:<12}{hdr[1]:>7}{hdr[2]:>11}{hdr[3]:>8}{hdr[4]:>8}{hdr[5]:>16}")
print("-" * 62)

# analytic mean multiplier per colour (uniform lo..hi, integers)
MEAN_MULT = {c: (lo + hi) / 2 for c, (lo, hi) in CAPS.items()}

for name, strat in STRATS:
    pledge = COST * len(strat)
    s = set(strat)
    # payout is 10 x multiplier of the colour that landed -- NOT 10 x len(strat)
    ev = sum((WHEEL.count(c) / N) * COST * MEAN_MULT[c] for c in s) - pledge

    T = 400
    wallets, busts = [], 0
    for _ in range(T):
        w, r, b = sim(strat, 4000)
        wallets.append(w)
        busts += b
    print(f"{name:<12}{pledge:>7}{ev:>11,.1f}{ev/pledge:>8.2f}"
          f"{busts/T*100:>7.1f}%{statistics.median(wallets):>16,.0f}")

print("\nFair (break-even) max multiplier per colour, single-colour bet:")
print(f"{'colour':<8}{'segments':>9}{'fair cap':>11}{'your cap':>10}{'overshoot':>11}")
print("-" * 49)
for c in ("white", "black", "blue", "orange", "red"):
    n = WHEEL.count(c)
    p = n / N
    fair = 1 / p                     # payout must equal stake x (1/p) to break even
    cap = CAPS[c][1]
    label = "2x flat" if CAPS[c][0] == CAPS[c][1] else f"{cap}x"
    print(f"{c:<8}{n:>9}{fair:>10.2f}x{label:>10}{cap/fair:>10.1f}x")

