"""US options features ported from the old Streamlit app (Option_System/app.py).

Reuses the original analysis modules (strategy_engine, Risk_Management,
Implied_Volatility) so results match what the Streamlit version showed.
"""

import importlib.util
import time
from datetime import date
from importlib.machinery import SourceFileLoader
from pathlib import Path

import numpy as np
import pandas as pd

from Implied_Volatility.iv_smile import fit_svi_smile
from Market_Data.yfinance_data import (
    add_mid_prices,
    estimate_annualized_volatility,
    estimate_forward_price,
    latest_close,
    matched_option_chain_prices,
)
from Option_System.strategy_engine import (
    backtest_metrics,
    build_chain_strategy_legs,
    payoff_grid,
    rolling_strategy_backtest,
)
from Risk_Management.risk_matrix import OptionLeg, build_risk_matrix
from Risk_Management.var_es import ewma_var_es_summary, historical_var_es_summary, iv_smoothed_var_es_summary
from Risk_Management.vol_curve_monitor import vol_curve_diagnostics
from optcore import bs_greeks, implied_vol
from webapp.services import _years_to, clean, frame_to_records

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STRATEGIES = [
    "Single Option", "Long Straddle", "Short Straddle", "Long Strangle", "Short Strangle",
    "Long Call Butterfly", "Short Call Butterfly", "Long Put Butterfly", "Short Put Butterfly",
    "Bull Call Spread", "Bear Put Spread", "Ratio Call Spread", "Short Iron Condor", "Long Iron Condor",
    "Custom",
]


