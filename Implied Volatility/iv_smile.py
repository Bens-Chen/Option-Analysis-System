import math
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from Methods.black_scholes import BS


def _bs_price(S, K, r, q, sigma, T, option_kind):
    call_price, put_price = BS(S, K, r, q, sigma, T)
    if option_kind == "call":
        return call_price
    if option_kind == "put":
        return put_price
    raise ValueError("option_kind must be 'call' or 'put'.")


def implied_volatility_bs(
    S,
    K,
    r,
    q,
    T,
    market_price,
    option_kind="call",
    lower_bound=1e-6,
    upper_bound=5.0,
    tolerance=1e-8,
    max_iterations=200,
):
    """Use bisection to find the BS implied volatility for one option."""
    if S <= 0 or K <= 0:
        raise ValueError("S and K must be positive.")
    if T <= 0:
        raise ValueError("T must be positive.")
    if market_price <= 0:
        raise ValueError("market_price must be positive.")

    def objective(sigma):
        return _bs_price(S, K, r, q, sigma, T, option_kind) - market_price

    low = lower_bound
    high = upper_bound
    f_low = objective(low)
    f_high = objective(high)

    if f_low * f_high > 0:
        raise ValueError(
            "Cannot bracket implied volatility. Check market_price or widen bounds."
        )

    for _ in range(max_iterations):
        mid = (low + high) / 2
        f_mid = objective(mid)

        if abs(f_mid) < tolerance:
            return mid

        if f_low * f_mid < 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid

    return (low + high) / 2


def IV_smile(
    S,
    K_list,
    r,
    q,
    T,
    market_price_list,
    option_kind="call",
    skip_errors=False,
):
    """Calculate one implied volatility for each strike."""
    option_data = sorted(zip(K_list, market_price_list))

    smile = []
    for K, market_price in option_data:
        try:
            iv = implied_volatility_bs(
                S=S,
                K=K,
                r=r,
                q=q,
                T=T,
                market_price=market_price,
                option_kind=option_kind,
            )
        except ValueError:
            if skip_errors:
                continue
            raise
        smile.append(
            {
                "strike": K,
                "market_price": market_price,
                "implied_volatility": iv,
            }
        )

    return smile


def IV_smile_arrays(
    S,
    K_list,
    r,
    q,
    T,
    market_price_list,
    option_kind="call",
    skip_errors=False,
):
    """Return strikes and IVs as arrays, which is convenient for plotting."""
    smile = IV_smile(S, K_list, r, q, T, market_price_list, option_kind, skip_errors)
    strikes = np.array([row["strike"] for row in smile], dtype=float)
    implied_volatilities = np.array(
        [row["implied_volatility"] for row in smile],
        dtype=float,
    )
    return strikes, implied_volatilities


if __name__ == "__main__":
    S = 100
    K_list = [90, 95, 100, 105, 110]
    market_price_list = [12.0, 8.0, 5.0, 2.8, 1.4]

    result = IV_smile(
        S=S,
        K_list=K_list,
        r=0.04,
        q=0.0,
        T=30 / 365,
        market_price_list=market_price_list,
        option_kind="call",
    )

    for row in result:
        print(row)
