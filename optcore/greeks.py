"""Vectorised Black-Scholes Greeks.

Learning versions:
    Option_System/analytics.py -> black_scholes_greeks() (scalar)
    Greak_Letters/             -> CRR / Monte Carlo finite-difference Greeks

Units follow analytics.py: theta per year and per calendar day,
vega and rho per 1 percentage point.
"""

import numpy as np
from scipy.special import ndtr

from optcore._utils import maybe_scalar, prepare

_INV_SQRT_2PI = 1.0 / np.sqrt(2.0 * np.pi)


def _pdf(x):
    return _INV_SQRT_2PI * np.exp(-0.5 * x * x)


def bs_greeks(S, K, r, q, sigma, T, kind="call"):
    """Return a dict of delta, gamma, theta_per_year, theta_per_day, vega, rho.

    For expired contracts (T <= 0) or sigma <= 0, delta is the exercise
    indicator (1/-1/0) and the other Greeks are 0.
    """
    is_call, S_, K_, r_, q_, sig_, T_ = prepare(kind, S, K, r, q, sigma, T)

    live = (T_ > 0) & (sig_ > 0)
    T_safe = np.where(live, T_, 1.0)
    sig_safe = np.where(live, sig_, 1.0)
    sqrt_t = np.sqrt(T_safe)

    d1 = (np.log(S_ / K_) + (r_ - q_ + 0.5 * sig_safe**2) * T_safe) / (sig_safe * sqrt_t)
    d2 = d1 - sig_safe * sqrt_t
    eq = np.exp(-q_ * T_safe)
    er = np.exp(-r_ * T_safe)
    pdf_d1 = _pdf(d1)

    delta = np.where(is_call, eq * ndtr(d1), eq * (ndtr(d1) - 1.0))
    gamma = eq * pdf_d1 / (S_ * sig_safe * sqrt_t)
    vega = S_ * eq * pdf_d1 * sqrt_t
    common_theta = -(S_ * eq * pdf_d1 * sig_safe) / (2.0 * sqrt_t)
    theta = np.where(
        is_call,
        common_theta - r_ * K_ * er * ndtr(d2) + q_ * S_ * eq * ndtr(d1),
        common_theta + r_ * K_ * er * ndtr(-d2) - q_ * S_ * eq * ndtr(-d1),
    )
    rho = np.where(is_call, K_ * T_safe * er * ndtr(d2), -K_ * T_safe * er * ndtr(-d2))

    dead_delta = np.where(is_call, (S_ > K_).astype(float), -(S_ < K_).astype(float))
    zero = np.zeros_like(S_)
    greeks = {
        "delta": np.where(live, delta, dead_delta),
        "gamma": np.where(live, gamma, zero),
        "theta_per_year": np.where(live, theta, zero),
        "theta_per_day": np.where(live, theta / 365.0, zero),
        "vega": np.where(live, vega / 100.0, zero),
        "rho": np.where(live, rho / 100.0, zero),
    }
    return {k: maybe_scalar(v, S, K, r, q, sigma, T, kind) for k, v in greeks.items()}
