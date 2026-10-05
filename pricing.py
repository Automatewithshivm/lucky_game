"""
Pricing engine for the 53-segment colour wheel.

Payout rule (per colour): the player stakes 10 points on each selected
colour. If the wheel lands on a selected colour, the player receives
10 x multiplier(landed_colour). Stakes on the other selected colours are
forfeited.

Because each colour pays only on its own stake, the house edges of the
selected colours simply ADD:

    EV(selection) = -10 * sum(house_edge_c for c in selection)

which is negative for every selection. There is no arbitrage available
from combining bets.

MULTIPLIER MODEL
----------------
    multiplier = clamp(round(exp(gauss(mu, SIGMA))), 1, cap)

Lognormal, so the big jackpots survive without wrecking the expected value.
A uniform 1..cap draw has mean (1+cap)/2, which is far too high at large
caps: a 500x cap implies a 250x mean, but red only needs a 53x mean to
break even.

PRICING IS EXACT, NOT SAMPLED
-----------------------------
mu is chosen so that E[multiplier] = (1 - edge) * 53 / segments exactly.
E[multiplier] is computed in closed form from the normal CDF:

    P(m = 1)   = Phi((ln 1.5      - mu) / sigma)
    P(m = k)   = Phi((ln(k+0.5)   - mu) / sigma)
               - Phi((ln(k-0.5)   - mu) / sigma)      for 2 <= k <= cap-1
    P(m = cap) = 1 - Phi((ln(cap-0.5) - mu) / sigma)

The clamp at 1 absorbs the entire lower tail and the clamp at cap absorbs
the upper tail, which is why the k=1 and k=cap terms have one-sided
bounds.

An earlier version solved this by Monte Carlo bisection. That estimator is
biased by the round() and clamp() steps (they break the symmetry
antithetic sampling relies on), which left a systematic error of roughly
0.1-0.2 percentage points of house edge -- real, and correctly flagged by
tests.py. Solving the CDF directly removes sampling error entirely, so
the realised edge is the target edge by construction.
"""

import math
import random

# ---------------------------------------------------------------- wheel
SEGMENTS = {"white": 23, "black": 23, "blue": 4, "orange": 2, "red": 1}
TOTAL = sum(SEGMENTS.values())          # 53
COLORS = tuple(SEGMENTS)
COST_PER_COLOUR = 10
FLAT_DOUBLE = ("white", "black")        # specified as a flat double

SIGMA = 1.2
CAPS = {"blue": 100, "orange": 200, "red": 500}

# Minimum multiplier. Raising the floor shifts probability mass out of the
# lower tail into the floor value, which RAISES the mean for a given mu.
# mu is therefore re-solved below, so the house edge still lands exactly on
# target. Caps are unchanged.
MIN_MULT = {"blue": 3, "orange": 5, "red": 12}

EDGE_CHOICES = (3, 5, 8, 10)

_SQRT2 = math.sqrt(2.0)


def _phi(x):
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(x / _SQRT2))


def exact_mean_multiplier(mu, sigma=SIGMA, cap=100, floor=1):
    """E[clamp(round(exp(mu + sigma*Z)), floor, cap)], computed exactly.

    The clamp absorbs both tails, but at OPPOSITE edges:

        P(m = floor) = Phi((ln(floor+0.5) - mu)/sigma)
        P(m = k)     = Phi((ln(k+0.5) - mu)/sigma)
                     - Phi((ln(k-0.5) - mu)/sigma)   for floor < k < cap
        P(m = cap)   = 1 - Phi((ln(cap-0.5) - mu)/sigma)

    The floor sits at floor+0.5 because it absorbs everything BELOW it (a
    floor of 3 collects every draw that would have rounded under 3), while
    the cap sits at cap-0.5 because it absorbs everything ABOVE it. These
    telescope to a total probability of exactly 1.
    """
    if cap <= floor:
        return float(floor)
    total = floor * _phi((math.log(floor + 0.5) - mu) / sigma)
    for k in range(floor + 1, cap):
        hi = _phi((math.log(k + 0.5) - mu) / sigma)
        lo = _phi((math.log(k - 0.5) - mu) / sigma)
        total += k * (hi - lo)
    total += cap * (1.0 - _phi((math.log(cap - 0.5) - mu) / sigma))
    return total


