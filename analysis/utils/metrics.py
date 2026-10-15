"""Small, tested metric helpers shared by every pipeline step."""
from __future__ import annotations

import numpy as np
import pandas as pd


def safe_div(num: float, den: float) -> float:
    """Division that returns NaN instead of raising / returning inf when den == 0."""
    return float(num) / float(den) if den else float("nan")


def pct(num: float, den: float, digits: int = 1) -> float:
    """Percentage (0-100) rounded to `digits`; NaN when the denominator is zero."""
    v = safe_div(num, den)
    return round(v * 100, digits) if v == v else float("nan")


def dist_summary(s: pd.Series, percentiles=(0.25, 0.5, 0.75, 0.9, 0.95, 0.99)) -> dict:
    s = pd.Series(s).dropna().astype(float)
    if s.empty:
        return {"count": 0}
    out = {"count": int(s.size), "mean": float(s.mean()), "std": float(s.std(ddof=1)) if s.size > 1 else 0.0,
           "min": float(s.min()), "max": float(s.max())}
    for p in percentiles:
        out[f"p{int(round(p * 100))}"] = float(s.quantile(p))
    return out


def tukey_upper_fence(s: pd.Series, k: float = 3.0) -> float:
    """Q3 + k*IQR. k=3 ('far out') is used for anomaly flags so only extreme values are flagged."""
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    return float(q3 + k * (q3 - q1))


def robust_z(s: pd.Series) -> pd.Series:
    """Median/MAD z-score (scaled to be comparable with a normal z)."""
    med = s.median()
    mad = (s - med).abs().median()
    if mad == 0:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return 0.6745 * (s - med) / mad


def minmax_log(s: pd.Series, cap_quantile: float = 0.99) -> pd.Series:
    """Winsorise at `cap_quantile`, log1p transform, then min-max scale to [0, 1]."""
    s = s.astype(float).clip(lower=0)
    cap = s.quantile(cap_quantile)
    t = np.log1p(s.clip(upper=cap))
    rng = t.max() - t.min()
    return (t - t.min()) / rng if rng else t * 0


def sample_size_two_proportions(p1: float, p2: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """Users per arm to detect p1 -> p2 with a two-sided two-proportion z-test (normal approximation)."""
    from scipy.stats import norm

    if not (0 < p1 < 1 and 0 < p2 < 1) or p1 == p2:
        raise ValueError("proportions must be in (0, 1) and differ")
    za, zb = norm.ppf(1 - alpha / 2), norm.ppf(power)
    pbar = (p1 + p2) / 2
    n = (za * np.sqrt(2 * pbar * (1 - pbar)) + zb * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p2 - p1) ** 2
    return int(np.ceil(n))


def share_table(s: pd.Series, name: str = "value") -> pd.DataFrame:
    vc = s.value_counts(dropna=False)
    return pd.DataFrame({name: vc.index, "count": vc.values, "pct": (vc.values / vc.sum() * 100).round(2)})