def _load_vix_svix():
    # The learning file has no .py extension, so load it explicitly (as app.py did).
    path = PROJECT_ROOT / "Implied_Volatility" / "vix_svix"
    loader = SourceFileLoader("vix_svix_module", str(path))
    spec = importlib.util.spec_from_loader("vix_svix_module", loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIX_SVIX_MODULE = _load_vix_svix()


# ---------------------------------------------------------------- market data cache
class MarketData:
    """Caches yfinance calls for a few minutes so the pages don't refetch on every click."""

    def __init__(self, fetch_chain, fetch_history, ttl=600, today=None):
        self._fetch_chain = fetch_chain
        self._fetch_history = fetch_history
        self._ttl = ttl
        self._cache = {}
        self.today = today

    def _cached(self, key, loader):
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < self._ttl:
            return hit[1]
        value = loader()
        self._cache[key] = (time.time(), value)
        return value

    def history(self, ticker, period="10y"):  # same window as the old Streamlit app
        return self._cached(("hist", ticker, period), lambda: self._fetch_history(ticker, period=period))

    def chain(self, ticker, expiration=None):
        return self._cached(("chain", ticker, expiration), lambda: self._fetch_chain(ticker, expiration))

    def default_expiration(self, ticker):
        available = self.chain(ticker)["expirations"]
        later = [e for e in available if _years_to(e, self.today) * 365 >= 7]
        return later[0] if later else available[0]

    def context(self, ticker, expiration, r, q):
        """Everything the US pages need for one ticker + expiry."""
        expiration = expiration or self.default_expiration(ticker)
        chain = self.chain(ticker, expiration)
        history = self.history(ticker)
        spot = latest_close(history)
        try:
            hist_vol = estimate_annualized_volatility(history)
        except ValueError:
            hist_vol = None
        T = _years_to(chain["expiration"], self.today)
        calls = add_mid_prices(chain["calls"]).assign(option_kind="call")
        puts = add_mid_prices(chain["puts"]).assign(option_kind="put")
        for table, kind in ((calls, "call"), (puts, "put")):
            table["strike"] = pd.to_numeric(table["strike"], errors="coerce")
            mids = table["midPrice"].to_numpy(float)
            table["iv"] = np.asarray(
                implied_vol(np.where(mids > 0, mids, np.nan), spot, table["strike"].to_numpy(float), r, q, T, kind),
                dtype=float,
            )
        forward = None
        try:
            forward = estimate_forward_price(matched_option_chain_prices(chain["calls"], chain["puts"]), r, T)["F"]
        except (ValueError, KeyError):
            pass
        return {
            "ticker": chain["ticker"], "expiration": chain["expiration"], "expirations": chain["expirations"],
            "chain": chain, "calls": calls, "puts": puts, "history": history,
            "spot": spot, "hist_vol": hist_vol, "forward": forward, "T": T, "r": r, "q": q,
        }


def _contract_vol(ctx, kind, strike):
    """Vol used to price a contract: its own mid-price IV, else historical vol."""
    table = ctx["calls"] if kind == "call" else ctx["puts"]
    row = table.iloc[(table["strike"] - strike).abs().argsort()[:1]]
    iv = float(row["iv"].iloc[0]) if not row.empty else np.nan
    if np.isfinite(iv) and iv > 0:
        return iv, "合約中價 IV"
    return float(ctx["hist_vol"] or 0.3), "歷史波動率（合約 IV 無法反推）"


# ---------------------------------------------------------------- chain view
def chain_view(md, ticker, expiration, r, q):
    """Chain with our own mid-price IV and Greeks next to yfinance's IV, plus SVI and VIX/SVIX."""
    ctx = md.context(ticker, expiration, r, q)
    sides = {}
    for kind, table in (("call", ctx["calls"]), ("put", ctx["puts"])):
        strikes = table["strike"].to_numpy(float)
        iv = table["iv"].to_numpy(float)
        ok = np.isfinite(iv)
        g = bs_greeks(ctx["spot"], strikes, r, q, np.where(ok, iv, 0.0), ctx["T"], kind)
        out = pd.DataFrame({
            "contract": table.get("contractSymbol"),
            "strike": strikes,
            "bid": pd.to_numeric(table.get("bid"), errors="coerce"),
            "ask": pd.to_numeric(table.get("ask"), errors="coerce"),
            "mid": table["midPrice"].to_numpy(float),
            "last": pd.to_numeric(table.get("lastPrice"), errors="coerce"),
            "volume": pd.to_numeric(table.get("volume"), errors="coerce"),
            "open_interest": pd.to_numeric(table.get("openInterest"), errors="coerce"),
            "yf_iv": pd.to_numeric(table.get("impliedVolatility"), errors="coerce"),
            "iv": iv,
        })
        for name in ("delta", "gamma", "theta_per_day", "vega"):
            out[name] = np.where(ok, g[name], np.nan)
        sides[kind] = frame_to_records(out, list(out.columns))
    return clean({
        "ticker": ctx["ticker"], "expiration": ctx["expiration"], "expirations": ctx["expirations"],
        "spot": ctx["spot"], "hist_vol": ctx["hist_vol"], "forward": ctx["forward"], "T": ctx["T"],
        "calls": sides["call"], "puts": sides["put"],
        "smile": smile_analytics(ctx),
        "strategies": STRATEGIES,
    })


# ---------------------------------------------------------------- smile, VIX/SVIX, surface
def smile_analytics(ctx):
    forward = ctx["forward"] or ctx["spot"]
    calls, puts = ctx["calls"], ctx["puts"]
    otm = pd.concat([puts[puts["strike"] <= forward], calls[calls["strike"] > forward]])
    otm = otm[np.isfinite(otm["iv"]) & (otm["iv"] > 0)]
    # Far wings have stale / wide quotes that wreck the fit; keep forward ±30%.
    otm = otm[(otm["strike"] > 0.7 * forward) & (otm["strike"] < 1.3 * forward)]
    out = {"svi": None, "svi_error": None, "vix": None, "svix": None, "vix_error": None}
    try:
        fit = fit_svi_smile(otm["strike"].to_numpy(float), otm["iv"].to_numpy(float), forward, ctx["T"])
        out["svi"] = {"strikes": fit["smooth_strikes"], "iv": fit["smooth_iv"], "rmse": fit["rmse"], "params": fit["params"]}
    except (ValueError, RuntimeError) as exc:
        out["svi_error"] = str(exc)
    try:
        matched = matched_option_chain_prices(ctx["chain"]["calls"], ctx["chain"]["puts"])
        res = VIX_SVIX_MODULE.VIX_SVIX(
            St=ctx["spot"], r=ctx["r"], T=ctx["T"], K_list=matched["strike"].tolist(),
            call_price_list=matched["call_mid"].tolist(), put_price_list=matched["put_mid"].tolist(),
        )
        out["vix"], out["svix"] = res["VIX"]["vix"], res["SVIX"]["svix"]
    except Exception as exc:  # the learning module raises plain Exceptions on thin chains
        out["vix_error"] = str(exc)
    return clean(out)


def iv_surface(md, ticker, r, q, max_expirations=8, min_days=3):
    first = md.chain(ticker)
    rows = []
    for expiration in first["expirations"][:max_expirations]:
        try:
            ctx = md.context(ticker, expiration, r, q)
        except (ValueError, KeyError):
            continue
        forward = ctx["forward"] or ctx["spot"]
        days = int(round(ctx["T"] * 365))
        if days < min_days:  # 1-2 day options have extreme IVs that flatten the rest of the surface
            continue
        for table, side in ((ctx["puts"], "put"), (ctx["calls"], "call")):
            mask = (table["strike"] < forward) if side == "put" else (table["strike"] > forward)
            mask &= np.isfinite(table["iv"]) & (table["iv"] > 0) & (table["iv"] < 3)
            mask &= (table["strike"] > 0.6 * ctx["spot"]) & (table["strike"] < 1.4 * ctx["spot"])
            for strike, iv in zip(table.loc[mask, "strike"], table.loc[mask, "iv"]):
                rows.append({"expiration": expiration, "days": days, "strike": float(strike), "iv": float(iv)})
    return clean({"ticker": first["ticker"], "nodes": rows})


# ---------------------------------------------------------------- strategy + backtest
def _strategy_legs(ctx, strategy, kind, strike, width, ratio_quantity, custom_legs):
    if strategy == "Custom":
        legs = []
        for leg in custom_legs or []:
            legs.append({
                "option_kind": leg["option_kind"], "side": leg["side"], "strike": float(leg["strike"]),
                "premium": float(leg["premium"]), "quantity": int(leg.get("quantity", 1)),
            })
        if not legs:
            raise ValueError("自訂策略至少需要一個部位")
        return legs
    table = ctx["calls"] if kind == "call" else ctx["puts"]
    selected = table.iloc[(table["strike"] - strike).abs().argsort()[:1]].iloc[0].to_dict()
    return build_chain_strategy_legs(
        strategy, selected, ctx["calls"], ctx["puts"], other_strike=width, ratio_quantity=ratio_quantity
    )


def _leg_greeks(legs, ctx, sigma):
    """Net strategy Greeks per 1 unit of underlying (long +, short −)."""
    totals = dict.fromkeys(["delta", "gamma", "theta_per_day", "vega", "rho"], 0.0)
    for leg in legs:
        g = bs_greeks(ctx["spot"], float(leg["strike"]), ctx["r"], ctx["q"], sigma, ctx["T"], leg["option_kind"])
        scale = (1 if leg["side"] == "long" else -1) * abs(int(leg.get("quantity", 1)))
        for key in totals:
            totals[key] += g[key] * scale
    return totals


def strategy_backtest(md, req):
    ctx = md.context(req["ticker"], req.get("expiration"), req["r"], req["q"])
    legs = _strategy_legs(ctx, req["strategy"], req["kind"], req["strike"], req.get("width"),
                          req.get("ratio_quantity", 2), req.get("custom_legs"))
    sigma, sigma_source = _contract_vol(ctx, req["kind"], req["strike"])
    grid = payoff_grid(ctx["spot"], legs)
    bt = rolling_strategy_backtest(
        ctx["history"], ctx["spot"], legs,
        holding_days=int(req["holding_days"]), non_overlapping=bool(req["non_overlapping"]),
        slippage_per_contract=req["slippage"], transaction_cost_per_contract=req["commission"],
        contract_multiplier=int(req["multiplier"]), risk_free_rate=ctx["r"], dividend_yield=ctx["q"],
        time_to_maturity=ctx["T"],
    )
    if bt.empty:
        raise ValueError("歷史資料不足，無法回測（請縮短持有天數）")
    margin = float(bt["margin_estimate"].max())
    metrics = backtest_metrics(bt, margin, initial_capital=req["initial_capital"], holding_days=int(req["holding_days"]))
    bt = bt.reset_index()
    bt["cumulative_pnl"] = bt["strategy_profit"].cumsum()
    bt["equity"] = req["initial_capital"] + bt["cumulative_pnl"]
    net_premium = sum((1 if l["side"] == "long" else -1) * float(l["premium"]) * int(l.get("quantity", 1)) for l in legs)
    return clean({
        "ticker": ctx["ticker"], "expiration": ctx["expiration"], "spot": ctx["spot"], "T": ctx["T"],
        "sigma": sigma, "sigma_source": sigma_source,
        "legs": [{k: l.get(k) for k in ("option_kind", "side", "strike", "premium", "bid", "ask", "quantity")} for l in legs],
        "net_premium": net_premium,
        "greeks": _leg_greeks(legs, ctx, sigma),
        "payoff": {"spot": grid["stock_price"].to_numpy(), "profit": grid["strategy_profit"].to_numpy()},
        "metrics": metrics,
        "backtest": frame_to_records(bt, [
            "exit_date", "entry_date", "entry_spot", "exit_spot", "entry_sigma", "exit_sigma",
            "strategy_profit", "cumulative_pnl", "equity", "transaction_cost",
        ]),
    })


# ---------------------------------------------------------------- risk
def _price_shocks(history, holding_days):
    close = history["Close"].dropna().astype(float)
    returns = close.pct_change(int(holding_days)).dropna()
    if len(returns) < 20:
        return [-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20]
    sizes = sorted({round(float(v), 4) for v in returns.abs().quantile([0.25, 0.5, 0.75, 0.9, 0.95]).dropna() if v > 0})
    return sorted({0.0} | {-v for v in sizes} | set(sizes))


def risk_report(md, req):
    ctx = md.context(req["ticker"], req.get("expiration"), req["r"], req["q"])
    sigma, sigma_source = _contract_vol(ctx, req["kind"], req["strike"])
    legs_in = req.get("legs") or [{"option_kind": req["kind"], "side": "long", "strike": req["strike"], "quantity": 1}]
    legs = [
        OptionLeg(option_kind=l["option_kind"], strike=float(l["strike"]),
                  quantity=(1 if l["side"] == "long" else -1) * abs(int(l.get("quantity", 1))),
                  multiplier=int(req.get("multiplier", 100)))
        for l in legs_in
    ]
    matrix = build_risk_matrix(legs, ctx["spot"], ctx["r"], ctx["q"], sigma, ctx["T"],
                               price_shocks=_price_shocks(ctx["history"], req.get("holding_days", 20)))

    returns = ctx["history"]["Close"].pct_change().dropna()
    value = ctx["spot"]
    var = {"historical": historical_var_es_summary(returns, 0.95, value)}
    for name, fn in (("ewma", lambda: ewma_var_es_summary(returns, confidence_level=0.95, portfolio_value=value)),
                     ("iv", lambda: iv_smoothed_var_es_summary(returns, annualized_volatility=sigma,
                                                               confidence_level=0.95, portfolio_value=value))):
        try:
            var[name] = fn()
        except ValueError:
            var[name] = None

    forward = ctx["forward"] or ctx["spot"]
    nodes = pd.concat([
        ctx["puts"][ctx["puts"]["strike"] <= forward], ctx["calls"][ctx["calls"]["strike"] > forward]
    ])
    nodes = nodes[np.isfinite(nodes["iv"]) & (nodes["iv"] > 0) & (nodes["iv"] < 3)]
    nodes = nodes[(nodes["strike"] > 0.6 * ctx["spot"]) & (nodes["strike"] < 1.4 * ctx["spot"])]
    curve = None
    if len(nodes) >= 4:
        curves = pd.DataFrame({"expiry": ctx["expiration"], "strike": nodes["strike"].astype(float),
                               "implied_volatility": nodes["iv"].astype(float)}).drop_duplicates("strike")
        diag, summary = vol_curve_diagnostics(curves, expiry=ctx["expiration"], forward=forward)
        curve = {"summary": summary, "nodes": frame_to_records(diag, [
            "strike", "moneyness", "curve_zone", "iv_pct", "slope_per_strike", "curvature", "abs_curvature"])}

    return clean({
        "ticker": ctx["ticker"], "expiration": ctx["expiration"], "spot": ctx["spot"],
        "sigma": sigma, "sigma_source": sigma_source, "legs": legs_in,
        "matrix": frame_to_records(matrix, list(matrix.columns)),
        "var": var, "curve": curve,
    })
