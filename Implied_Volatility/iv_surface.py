import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


def current_otm_surface_iv(calls, puts, forward, strike):
    if forward <= 0:
        raise ValueError("forward must be positive.")
    nodes = current_otm_surface_nodes(calls, puts, forward)
    target_moneyness = float(strike) / float(forward)
    if nodes.empty:
        raise ValueError("Not enough OTM IV nodes to build a current IV surface slice.")

    x = nodes["moneyness"].to_numpy(dtype=float)
    y = nodes["impliedVolatility"].to_numpy(dtype=float)
    if len(nodes) >= 3 and x.min() <= target_moneyness <= x.max():
        interpolator = PchipInterpolator(x, y, extrapolate=False)
        surface_iv = float(interpolator(target_moneyness))
        if np.isfinite(surface_iv) and surface_iv > 0:
            return surface_iv, "current OTM IV surface"

    nearest = nodes.iloc[(nodes["moneyness"] - target_moneyness).abs().argmin()]
    return float(nearest["impliedVolatility"]), "nearest OTM IV node"


def current_otm_surface_nodes(calls, puts, forward):
    if forward <= 0:
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
                    "impliedVolatility": iv,
                    "option_kind": option_kind,
                }
            )

    nodes = pd.DataFrame(rows)
    if nodes.empty:
        return nodes
    nodes = (
        nodes.groupby("moneyness", as_index=False)
        .agg({"strike": "median", "impliedVolatility": "median", "option_kind": "first"})
        .sort_values("moneyness")
        .reset_index(drop=True)
    )
    return nodes
