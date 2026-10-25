"""Family-cluster bootstrap.

Cases within a scenario family share a template, and replicates, follow-ups and search
samples are repeated measurements, so none of them is an independent draw. The bootstrap
therefore resamples *families* with replacement and recomputes each statistic as a ratio of
pooled sums over every unit in the drawn families. Paired comparisons apply the same family
draw to both conditions.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence

N_DRAWS = 2000
BOOT_SEED = 1684

# A unit is (family_id, numerator, denominator) for one ratio statistic.
Units = Sequence[tuple[str, float, float]]


def ratio(units: Units) -> float | None:
    den = sum(d for _, _, d in units)
    return None if den == 0 else sum(n for _, n, _ in units) / den


def _by_family(units: Units) -> dict[str, tuple[float, float]]:
    out: dict[str, list[float]] = {}
    for fam, n, d in units:
        acc = out.setdefault(fam, [0.0, 0.0])
        acc[0] += n
        acc[1] += d
    return {k: (v[0], v[1]) for k, v in out.items()}


def _percentile(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    pos = q * (len(xs) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def cluster_bootstrap(
    stat: Callable[[list[str]], float | None],
    families: list[str],
    n_draws: int = N_DRAWS,
    seed: int = BOOT_SEED,
) -> tuple[float, float] | None:
    """95% percentile interval of ``stat`` over family resamples. ``stat`` receives the drawn
    family list (with repeats) and returns a value or ``None`` when undefined."""
    if not families:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(n_draws):
        draw = [families[rng.randrange(len(families))] for _ in families]
        v = stat(draw)
        if v is not None:
            vals.append(v)
    if len(vals) < n_draws * 0.5:
        return None
    return _percentile(vals, 0.025), _percentile(vals, 0.975)


def ratio_ci(units: Units, families: list[str] | None = None, **kw) -> tuple[float, float] | None:
    fam_sums = _by_family(units)
    fams = families or sorted(fam_sums)

    def stat(draw: list[str]) -> float | None:
        n = sum(fam_sums.get(f, (0.0, 0.0))[0] for f in draw)
        d = sum(fam_sums.get(f, (0.0, 0.0))[1] for f in draw)
        return None if d == 0 else n / d

    return cluster_bootstrap(stat, fams, **kw)


def paired_diff_ci(units_a: Units, units_b: Units, **kw) -> tuple[float, float] | None:
    """Interval for ratio(a) - ratio(b) with the same family draw applied to both."""
    fa, fb = _by_family(units_a), _by_family(units_b)
    fams = sorted(set(fa) | set(fb))

    def stat(draw: list[str]) -> float | None:
        na = sum(fa.get(f, (0, 0))[0] for f in draw)
        da = sum(fa.get(f, (0, 0))[1] for f in draw)
        nb = sum(fb.get(f, (0, 0))[0] for f in draw)
        db = sum(fb.get(f, (0, 0))[1] for f in draw)
        if da == 0 or db == 0:
            return None
        return na / da - nb / db

    return cluster_bootstrap(stat, fams, **kw)
