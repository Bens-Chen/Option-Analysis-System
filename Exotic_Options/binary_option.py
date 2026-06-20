"""Binary option pricing formulas."""

import math
from scipy.stats import norm


def cash_or_nothing_binary_price(S, K, r, q, sigma, T, option_kind="call", cash_payoff=1.0):

    d2 = (math.log(S / K) + (r - q - 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    discount = math.exp(-r * T)

    if option_kind == "call":
        probability = norm.cdf(d2)
    elif option_kind == "put":
        probability = norm.cdf(-d2)
    else:
        raise ValueError("option_kind must be 'call' or 'put'.")

    return cash_payoff * discount * probability


def asset_or_nothing_binary_price(S, K, r, q, sigma, T, option_kind="call"):

    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    forward_discount = S * math.exp(-q * T)

    if option_kind == "call":
        probability = norm.cdf(d1)
    elif option_kind == "put":
        probability = norm.cdf(-d1)
    else:
        raise ValueError("option_kind must be 'call' or 'put'.")

    return forward_discount * probability
