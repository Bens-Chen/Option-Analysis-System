"""Implied volatility.

Learning versions:
    Implied_Volatility/constant_IV.py -> Bisection(), Newtons(),
                                         implied_volatility_bisection()
    Option_System/analytics.py        -> implied_volatility_from_price()

Here there is one entry point. The BS model runs a vectorised bisection over
the whole array at once (robust, no derivative needed); the CRR model solves
each contract with scipy's brentq.
"""

import numpy as np
from scipy.optimize import brentq

from optcore._utils import maybe_scalar, prepare
from optcore.pricing import bs_price, crr_price


def implied_vol(
    price,
    S,
    K,
    r,
    q,
    T,
    kind="call",
    model="bs",
    style="american",
    steps=200,
    lower=1e-4,
    upper=5.0,
    tol=1e-8,
    max_iter=100,
):
    """Solve sigma such that model price == market price.

    Returns NaN (instead of raising) for contracts with no solution, e.g. a
    price below intrinsic value, T <= 0, or a price needing sigma > upper.
    That keeps a scan over thousands of warrants from stopping on one bad row.
    """
    model_l = str(model).lower()
    if model_l not in {"bs", "crr"}:
        raise ValueError("model must be 'bs' or 'crr'.")

    is_call, P, S_, K_, r_, q_, T_ = prepare(kind, price, S, K, r, q, T)
    kind_arr = np.where(is_call, "call", "put")

    if model_l == "bs":
        result = _bs_bisection(P, S_, K_, r_, q_, T_, kind_arr, lower, upper, tol, max_iter)
    else:
        result = np.full(P.shape, np.nan)
        for idx in np.ndindex(P.shape):
            result[idx] = _crr_brentq(
                P[idx], S_[idx], K_[idx], r_[idx], q_[idx], T_[idx], kind_arr[idx], style, steps, lower, upper, tol
            )
    return maybe_scalar(result, price, S, K, r, q, T, kind)


def _bs_bisection(P, S, K, r, q, T, kind_arr, lower, upper, tol, max_iter):
    lo = np.full(P.shape, lower)
    hi = np.full(P.shape, upper)
    p_lo = bs_price(S, K, r, q, lo, T, kind_arr)
    p_hi = bs_price(S, K, r, q, hi, T, kind_arr)
    solvable = (T > 0) & (P > 0) & np.isfinite(P) & (P >= p_lo) & (P <= p_hi)

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        above = bs_price(S, K, r, q, mid, T, kind_arr) > P  # price rises with sigma
        hi = np.where(above, mid, hi)
        lo = np.where(above, lo, mid)
        if np.all((hi - lo)[solvable] < tol):
            break
    return np.where(solvable, 0.5 * (lo + hi), np.nan)


def _crr_brentq(P, S, K, r, q, T, kind, style, steps, lower, upper, tol):
    if not (T > 0 and P > 0 and np.isfinite(P)):
        return np.nan

    def err(sig):
        return crr_price(S, K, r, q, sig, T, kind, style, steps) - P

    try:
        f_lo, f_hi = err(lower), err(upper)
        if f_lo * f_hi > 0:
            return np.nan
        return brentq(err, lower, upper, xtol=tol)
    except ValueError:
        return np.nan
