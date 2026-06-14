import math

from scipy.optimize import brentq
from scipy.stats import norm

from Methods.black_scholes import BS
from Methods.crr import CRR_O_n


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
    pricing_model="BS",
    option_style="European",
    steps=200,
    lower=1e-4,
    upper=5.0,
):
    if market_price <= 0:
        raise ValueError("market_price must be positive.")

    def pricing_error(sigma):
        if pricing_model == "CRR":
            model_price = crr_option_price(S, K, r, q, sigma, T, option_kind, option_style, steps)
        else:
            model_price = option_price_from_bs(S, K, r, q, sigma, T, option_kind)
        return model_price - market_price

    try:
        return brentq(pricing_error, lower, upper)
    except ValueError as exc:
        raise ValueError("Could not solve implied volatility for this contract.") from exc


def crr_option_price(S, K, r, q, sigma, T, option_kind, option_style="American", steps=200):
    call, put = CRR_O_n(S, K, r, q, sigma, T, steps, option_type=option_style)
    return call if option_kind == "call" else put


def crr_greeks_by_bump(
    S,
    K,
    r,
    q,
    sigma,
    T,
    option_kind,
    option_style="American",
    steps=200,
    spot_bump=0.01,
    vol_bump=0.01,
    rate_bump=0.0001,
    time_bump_days=1,
):
    if sigma <= 0 or T <= 0:
        raise ValueError("sigma and T must be positive.")

    dS = max(S * spot_bump, 0.01)
    dT = min(time_bump_days / 365, max(T / 2, 1e-6))

    price = crr_option_price(S, K, r, q, sigma, T, option_kind, option_style, steps)
    price_up = crr_option_price(S + dS, K, r, q, sigma, T, option_kind, option_style, steps)
    price_down = crr_option_price(S - dS, K, r, q, sigma, T, option_kind, option_style, steps)
    vol_up = crr_option_price(S, K, r, q, sigma + vol_bump, T, option_kind, option_style, steps)
    rate_up = crr_option_price(S, K, r + rate_bump, q, sigma, T, option_kind, option_style, steps)
    shorter_time = crr_option_price(S, K, r, q, sigma, T - dT, option_kind, option_style, steps)

    return {
        "model_price": price,
        "delta": (price_up - price_down) / (2 * dS),
        "gamma": (price_up - 2 * price + price_down) / (dS**2),
        "theta_per_year": (shorter_time - price) / dT,
        "theta_per_day": (shorter_time - price) / time_bump_days,
        "vega": (vol_up - price) / (vol_bump * 100),
        "rho": (rate_up - price) / (rate_bump * 10000),
    }
