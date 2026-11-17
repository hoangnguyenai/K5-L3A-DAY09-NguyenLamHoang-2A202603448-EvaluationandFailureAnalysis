"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb, isfinite
from numbers import Integral

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge) or not len(human):
        raise ValueError("expected nonempty paired labels")
    counts = dict(tp=0, fp=0, fn=0, tn=0)
    for truth, prediction in zip(human, judge):
        if truth not in ("PASS", POS) or prediction not in ("PASS", POS):
            raise ValueError("expected PASS or FAIL")
        key = ("t" if truth == prediction else "f") + ("p" if prediction == POS else "n")
        counts[key] += 1
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    m = confusion(human, judge)
    return (m["tp"] / max(1, m["tp"] + m["fp"]),
            m["tp"] / max(1, m["tp"] + m["fn"]))


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    m = confusion(human, judge)
    tp, fp, fn, tn = (m[k] for k in ("tp", "fp", "fn", "tn"))
    n = sum(m.values())
    chance = (tp + fn) * (tp + fp) + (tn + fp) * (tn + fn)
    if chance == n * n:
        raise ValueError("undefined kappa")
    return ((tp + tn) * n - chance) / (n * n - chance)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    if any(not isfinite(v) or not 0 <= v <= 1 for v in (observed_rate, sensitivity, specificity)):
        raise ValueError("rates must be finite probabilities")
    scale = sensitivity + specificity - 1
    if scale <= 0:
        raise ValueError("judge must have positive discrimination")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / scale))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.ndim != 1 or a.shape != b.shape or not len(a):
        raise ValueError("expected aligned nonempty per-item vectors")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("samples must be finite")
    if not 0 < confidence < 1 or n_resamples < 1:
        raise ValueError("invalid bootstrap settings")
    delta = a - b
    mean = float(delta.mean())
    if np.all(delta == delta[0]):
        return mean, mean, mean
    def difference(x, y, axis):
        return (x - y).mean(axis=axis)
    interval = bootstrap((a, b), difference, paired=True, method="percentile",
                         rng=np.random.default_rng(rng), confidence_level=confidence,
                         n_resamples=n_resamples).confidence_interval
    return mean, float(interval.low), float(interval.high)


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _validate_trials(n, c, k)
    return 1 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _validate_trials(n, c, k)
    return comb(c, k) / comb(n, k)


def _validate_trials(n: int, c: int, k: int) -> None:
    if any(isinstance(v, bool) or not isinstance(v, Integral) for v in (n, c, k)):
        raise ValueError("n, c, k must be integers")
    if not (n >= 1 and 0 <= c <= n and 1 <= k <= n):
        raise ValueError("require n >= 1, 0 <= c <= n, 1 <= k <= n")
