import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

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


def implied_volatility_bs(S,K,r,q,T,market_price,option_kind="call",lower_bound=1e-6,upper_bound=5.0,tolerance=1e-8,max_iterations=200):
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


def IV_smile(S,K_list,r,q,T,market_price_list,option_kind="call",skip_errors=False):
    """Calculate one implied volatility for each strike."""
    option_data = sorted(zip(K_list, market_price_list))

    smile = []
    for K, market_price in option_data:
        try:
            iv = implied_volatility_bs(S=S, K=K,r=r,q=q,T=T,market_price=market_price,option_kind=option_kind)
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


def svi_total_variance(log_moneyness, a, b, rho, m, sigma):
    k = log_moneyness
    return a + b * (rho * (k - m) + ((k - m) ** 2 + sigma**2) ** 0.5)


def _svi_parameters_are_valid(a, b, rho, m, sigma):
    if a < 0 or b <= 0 or abs(rho) >= 1 or sigma <= 0:
        return False
    return a + b * sigma * math.sqrt(1 - rho**2) >= -1e-10


def _svi_density_is_nonnegative(k_grid, params):
    total_variance = svi_total_variance(k_grid, *params)
    if np.any(~np.isfinite(total_variance)) or np.any(total_variance <= 0):
        return False

    dk = k_grid[1] - k_grid[0]
    dw = np.gradient(total_variance, dk)
    d2w = np.gradient(dw, dk)
    g = (
        (1 - k_grid * dw / (2 * total_variance)) ** 2
        - (dw / 2) ** 2 * (0.25 + 1 / total_variance)
        + d2w / 2
    )
    return bool(np.all(g >= -1e-4))


def _svi_objective(params, log_moneyness, implied_volatilities, T):
    a, b, rho, m, sigma = params
    if not _svi_parameters_are_valid(a, b, rho, m, sigma):
        return 1e9

    total_variance = svi_total_variance(log_moneyness, a, b, rho, m, sigma)
    if np.any(~np.isfinite(total_variance)) or np.any(total_variance <= 0):
        return 1e9

    fitted_iv = np.sqrt(total_variance / T)
    return float(np.mean((fitted_iv - implied_volatilities) ** 2))


def fit_svi_smile(strikes, implied_volatilities, forward, T):
    """Fit raw SVI to discrete IV points and return smooth smile data."""
    if forward <= 0:
        raise ValueError("forward must be positive.")
    if T <= 0:
        raise ValueError("T must be positive.")

    strikes = np.asarray(strikes, dtype=float)
    implied_volatilities = np.asarray(implied_volatilities, dtype=float)
    valid = (
        np.isfinite(strikes)
        & np.isfinite(implied_volatilities)
        & (strikes > 0)
        & (implied_volatilities > 0)
    )
    strikes = strikes[valid]
    implied_volatilities = implied_volatilities[valid]
    if len(strikes) < 5:
        raise ValueError("At least five valid IV points are recommended for SVI fitting.")

    k = np.log(strikes / forward)
    total_variance = implied_volatilities**2 * T
    atm_variance = max(float(total_variance[np.argmin(np.abs(k))]), 1e-8)
    k_bound = max(float(np.max(np.abs(k))) * 2, 0.25)
    bounds = [
        (0.0, max(10.0, atm_variance * 10)),
        (1e-6, 10.0),
        (-0.999, 0.999),
        (-k_bound, k_bound),
        (1e-4, 5.0),
    ]
    starts = [
        [atm_variance * 0.8, 0.1, -0.3, 0.0, 0.2],
        [atm_variance * 0.5, 0.3, -0.5, 0.0, 0.3],
        [atm_variance * 0.9, 0.05, 0.0, 0.0, 0.15],
        [atm_variance * 0.7, 0.2, -0.2, 0.05, 0.25],
        [atm_variance * 0.7, 0.2, 0.2, -0.05, 0.25],
    ]

    candidates = []
    for start in starts:
        result = minimize(
            _svi_objective,
            x0=start,
            args=(k, implied_volatilities, T),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 1000, "ftol": 1e-12},
        )
        if result.success and np.isfinite(result.fun):
            candidates.append((float(result.fun), result.x))

    if not candidates:
        raise ValueError("Could not fit SVI smile from these IV points.")

    _, params = min(candidates, key=lambda item: item[0])

    smooth_strikes = np.linspace(float(strikes.min()), float(strikes.max()), 100)
    smooth_k = np.log(smooth_strikes / forward)
    smooth_total_variance = svi_total_variance(smooth_k, *params)
    smooth_iv = np.sqrt(np.maximum(smooth_total_variance / T, 0))
    fitted_iv = np.sqrt(np.maximum(svi_total_variance(k, *params) / T, 0))
    rmse = float(np.sqrt(np.mean((fitted_iv - implied_volatilities) ** 2)))
    density_grid = np.linspace(float(k.min()), float(k.max()), 200)
    return {
        "params": {
            "a": float(params[0]),
            "b": float(params[1]),
            "rho": float(params[2]),
            "m": float(params[3]),
            "sigma": float(params[4]),
        },
        "smooth_strikes": smooth_strikes,
        "smooth_iv": smooth_iv,
        "rmse": rmse,
        "n_obs": int(len(strikes)),
        "density_check": _svi_density_is_nonnegative(density_grid, params),
    }


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
