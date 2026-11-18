"""Vectorised option pricing.

Learning versions:
    Methods/black_scholes.py  -> BS()      (scalar, math module)
    Methods/crr.py            -> CRR_O_n() (double Python loop)
"""

import numpy as np
from scipy.special import ndtr

from optcore._utils import maybe_scalar, prepare


def _forward_intrinsic(S, K, r, q, T, is_call):
    """Discounted intrinsic value; this is the price when sigma or T is 0."""
    Tc = np.maximum(T, 0.0)
    fwd_s = S * np.exp(-q * Tc)
    pv_k = K * np.exp(-r * Tc)
    return np.where(is_call, np.maximum(fwd_s - pv_k, 0.0), np.maximum(pv_k - fwd_s, 0.0))


def bs_price(S, K, r, q, sigma, T, kind="call"):
    """Black-Scholes-Merton price for European options.

    Every argument may be a scalar or an array (they broadcast together), so a
    whole option chain is priced in one call. T <= 0 or sigma <= 0 returns the
    (discounted) intrinsic value instead of dividing by zero.
    """
    is_call, S_, K_, r_, q_, sig_, T_ = prepare(kind, S, K, r, q, sigma, T)

    live = (T_ > 0) & (sig_ > 0)
    T_safe = np.where(live, T_, 1.0)
    sig_safe = np.where(live, sig_, 1.0)
    vol_sqrt_t = sig_safe * np.sqrt(T_safe)

    d1 = (np.log(S_ / K_) + (r_ - q_ + 0.5 * sig_safe**2) * T_safe) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    disc_s = S_ * np.exp(-q_ * T_safe)
    disc_k = K_ * np.exp(-r_ * T_safe)

    call = disc_s * ndtr(d1) - disc_k * ndtr(d2)
    put = disc_k * ndtr(-d2) - disc_s * ndtr(-d1)
    price = np.where(is_call, call, put)
    price = np.where(live, price, _forward_intrinsic(S_, K_, r_, q_, T_, is_call))
    return maybe_scalar(price, S, K, r, q, sigma, T, kind)


def _crr_single(S, K, r, q, sigma, T, is_call, american, steps):
    if T <= 0 or sigma <= 0:
        return float(_forward_intrinsic(S, K, r, q, T, is_call))

    dt = T / steps
    u = np.exp(sigma * np.sqrt(dt))
    d = 1.0 / u
    p = (np.exp((r - q) * dt) - d) / (u - d)
    disc = np.exp(-r * dt)

    # Node j at step i has price S * u**(i-j) * d**j (j = number of down moves).
    j = np.arange(steps + 1)
    stock = S * u ** (steps - j) * d**j
    value = np.maximum(stock - K, 0.0) if is_call else np.maximum(K - stock, 0.0)

    for i in range(steps - 1, -1, -1):
        value = disc * (p * value[:-1] + (1.0 - p) * value[1:])
        if american:
            stock = stock[:-1] * d  # same nodes one step earlier
            exercise = np.maximum(stock - K, 0.0) if is_call else np.maximum(K - stock, 0.0)
            value = np.maximum(value, exercise)
    return float(value[0])


def crr_price(S, K, r, q, sigma, T, kind="call", style="american", steps=200):
    """Cox-Ross-Rubinstein binomial price (European or American).

    Each backward-induction step is one NumPy operation over all nodes,
    instead of the inner Python loop in Methods/crr.py.
    """
    style_l = str(style).lower()
    if style_l not in {"american", "european"}:
        raise ValueError("style must be 'american' or 'european'.")
    american = style_l == "american"

    is_call, S_, K_, r_, q_, sig_, T_ = prepare(kind, S, K, r, q, sigma, T)

    out = np.empty(S_.shape, dtype=float)
    for idx in np.ndindex(S_.shape):
        out[idx] = _crr_single(
            S_[idx], K_[idx], r_[idx], q_[idx], sig_[idx], T_[idx], bool(is_call[idx]), american, steps
        )
    return maybe_scalar(out, S, K, r, q, sigma, T, kind)
