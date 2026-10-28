"""Family-cluster bootstrap behaves like a cluster bootstrap."""

from warranted_revision import stats


def test_duplicating_units_within_families_does_not_shrink_interval():
    base = [("f1", 1, 1), ("f2", 0, 1), ("f3", 1, 1), ("f4", 0, 1), ("f5", 1, 1)]
    many = [u for u in base for _ in range(50)]  # 50 near-duplicate cases per family
    ci_few = stats.ratio_ci(base, n_draws=500)
    ci_many = stats.ratio_ci(many, n_draws=500)
    assert ci_few == ci_many
    assert ci_many[1] - ci_many[0] > 0.5  # five families: wide, as it should be


def test_deterministic_and_paired():
    u = [("f1", 3, 4), ("f2", 1, 4), ("f3", 2, 4)]
    assert stats.ratio_ci(u, n_draws=300) == stats.ratio_ci(u, n_draws=300)
    assert stats.paired_diff_ci(u, u, n_draws=300) == (0.0, 0.0)
    assert stats.ratio(u) == 0.5
    assert stats.ratio([]) is None
