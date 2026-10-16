import numpy as np

from stats import cp_upper, cp_interval, holm, iqm, cochran_armitage, page_l, strat_boot


def test_cp_upper_zero():
    assert abs(cp_upper(0, 3e6) - 1.0e-6) < 2e-8
    assert abs(cp_upper(0, 1e7) - 3.0e-7) < 1e-8


def test_cp_interval_contains_p():
    lo, hi = cp_interval(5, 100)
    assert lo < 0.05 < hi


def test_holm_monotone():
    adj = holm([0.01, 0.04, 0.03, 0.2])
    assert np.allclose(adj, [0.04, 0.09, 0.09, 0.2])


def test_trend_tests_detect_increase():
    z, p = cochran_armitage([1, 5, 10, 20], [50, 50, 50, 50])
    assert z > 0 and p < 1e-4
    L, p2 = page_l(np.tile([0.1, 0.2, 0.3, 0.4], (10, 1)) + np.random.default_rng(10).normal(0, 0.01, (10, 4)))
    assert p2 < 1e-3


def test_iqm_and_boot():
    x = np.arange(100.0)
    assert abs(iqm(x) - 49.5) < 1e-9
    pt, lo, hi = strat_boot([x[:50], x[50:]])
    assert lo <= pt <= hi
