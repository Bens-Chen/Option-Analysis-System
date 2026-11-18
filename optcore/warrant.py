"""Warrant helpers.

A Taiwan warrant is an option on `ratio` shares of the underlying
(TEJ column 目前行使比例, e.g. 0.051 shares per warrant unit), so

    warrant price = ratio * option price
    warrant Greeks = ratio * option Greeks (per warrant unit)

`T` is in years. TEJ's 剩餘期間(日) is calendar days, so use days / 365.
"""

from optcore.greeks import bs_greeks
from optcore.iv import implied_vol
from optcore.pricing import bs_price, crr_price


def warrant_price(S, K, r, q, sigma, T, ratio, kind="call", model="bs", style="european", steps=200):
    if model == "crr":
        option = crr_price(S, K, r, q, sigma, T, kind, style, steps)
    else:
        option = bs_price(S, K, r, q, sigma, T, kind)
    return ratio * option


def warrant_iv(warrant_price_, S, K, r, q, T, ratio, kind="call", **kwargs):
    """Implied volatility from a warrant quote (divides out the ratio first)."""
    return implied_vol(warrant_price_ / ratio, S, K, r, q, T, kind, **kwargs)


def warrant_greeks(S, K, r, q, sigma, T, ratio, kind="call"):
    """Greeks per warrant unit (option Greeks scaled by ratio)."""
    return {k: ratio * v for k, v in bs_greeks(S, K, r, q, sigma, T, kind).items()}
