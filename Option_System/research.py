"""Research-oriented option-chain analytics and strategy diagnostic helpers."""

from datetime import date

import numpy as np
import pandas as pd

from Market_Data.yfinance_data import filter_option_chain_by_quality, option_mid_price
from Option_System.analytics import option_price_from_bs
from Option_System.strategy_engine import (
    backtest_metrics,
    build_chain_strategy_legs,
    estimate_strategy_margin,
    rolling_strategy_backtest,
)


def days_to_years(expiration, today=None):
    today = today or date.today()
    expiry = pd.to_datetime(expiration).date()
    days = max((expiry - today).days, 1)
    return days / 365


def build_research_chain_table(
    option_chains,
    spot,
    risk_free_rate,
    dividend_yield,
    model_volatility,
    max_spread_pct=0.50,
    min_open_interest=0,
    min_volume=0,
    require_bid_ask=False,
):
    rows = []
    for expiration, chain in option_chains.items():
        T = days_to_years(expiration)
        for option_kind, table_name in [("call", "calls"), ("put", "puts")]:
            filtered = filter_option_chain_by_quality(
                chain[table_name],
                max_spread_pct=max_spread_pct,
                min_open_interest=min_open_interest,
                min_volume=min_volume,
                require_bid_ask=require_bid_ask,
            )
            for _, row in filtered.iterrows():
                strike = float(row["strike"])
                market_price = option_mid_price(row)
                yfinance_iv = float(row.get("impliedVolatility", 0) or 0)
                if market_price <= 0 or strike <= 0:
                    continue
                try:
                    model_price = option_price_from_bs(
                        spot,
                        strike,
                        risk_free_rate,
                        dividend_yield,
                        model_volatility,
                        T,
                        option_kind,
                    )
                except Exception:
                    continue
                mispricing = market_price - model_price
                rows.append(
                    {
                        "expiration": expiration,
                        "days_to_expiration": int(round(T * 365)),
                        "option_kind": option_kind,
                        "contractSymbol": row.get("contractSymbol", ""),
                        "strike": strike,
                        "moneyness": strike / spot,
                        "market_price": market_price,
                        "model_price": model_price,
                        "mispricing": mispricing,
                        "abs_mispricing": abs(mispricing),
                        "pct_mispricing": mispricing / model_price if model_price > 0 else np.nan,
                        "bid": float(row.get("bid", 0) or 0),
                        "ask": float(row.get("ask", 0) or 0),
                        "spread": float(row.get("bid_ask_spread", np.nan)),
                        "spread_pct_mid": float(row.get("spread_pct_mid", np.nan)),
                        "volume": float(row.get("volume", 0) or 0),
                        "openInterest": float(row.get("openInterest", 0) or 0),
                        "impliedVolatility": yfinance_iv,
                    }
                )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["expiration", "option_kind", "strike"]).reset_index(drop=True)


def volatility_surface_table(research_table, option_kind="call", moneyness_step=0.05):
    if research_table.empty:
        return pd.DataFrame()
    table = research_table.copy()
    table = table[(table["option_kind"] == option_kind) & (table["impliedVolatility"] > 0)]
    if table.empty:
        return pd.DataFrame()
    table["moneyness_bucket"] = (table["moneyness"] / moneyness_step).round() * moneyness_step
    pivot = table.pivot_table(
        index="days_to_expiration",
        columns="moneyness_bucket",
        values="impliedVolatility",
        aggfunc="mean",
    )
    return pivot.sort_index()


def surface_summary(research_table):
    if research_table.empty:
        return {
            "atm_iv": np.nan,
            "skew_90_110": np.nan,
            "term_structure_slope": np.nan,
            "iv_rank_proxy": np.nan,
        }

    valid = research_table[research_table["impliedVolatility"] > 0].copy()
    if valid.empty:
        return {
            "atm_iv": np.nan,
            "skew_90_110": np.nan,
            "term_structure_slope": np.nan,
            "iv_rank_proxy": np.nan,
        }

    valid["atm_distance"] = (valid["moneyness"] - 1.0).abs()
    atm_by_exp = valid.sort_values("atm_distance").groupby("expiration").head(1)
    near_atm = atm_by_exp.sort_values("days_to_expiration").iloc[0]
    front = atm_by_exp.sort_values("days_to_expiration").iloc[0]["impliedVolatility"]
    back = atm_by_exp.sort_values("days_to_expiration").iloc[-1]["impliedVolatility"]

    low = _nearest_iv(valid, 0.90)
    high = _nearest_iv(valid, 1.10)
    iv_min = float(valid["impliedVolatility"].min())
    iv_max = float(valid["impliedVolatility"].max())
    atm_iv = float(near_atm["impliedVolatility"])
    iv_rank_proxy = (atm_iv - iv_min) / (iv_max - iv_min) if iv_max > iv_min else np.nan

    return {
        "atm_iv": atm_iv,
        "skew_90_110": low - high if np.isfinite(low) and np.isfinite(high) else np.nan,
        "term_structure_slope": float(back - front),
        "iv_rank_proxy": float(iv_rank_proxy) if np.isfinite(iv_rank_proxy) else np.nan,
    }


def _nearest_iv(table, target_moneyness):
    candidates = table.copy()
    candidates["distance"] = (candidates["moneyness"] - target_moneyness).abs()
    if candidates.empty:
        return np.nan
    return float(candidates.sort_values("distance").iloc[0]["impliedVolatility"])


