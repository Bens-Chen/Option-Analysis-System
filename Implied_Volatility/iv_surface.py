import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


def current_otm_surface_nodes(calls, puts, forward, T, atm_iv=None):
    if forward <= 0 or T <= 0:
        return pd.DataFrame()
    rows = []
    for option_kind, table in [("put", puts), ("call", calls)]:
        if table.empty:
            continue
        for _, row in table.iterrows():
            strike = float(row.get("strike", 0) or 0)
            iv = float(row.get("impliedVolatility", 0) or 0)
            if strike <= 0 or iv <= 0 or iv > 5.0 or not np.isfinite(iv):
                continue
            if option_kind == "put" and strike >= forward:
                continue
            if option_kind == "call" and strike <= forward:
                continue
            rows.append(
                {
                    "strike": strike,
                    "moneyness": strike / forward,
                    "log_moneyness": np.log(strike / forward),
                    "impliedVolatility": iv,
                    "option_kind": option_kind,
                }
            )

    nodes = pd.DataFrame(rows)
    if nodes.empty:
        return nodes
    atm_iv = _resolve_atm_iv(nodes, atm_iv)
    denominator = atm_iv * np.sqrt(T)
    if denominator <= 0 or not np.isfinite(denominator):
        return pd.DataFrame()
    nodes["standardized_moneyness"] = nodes["log_moneyness"] / denominator
    nodes.attrs["atm_iv"] = atm_iv
    nodes = (
        nodes.groupby("standardized_moneyness", as_index=False)
        .agg(
            {
                "strike": "median",
                "moneyness": "median",
                "log_moneyness": "median",
                "impliedVolatility": "median",
                "option_kind": "first",
            }
        )
        .sort_values("standardized_moneyness")
        .reset_index(drop=True)
    )
    nodes.attrs["atm_iv"] = atm_iv
    return nodes


def current_otm_surface_iv(calls, puts, forward, strike, T, atm_iv=None):
    if forward <= 0:
        raise ValueError("forward must be positive.")
    if T <= 0:
        raise ValueError("T must be positive.")
    nodes = current_otm_surface_nodes(calls, puts, forward, T, atm_iv=atm_iv)
    if nodes.empty:
        raise ValueError("Not enough OTM IV nodes to build a current IV surface slice.")
    resolved_atm_iv = nodes.attrs.get("atm_iv")
    if resolved_atm_iv is None:
        resolved_atm_iv = _resolve_atm_iv(nodes, atm_iv)
    atm_iv = float(resolved_atm_iv)
    target_log_moneyness = np.log(float(strike) / float(forward))
    target_moneyness = target_log_moneyness / (atm_iv * np.sqrt(T))

    x = nodes["standardized_moneyness"].to_numpy(dtype=float)
    y = nodes["impliedVolatility"].to_numpy(dtype=float)
    if len(nodes) >= 3 and x.min() <= target_moneyness <= x.max():
        interpolator = PchipInterpolator(x, y, extrapolate=False)
        surface_iv = float(interpolator(target_moneyness))
        if np.isfinite(surface_iv) and surface_iv > 0:
            return surface_iv, "current OTM IV surface"

    nearest = nodes.iloc[(nodes["standardized_moneyness"] - target_moneyness).abs().argmin()]
    return float(nearest["impliedVolatility"]), "nearest OTM IV node"


def _resolve_atm_iv(nodes, atm_iv=None):
    if atm_iv is not None and np.isfinite(atm_iv) and atm_iv > 0:
        return float(atm_iv)
    nearest_atm = nodes.iloc[nodes["log_moneyness"].abs().argmin()]
    resolved = float(nearest_atm["impliedVolatility"])
    if resolved <= 0 or not np.isfinite(resolved):
        raise ValueError("Could not resolve a positive ATM implied volatility.")
    return resolved
