"""
RTP = expected return to player / total stake wagered.

For a selection S (|S| = k colours, stake = 10k per round):

    E[payout] = 10 * sum over c in S of (n_c / 53) * E[multiplier_c]
    RTP(S)    = E[payout] / (10k) = mean over c in S of RTP(c)

So a multi-colour bet's RTP is the plain average of its constituent
colours' RTPs -- each selected colour counts equally regardless of how
many wheel segments it covers. That is a direct consequence of the payout
rule: losing colours' stakes are forfeited, so the stake is k x 10 but only
one colour ever pays.

Per-colour RTP:
    RTP(c) = (n_c / 53) * E[multiplier_c]
white/black are a flat 2x, so their RTP is fixed at (23/53)*2 and the
--edge flag does NOT move them. The rare colours are priced to the target
edge exactly.
"""

import random

import pricing
from pricing import COST_PER_COLOUR, TOTAL

GROUPS = {
    "red": ["red"],
    "orange": ["orange"],
    "blue": ["blue"],
    "white": ["white"],
    "black": ["black"],
    "bonus": ["red", "orange", "blue"],
    "white,black": ["white", "black"],
    "all": list(pricing.COLORS),
}


def colour_rtp(colour, edge_pct):
    """Exact RTP for a single-colour bet."""
    if colour in pricing.FLAT_DOUBLE:
        em = 2.0
    else:
        em = pricing.exact_mean_multiplier(
            pricing.mu_for(colour, edge_pct), pricing.SIGMA,
            pricing.CAPS[colour], pricing.MIN_MULT[colour])
    return (pricing.SEGMENTS[colour] / TOTAL) * em


def selection_rtp(chosen, edge_pct):
    return sum(colour_rtp(c, edge_pct) for c in chosen) / len(chosen)


def main():
    print("=" * 76)
    print("PER-COLOUR RTP AND HOUSE EDGE")
    print("=" * 76)
    for edge in pricing.EDGE_CHOICES:
        tag = "  (default)" if edge == 5 else ""
        print(f"\n  --edge {edge}{tag}")
        print(f"  {'colour':<9}{'segs':>6}{'hit %':>8}{'E[mult]':>10}"
              f"{'RTP':>9}{'edge':>8}")
        print("  " + "-" * 50)
        for c in pricing.COLORS:
            rtp = colour_rtp(c, edge)
            em = 2.0 if c in pricing.FLAT_DOUBLE else pricing.target_mean(c, edge)
            print(f"  {c:<9}{pricing.SEGMENTS[c]:>6}"
                  f"{pricing.SEGMENTS[c]/TOTAL*100:>7.2f}%{em:>10.3f}"
                  f"{rtp*100:>8.2f}%{(1-rtp)*100:>7.2f}%")

    print()
    print("=" * 76)
    print("RTP BY BET SELECTION  (what a player actually chooses)")
    print("=" * 76)
    hdr = f"  {'selection':<14}{'stake':>7}"
    for edge in pricing.EDGE_CHOICES:
        hdr += f"{str(edge)+'% RTP':>11}"
    hdr += f"{'edge':>9}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for name, sel in GROUPS.items():
        line = f"  {name:<14}{COST_PER_COLOUR*len(sel):>7}"
        rtps = []
        for edge in pricing.EDGE_CHOICES:
            r = selection_rtp(sel, edge)
            rtps.append(r)
            line += f"{r*100:>10.2f}%"
        line += f"{(1-rtps[1])*100:>8.2f}%"
        print(line)

    print()
    print("  the 'edge' column is the default --edge 5 setting")

    # ---------------------------------------------------------- confirmation
    print()
    print("=" * 76)
    print("MONTE CARLO CONFIRMATION AT --edge 5 (2,000,000 rounds each)")
    print("=" * 76)
    random.seed(7)
    wheel = [c for c in pricing.COLORS for _ in range(pricing.SEGMENTS[c])]
    print(f"  {'selection':<14}{'analytic RTP':>14}{'measured RTP':>14}"
          f"{'error':>10}")
    print("  " + "-" * 52)
    n = 2_000_000
    for name, sel in GROUPS.items():
        stake = COST_PER_COLOUR * len(sel)
        returned = 0
        for _ in range(n):
            landed = random.choice(wheel)
            if landed in sel:
                returned += COST_PER_COLOUR * pricing.roll(landed, 5.0)
        meas = returned / (n * stake)
        exact = selection_rtp(sel, 5.0)
        print(f"  {name:<14}{exact*100:>13.2f}%{meas*100:>13.2f}%"
              f"{(meas-exact)*100:>+9.2f}pp")

    print()
    print("=" * 76)
    print("THE NUMBER THAT MATTERS FOR DISCLOSURE")
    print("=" * 76)
    worst = min(colour_rtp(c, 5.0) for c in pricing.COLORS)
    print(f"  lowest RTP a player can encounter : {worst*100:.2f}%  "
          f"(white or black alone)")
    print(f"  highest RTP a player can encounter: "
          f"{max(colour_rtp(c, 5.0) for c in pricing.COLORS)*100:.2f}%  "
          f"(red, orange or blue alone)")
    print(f"  RTP of the 'all' bet              : "
          f"{selection_rtp(GROUPS['all'], 5.0)*100:.2f}%")
    print()
    print("  white/black are pinned at 86.79% by the flat 2x rule and cannot")
    print("  be re-priced by --edge. On a 46/53 coverage they are also where")
    print("  the majority of volume sits, so they dominate the blended RTP.")
    print()
    print("  if you need ONE headline figure, a player-mix-weighted average")
    print("  must be computed from real bet distribution -- there is no")
    print("  defensible single number without it.")


if __name__ == "__main__":
    main()