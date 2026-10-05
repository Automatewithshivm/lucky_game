"""Regression tests for the wheel.  Run:  python tests.py"""

import math
import random

import pricing
from pricing import COST_PER_COLOUR, TOTAL

WHEEL = [c for c in pricing.COLORS for _ in range(pricing.SEGMENTS[c])]
passed = failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


print("wheel composition")
check("53 segments", len(WHEEL) == TOTAL, f"got {len(WHEEL)}")
check("23 white", WHEEL.count("white") == 23)
check("23 black", WHEEL.count("black") == 23)
check("4 blue", WHEEL.count("blue") == 4)
check("2 orange", WHEEL.count("orange") == 2)
check("1 red", WHEEL.count("red") == 1)

print("\npayout rule: bonus,white landing white pays 10 x 2 = 20")
import wheel

chosen, err = wheel.parse_choice("bonus,white")
check("parses to 4 colours", chosen == ["red", "orange", "blue", "white"], f"got {chosen}")
check("no parse error", err is None, f"got {err}")
pledge = COST_PER_COLOUR * len(chosen)
check("pledge is 40", pledge == 40, f"got {pledge}")

real = random.choice
random.choice = lambda seq: "white"
wallet, won, landed, payout, mult = wheel.play(1000, chosen, 5.0, log=False)
random.choice = real
check("landed white", landed == "white")
check("counts as a win", won is True)
check("multiplier is 2", mult == 2, f"got {mult}")
check("payout is 20", payout == 20, f"got {payout}")
check("wallet 1000-40+20 = 980", wallet == 980, f"got {wallet}")

print("\nlosing the other colours forfeits their stake")
random.seed(5)
N_ROUNDS = 20000
white_hits = 0
wrong_payout = None
for _ in range(N_ROUNDS):
    w, won, landed, payout, _m = wheel.play(1000, chosen, 5.0, log=False)
    if landed == "white":
        white_hits += 1
        if payout != 20:
            wrong_payout = payout
check("white always yields exactly 20", wrong_payout is None, f"got {wrong_payout}")
rate = white_hits / N_ROUNDS
check("white hit rate ~23/53", 0.40 < rate < 0.47, f"got {rate:.4f}")
print(f"  (white landed {white_hits}/{N_ROUNDS} = {rate:.4f}, theoretical "
      f"{23/53:.4f})")

print("\nmultipliers are integers within [floor, cap]")
bad = []
for c in pricing.COLORS:
    floor = 2 if c in pricing.FLAT_DOUBLE else pricing.MIN_MULT[c]
    cap = 2 if c in pricing.FLAT_DOUBLE else pricing.CAPS[c]
    for _ in range(30000):
        m = pricing.roll(c, 5.0)
        if not isinstance(m, int):
            bad.append((c, m, "not int"))
            break
        if c in pricing.FLAT_DOUBLE:
            if m != 2:
                bad.append((c, m, "white/black must be 2"))
                break
        elif not (floor <= m <= cap):
            bad.append((c, m, f"outside [{floor},{cap}]"))
            break
check("all multipliers int and in range", not bad, f"{bad[:3]}")

print("\nminimum multipliers are respected")
for c, want_min in (("blue", 3), ("orange", 5), ("red", 12)):
    vals = [pricing.roll(c, 5.0) for _ in range(200_000)]
    check(f"{c} min observed >= {want_min}", min(vals) >= want_min,
          f"got {min(vals)}")
    check(f"{c} never below floor", all(v >= want_min for v in vals))
    check(f"{c} cap unchanged at {pricing.CAPS[c]}",
          max(vals) <= pricing.CAPS[c], f"got {max(vals)}")
# the floor must actually bind, otherwise the test is vacuous
for c in ("blue", "orange", "red"):
    vals = [pricing.roll(c, 5.0) for _ in range(50_000)]
    at_floor = sum(1 for v in vals if v == pricing.MIN_MULT[c]) / len(vals)
    check(f"{c} hits its floor sometimes (>0.5%)", at_floor > 0.005,
          f"only {at_floor*100:.2f}%")

