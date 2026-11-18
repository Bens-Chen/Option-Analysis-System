"""Business logic for the web app, kept separate from HTTP routes so it can be tested directly."""

import math
import tempfile
import uuid
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from optcore import bs_greeks, bs_price, crr_price, warrant_greeks, warrant_iv
from optcore.data import merge_daily_with_terms, read_tej_daily, read_tej_terms
from optcore.data.tej import parse_issuer, parse_warrant_type


# ---------------------------------------------------------------- helpers
def clean(value):
    """Make numpy / pandas values JSON-safe (NaN and inf become None)."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return [clean(v) for v in value.tolist()]
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return None if pd.isna(value) else value.strftime("%Y-%m-%d")
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    if value is pd.NaT:
        return None
    return value


def frame_to_records(df, columns):
    present = [c for c in columns if c in df.columns]
    return [clean(row) for row in df[present].to_dict(orient="records")]


# ---------------------------------------------------------------- calculator
def calculate(S, K, r, q, sigma, T, kind, model="bs", style="european", steps=200, ratio=1.0):
    if model == "crr":
        price = crr_price(S, K, r, q, sigma, T, kind, style, steps)
    else:
        price = bs_price(S, K, r, q, sigma, T, kind)
    greeks = bs_greeks(S, K, r, q, sigma, T, kind)

    grid = np.linspace(max(0.4 * K, 0.01), 1.6 * K, 121)
    curves = {"spot": grid, "payoff": bs_price(grid, K, r, q, sigma, 0.0, kind) * ratio}
    for label, frac in (("now", 1.0), ("half", 0.5)):
        curves[label] = bs_price(grid, K, r, q, sigma, T * frac, kind) * ratio
    curves["delta"] = bs_greeks(grid, K, r, q, sigma, T, kind)["delta"]
    curves["gamma"] = bs_greeks(grid, K, r, q, sigma, T, kind)["gamma"]

    return clean({
        "price": price * ratio,
        "option_price": price,
        "bs_price": bs_price(S, K, r, q, sigma, T, kind),
        "greeks": {k: v * ratio for k, v in greeks.items()},
        "intrinsic": bs_price(S, K, r, q, sigma, 0.0, kind) * ratio,
        "curves": curves,
    })


# ---------------------------------------------------------------- US options (yfinance)
def _years_to(expiration, today=None):
    today = today or date.today()
    exp = datetime.strptime(expiration, "%Y-%m-%d").date()
    return max((exp - today).days, 1) / 365.0


# ---------------------------------------------------------------- Taiwan warrants (TEJ)
class WarrantStore:
    """Uploaded TEJ datasets kept in memory for the running server."""

    def __init__(self):
        self._data = {}

    def load(self, daily_bytes, daily_name, terms_bytes=None, terms_name=None):
        with tempfile.TemporaryDirectory() as tmp:
            daily_path = Path(tmp) / ("daily" + Path(daily_name).suffix.lower())
            daily_path.write_bytes(daily_bytes)
            daily = read_tej_daily(daily_path)
            terms = None
            if terms_bytes:
                terms_path = Path(tmp) / ("terms" + Path(terms_name).suffix.lower())
                terms_path.write_bytes(terms_bytes)
                terms = read_tej_terms(terms_path)

        if terms is not None:
            merged = merge_daily_with_terms(daily, terms)
        else:
            merged = daily.copy()
            merged["kind"] = merged["name"].map(lambda n: parse_warrant_type(n)[0])
            merged["issuer"] = merged["name"].map(parse_issuer)
            merged["ratio"] = np.nan
        dataset_id = uuid.uuid4().hex[:12]
        self._data[dataset_id] = merged
        return dataset_id, self.summary(dataset_id, has_terms=terms is not None)

    def get(self, dataset_id):
        if dataset_id not in self._data:
            raise KeyError(dataset_id)
        return self._data[dataset_id]

    def summary(self, dataset_id, has_terms=None):
        df = self.get(dataset_id)
        return clean({
            "dataset_id": dataset_id,
            "rows": len(df),
            "warrants": int(df["warrant_id"].nunique()),
            "underlyings": sorted(df["underlying_id"].dropna().unique().tolist()),
            "issuers": sorted(df["issuer"].dropna().unique().tolist()),
            "start": df["date"].min(),
            "end": df["date"].max(),
            "has_terms": has_terms if has_terms is not None else bool(df["ratio"].notna().any()),
        })


def add_model_columns(df, r, q=0.0):
    """Our IV (from the close price) and per-warrant delta. Stale (no-trade) rows are flagged."""
    out = df.copy()
    kinds = out["kind"].fillna("call").to_numpy()
    ratio = pd.to_numeric(out["ratio"], errors="coerce").to_numpy(float)
    args = dict(
        S=out["underlying_price"].to_numpy(float),
        K=out["strike"].to_numpy(float),
        r=r, q=q,
        T=out["T"].to_numpy(float),
    )
    close = pd.to_numeric(out["close"], errors="coerce").to_numpy(float)
    iv = warrant_iv(close, ratio=ratio, kind=kinds, **args)
    iv = np.where(out["kind"].notna(), iv, np.nan)
    out["iv"] = iv
    sigma = np.where(np.isfinite(iv), iv, 0.0)
    g = warrant_greeks(sigma=sigma, ratio=ratio, kind=kinds, **args)
    out["delta"] = np.where(np.isfinite(iv), g["delta"], np.nan)
    out["iv_minus_hv"] = out["iv"] - pd.to_numeric(out.get("tej_hist_vol"), errors="coerce")
    return out


SNAPSHOT_COLUMNS = [
    "warrant_id", "name", "date", "underlying_id", "underlying_name", "issuer", "kind",
    "close", "volume", "traded", "strike", "ratio", "days_to_expiry", "underlying_price",
    "iv", "tej_iv", "tej_hist_vol", "iv_minus_hv", "delta", "tej_delta",
    "effective_leverage", "moneyness_label", "tej_overvalue_pct",
]

SERIES_COLUMNS = [
    "date", "close", "volume", "traded", "underlying_price", "iv", "tej_iv",
    "tej_hist_vol", "strike", "ratio", "days_to_expiry",
]


def warrant_snapshot(df, as_of, r):
    as_of = pd.Timestamp(as_of) if as_of else df["date"].max()
    latest = df[df["date"] <= as_of].groupby("warrant_id", as_index=False).tail(1)
    latest = add_model_columns(latest, r)
    latest = latest.sort_values(["underlying_id", "kind", "strike"])
    return {"as_of": clean(as_of), "rows": frame_to_records(latest, SNAPSHOT_COLUMNS)}


def warrant_series(df, warrant_id, r):
    rows = df[df["warrant_id"] == warrant_id].sort_values("date")
    if rows.empty:
        raise KeyError(warrant_id)
    rows = add_model_columns(rows, r)
    first = rows.iloc[-1]
    return {
        "warrant_id": warrant_id,
        "name": clean(first.get("name")),
        "kind": clean(first.get("kind")),
        "issuer": clean(first.get("issuer")),
        "rows": frame_to_records(rows, SERIES_COLUMNS),
    }