def target_mean(colour, edge_pct):
    """Mean multiplier that yields exactly the requested house edge."""
    return (1 - edge_pct / 100) * TOTAL / SEGMENTS[colour]


def _solve_mu(colour, edge_pct, sigma=SIGMA):
    cap = CAPS[colour]
    floor = MIN_MULT[colour]
    want = target_mean(colour, edge_pct)
    lo = math.log(want) - 4 * sigma
    hi = math.log(want) + 4 * sigma
    for _ in range(80):
        mid = (lo + hi) / 2
        if exact_mean_multiplier(mid, sigma, cap, floor) < want:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


_MU_CACHE = {}


def mu_for(colour, edge_pct):
    snapped = pricing_key(edge_pct)
    key = (colour, snapped)
    if key not in _MU_CACHE:
        _MU_CACHE[key] = _solve_mu(colour, snapped)
    return _MU_CACHE[key]


def pricing_key(edge_pct):
    return min(EDGE_CHOICES, key=lambda k: abs(k - edge_pct))


# ---------------------------------------------------------------- game api
def house_edge(colour, edge_pct=5.0):
    """Exact house edge. Exact for white/black; by construction otherwise."""
    if colour in FLAT_DOUBLE:
        return 1 - (SEGMENTS[colour] / TOTAL) * 2
    return pricing_key(edge_pct) / 100


def roll(colour, edge_pct=5.0):
    """Draw the multiplier for a landed colour. Always an int."""
    if colour in FLAT_DOUBLE:
        return 2
    cap = CAPS[colour]
    floor = MIN_MULT[colour]
    raw = math.exp(random.gauss(mu_for(colour, edge_pct), SIGMA))
    return max(floor, min(cap, round(raw)))


def hit_probability(colour):
    return SEGMENTS[colour] / TOTAL


def selection_edge(chosen, edge_pct=5.0):
    return sum(house_edge(c, edge_pct) for c in chosen)


def ev_per_round(chosen, edge_pct=5.0):
    """Expected point change for the player on one round."""
    return -COST_PER_COLOUR * selection_edge(chosen, edge_pct)


def edge_table(edge_pct=5.0):
    return {c: house_edge(c, edge_pct) for c in COLORS}


def verify(edge_pct=5.0, samples=400_000):
    """Confirm the sampler reproduces the exactly-priced distribution."""
    key = pricing_key(edge_pct)
    print(f"verifying sigma={SIGMA} at target edge {key}%, {samples:,} samples/colour")
    print("exact target comes from the CDF, measured is the live sampler\n")
    print(f"{'colour':<8}{'exact mean':>12}{'measured':>11}{'median':>8}{'min':>6}"
          f"{'max':>6}{'P(>=100x)':>11}{'edge exact':>12}{'edge meas':>11}")
    print("-" * 85)
    for c in COLORS:
        mu = None if c in FLAT_DOUBLE else mu_for(c, key)
        cap = CAPS.get(c, 2)
        floor = MIN_MULT.get(c, 2)
        vals = [roll(c, key) for _ in range(samples)]
        mean = sum(vals) / len(vals)
        vals.sort()
        exact = (2.0 if c in FLAT_DOUBLE
                 else exact_mean_multiplier(mu, SIGMA, cap, floor))
        e_exact = 1 - hit_probability(c) * exact
        e_meas = 1 - hit_probability(c) * mean
        print(f"{c:<8}{exact:>12.3f}{mean:>11.3f}{vals[samples//2]:>8}"
              f"{vals[0]:>6}{vals[-1]:>6}"
              f"{sum(1 for v in vals if v >= 100)/samples*100:>10.2f}%"
              f"{e_exact*100:>11.3f}%{e_meas*100:>10.3f}%")