def mispricing_scanner(research_table, min_abs_mispricing=0.05, max_spread_pct=0.50):
    if research_table.empty:
        return pd.DataFrame()
    table = research_table.copy()
    spread_ok = table["spread_pct_mid"].isna() | (table["spread_pct_mid"] <= max_spread_pct)
    table = table[spread_ok & (table["abs_mispricing"] >= min_abs_mispricing)].copy()
    if table.empty:
        return table
    table["pricing_signal"] = np.where(table["mispricing"] > 0, "rich_vs_model", "cheap_vs_model")
    return table.sort_values("abs_mispricing", ascending=False).reset_index(drop=True)


def strategy_robustness_grid(
    research_table,
    price_history,
    spot,
    calls_by_expiration,
    puts_by_expiration,
    strategy_name,
    moneyness_values,
    holding_days=20,
):
    rows = []
    for expiration in sorted(calls_by_expiration):
        calls = calls_by_expiration[expiration]
        puts = puts_by_expiration.get(expiration, pd.DataFrame())
        if calls.empty or puts.empty:
            continue
        dte_rows = research_table[research_table["expiration"] == expiration]
        if dte_rows.empty:
            continue
        dte = int(dte_rows["days_to_expiration"].iloc[0])
        for moneyness in moneyness_values:
            target_strike = spot * float(moneyness)
            selected = _nearest_chain_row(calls, target_strike, "call")
            try:
                legs = build_chain_strategy_legs(strategy_name, selected, calls, puts, other_strike=target_strike * 0.05)
                backtest = rolling_strategy_backtest(price_history, spot, legs, holding_days=holding_days)
                margin = estimate_strategy_margin(legs, spot)
                metrics = backtest_metrics(backtest, margin)
            except Exception:
                continue
            rows.append(
                {
                    "expiration": expiration,
                    "days_to_expiration": dte,
                    "moneyness": float(moneyness),
                    "sharpe_ratio": metrics["sharpe_ratio"],
                    "mdd": metrics["mdd"],
                    "win_rate": metrics["win_rate"],
                    "return_on_margin": metrics["return_on_margin"],
                }
            )
    return pd.DataFrame(rows)


def _nearest_chain_row(chain, target_strike, option_kind):
    table = chain.copy()
    table["option_kind"] = option_kind
    table["distance"] = (table["strike"].astype(float) - float(target_strike)).abs()
    return table.sort_values("distance").iloc[0].to_dict()


def tear_sheet_metrics(backtest, margin, confidence=0.95):
    profit = backtest["strategy_profit"].astype(float)
    returns = profit / margin if margin > 0 else profit
    cumulative = profit.cumsum()
    drawdown = cumulative - cumulative.cummax()
    var_level = 1 - confidence
    var = float(returns.quantile(var_level))
    cvar = float(returns[returns <= var].mean()) if not returns[returns <= var].empty else np.nan
    monthly_pnl = profit.groupby(pd.to_datetime(profit.index).to_period("M")).sum()
    return {
        "total_pnl": float(profit.sum()),
        "avg_pnl": float(profit.mean()),
        "volatility": float(returns.std(ddof=1)),
        "max_drawdown": float(drawdown.min()),
        "win_rate": float((profit > 0).mean()),
        "var": var,
        "cvar": cvar,
        "best_trade": float(profit.max()),
        "worst_trade": float(profit.min()),
        "monthly_pnl": monthly_pnl,
    }


def event_straddle_analysis(price_history, spot, calls, puts, event_date=None):
    call = _nearest_chain_row(calls, spot, "call")
    put = _nearest_chain_row(puts, spot, "put")
    call_price = option_mid_price(call)
    put_price = option_mid_price(put)
    implied_move = (call_price + put_price) / spot if spot > 0 else np.nan
    result = {
        "atm_strike": float(call["strike"]),
        "call_mid": call_price,
        "put_mid": put_price,
        "implied_move": implied_move,
        "actual_next_move": np.nan,
    }
    if event_date is not None:
        close = price_history["Close"].dropna().astype(float)
        close.index = pd.to_datetime(close.index)
        event_ts = pd.to_datetime(event_date)
        before = close[close.index <= event_ts]
        after = close[close.index > event_ts]
        if not before.empty and not after.empty:
            result["actual_next_move"] = float(after.iloc[0] / before.iloc[-1] - 1)
    return result


def paper_alerts(surface_stats, scanner_table, iv_rank_threshold=0.80, mispricing_threshold=0.15):
    alerts = []
    iv_rank = surface_stats.get("iv_rank_proxy", np.nan)
    skew = surface_stats.get("skew_90_110", np.nan)
    if np.isfinite(iv_rank) and iv_rank >= iv_rank_threshold:
        alerts.append({"alert": "high_iv_rank_proxy", "value": iv_rank, "detail": "ATM IV is high versus the current surface range."})
    if np.isfinite(skew) and abs(skew) >= 0.10:
        alerts.append({"alert": "steep_surface_skew", "value": skew, "detail": "90% and 110% moneyness IV differ by at least 10 vol points."})
    if not scanner_table.empty:
        large = scanner_table[scanner_table["pct_mispricing"].abs() >= mispricing_threshold]
        for _, row in large.head(5).iterrows():
            alerts.append(
                {
                    "alert": "large_model_mispricing",
                    "value": float(row["pct_mispricing"]),
                    "detail": f"{row['contractSymbol']} is {row['pricing_signal']}.",
                }
            )
    return pd.DataFrame(alerts)