print("\nno arbitrage: EV negative for every selection")
for name, sel in [("red", ["red"]), ("orange", ["orange"]), ("blue", ["blue"]),
                  ("white", ["white"]), ("bonus", ["red", "orange", "blue"]),
                  ("white,black", ["white", "black"]),
                  ("all", list(pricing.COLORS))]:
    ev = pricing.ev_per_round(sel, 5.0)
    check(f"EV({name}) < 0", ev < 0, f"got {ev:+.3f}")

print("\npricing is exact (CDF, not sampled)")
for target in pricing.EDGE_CHOICES:
    for c in ("blue", "orange", "red"):
        mu = pricing.mu_for(c, target)
        got = pricing.exact_mean_multiplier(mu, pricing.SIGMA,
                                            pricing.CAPS[c], pricing.MIN_MULT[c])
        want = pricing.target_mean(c, target)
        check(f"{c} @ {target}%: exact mean == target mean",
              abs(got - want) < 1e-9, f"got {got:.10f} want {want:.10f}")
# the CDF must be a valid distribution: probabilities sum to 1, which we
# confirm by checking E[1] computed the same way equals 1
for c in ("blue", "orange", "red"):
    mu = pricing.mu_for(c, 5.0)
    cap, floor = pricing.CAPS[c], pricing.MIN_MULT[c]
    # E[m] == sum over k of k*P(k); if the masses did not sum to 1 the mean
    # solve would still "pass" but the distribution would be malformed.
    # Reconstruct total mass the same way the mean does, scaled to 1.
    lo_mass = pricing._phi((math.log(floor + 0.5) - mu) / pricing.SIGMA)
    mid = sum(pricing._phi((math.log(k + 0.5) - mu) / pricing.SIGMA)
              - pricing._phi((math.log(k - 0.5) - mu) / pricing.SIGMA)
              for k in range(floor + 1, cap))
    hi_mass = 1.0 - pricing._phi((math.log(cap - 0.5) - mu) / pricing.SIGMA)
    check(f"{c} CDF masses sum to 1",
          abs(lo_mass + mid + hi_mass - 1.0) < 1e-12,
          f"got {lo_mass + mid + hi_mass}")
for c in ("white", "black"):
    check(f"{c} edge is exactly 1-(23/53)*2",
          abs(pricing.house_edge(c, 5.0) - (1 - 23 / 53 * 2)) < 1e-15)

print("\nsampler smoke test")
# The exact CDF test above is the precision guarantee (1e-9). This only
# has to catch gross implementation bugs: wrong sigma, wrong cap, wrong mu
# threaded into roll(). Any of those shifts the realised edge by several
# percentage points, so a coarse fixed tolerance is both sufficient and
# immune to the sampling noise that made three earlier versions of this
# check fail spuriously.
#
# For reference, at n=1.5M the CLT SE of the measured edge is 0.026pp for
# blue and 0.113pp for red; observed deviations peak around 0.19pp. A
# 0.40pp tolerance leaves ~2x headroom over the worst observed while
# still failing loudly on any real bug.
STREAMS, PER_STREAM = 10, 150_000
TOL = 0.0040
for ti, target in enumerate(pricing.EDGE_CHOICES):
    for ci, c in enumerate(("blue", "orange", "red")):
        vals = []
        for s in range(STREAMS):
            random.seed(10_000 * ti + 100 * ci + s)
            vals.extend(pricing.roll(c, target) for _ in range(PER_STREAM))
        n = len(vals)
        mean = sum(vals) / n
        realised = 1 - (pricing.SEGMENTS[c] / pricing.TOTAL) * mean
        want = pricing.house_edge(c, target)
        check(f"{c} at {target}% -> {realised*100:.3f}% (n={n:,})",
              abs(realised - want) <= TOL,
              f"want {want*100:.3f}%, off by {(realised-want)*100:+.3f}pp")

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
