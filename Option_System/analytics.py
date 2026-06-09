import math

from scipy.optimize import brentq
from scipy.stats import norm

from Methods.black_scholes import BS


def black_scholes_greeks(S, K, r, q, sigma, T, option_kind):
    if sigma <= 0 or T <= 0:
        raise ValueError("sigma and T must be positive.")

    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_kind == "call":
        delta = math.exp(-q * T) * norm.cdf(d1)
        rho = K * T * math.exp(-r * T) * norm.cdf(d2)
        theta = (
            -(S * math.exp(-q * T) * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * norm.cdf(d2)
            + q * S * math.exp(-q * T) * norm.cdf(d1)
        )
    elif option_kind == "put":
        delta = math.exp(-q * T) * (norm.cdf(d1) - 1)
        rho = -K * T * math.exp(-r * T) * norm.cdf(-d2)
        theta = (
            -(S * math.exp(-q * T) * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
            + r * K * math.exp(-r * T) * norm.cdf(-d2)
            - q * S * math.exp(-q * T) * norm.cdf(-d1)
        )
    else:
        raise ValueError("option_kind must be 'call' or 'put'.")

    gamma = math.exp(-q * T) * norm.pdf(d1) / (S * sigma * math.sqrt(T))
    vega = S * math.exp(-q * T) * norm.pdf(d1) * math.sqrt(T)

    return {
        "delta": delta,
        "gamma": gamma,
        "theta_per_year": theta,
        "theta_per_day": theta / 365,
        "vega": vega / 100,
        "rho": rho / 100,
    }


def option_price_from_bs(S, K, r, q, sigma, T, option_kind):
    call, put = BS(S, K, r, q, sigma, T)
    return call if option_kind == "call" else put


def implied_volatility_from_price(
    market_price,
    S,
    K,
    r,
    q,
    T,
    option_kind,
    lower=1e-4,
    upper=5.0,
):
    if market_price <= 0:
        raise ValueError("market_price must be positive.")

    def pricing_error(sigma):
        return option_price_from_bs(S, K, r, q, sigma, T, option_kind) - market_price

    try:
        return brentq(pricing_error, lower, upper)
    except ValueError as exc:
        raise ValueError("Could not solve implied volatility for this contract.") from exc
