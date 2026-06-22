import math

import numpy as np
import pandas as pd


def _import_yfinance():
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError(
            "yfinance is required for live market data. Install it with "
            "`pip install -r requirements.txt`."
        ) from exc
    return yf


def _flatten_single_ticker_columns(data):
    if isinstance(data.columns, pd.MultiIndex):
        return data.droplevel(1, axis=1)
    return data


def download_price_history(
    ticker,
    period="1y",
    interval="1d",
    start=None,
    end=None,
    auto_adjust=True,
):
    yf = _import_yfinance()
    data = yf.download(
        tickers=ticker,
        period=period,
        interval=interval,
        start=start,
        end=end,
        auto_adjust=auto_adjust,
        progress=False,
        multi_level_index=False,
    )
    data = _flatten_single_ticker_columns(data).dropna(how="all")
    if data.empty:
        raise ValueError(f"No price history returned for ticker {ticker}.")
    return data


def latest_close(price_history, column="Close"):
    close = price_history[column].dropna()
    if close.empty:
        raise ValueError(f"No valid {column} price found.")
    return float(close.iloc[-1])


def _newey_west_lag_count(sample_size):
    if sample_size < 2:
        raise ValueError("At least two returns are required to estimate volatility.")
    return max(1, int(math.floor(4 * (sample_size / 100) ** (2 / 9))))


def _newey_west_long_run_variance(values, lags):
    returns = np.asarray(values, dtype=float)
    returns = returns[np.isfinite(returns)]
    if returns.size < 2:
        raise ValueError("At least two finite returns are required to estimate volatility.")

    centered = returns - returns.mean()
    lags = min(int(lags), returns.size - 1)
    if lags < 0:
        raise ValueError("lags must be non-negative.")

    variance = float(np.mean(centered * centered))
    for lag in range(1, lags + 1):
        autocovariance = float(np.mean(centered[lag:] * centered[:-lag]))
        bartlett_weight = 1 - lag / (lags + 1)
        variance += 2 * bartlett_weight * autocovariance

    return variance


def estimate_annualized_volatility(price_history, column="Close", trading_days=252, lags=None):
    close = price_history[column].dropna().astype(float)
    if len(close) < 3:
        raise ValueError("At least three close prices are required to estimate volatility.")

    log_returns = np.log(close / close.shift(1)).dropna()
    selected_lags = _newey_west_lag_count(len(log_returns)) if lags is None else int(lags)
    long_run_variance = _newey_west_long_run_variance(log_returns.to_numpy(), selected_lags)
    if not math.isfinite(long_run_variance) or long_run_variance <= 0:
        raise ValueError("Estimated Newey-West long-run variance must be positive.")
    volatility = float(math.sqrt(long_run_variance * trading_days))
    if not math.isfinite(volatility) or volatility <= 0:
        raise ValueError("Estimated volatility must be positive.")
    return volatility


def fetch_option_chain(ticker, expiration=None):
    yf = _import_yfinance()
    instrument = yf.Ticker(ticker)
    expirations = list(instrument.options)
    if not expirations:
        raise ValueError(f"No option expirations returned for ticker {ticker}.")

    selected_expiration = expiration or expirations[0]
    if selected_expiration not in expirations:
        raise ValueError(
            f"Expiration {selected_expiration} is not available. "
            f"Available expirations: {', '.join(expirations)}"
        )

    chain = instrument.option_chain(selected_expiration)
    return {
        "ticker": ticker.upper(),
        "expiration": selected_expiration,
        "expirations": expirations,
        "calls": chain.calls.copy(),
        "puts": chain.puts.copy(),
        "underlying": getattr(chain, "underlying", None),
    }


def option_mid_price(row):
    bid = _clean_option_price(row.get("bid", 0))
    ask = _clean_option_price(row.get("ask", 0))
    last = _clean_option_price(row.get("lastPrice", 0))
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    return last


def _clean_option_price(value):
    price = pd.to_numeric(value, errors="coerce")
    if pd.isna(price) or not math.isfinite(float(price)) or float(price) <= 0:
        return 0.0
    return float(price)


def add_mid_prices(option_table):
    table = option_table.copy()
    table["midPrice"] = table.apply(option_mid_price, axis=1)
    return table


def filter_option_chain_by_quality(option_table,max_spread_pct=0.50,min_open_interest=0,min_volume=0,require_bid_ask=False):
    table = add_mid_prices(option_table)
    if table.empty:
        return table

    for column in ["strike", "bid", "ask", "lastPrice", "volume", "openInterest"]:
        if column not in table:
            table[column] = 0
        table[column] = pd.to_numeric(table[column], errors="coerce").fillna(0.0)

    table["has_bid_ask"] = (table["bid"] > 0) & (table["ask"] > 0) & (table["ask"] >= table["bid"])
    table["bid_ask_spread"] = np.where(
        table["has_bid_ask"],
        table["ask"] - table["bid"],
        np.nan,
    )
    table["spread_pct_mid"] = np.where(
        table["has_bid_ask"] & (table["midPrice"] > 0),
        table["bid_ask_spread"] / table["midPrice"],
        np.nan,
    )

    base_filter = (table["strike"] > 0) & (table["midPrice"] > 0)
    liquidity_filter = (table["openInterest"] >= min_open_interest) & (table["volume"] >= min_volume)
    if require_bid_ask:
        quote_filter = table["has_bid_ask"] & (table["spread_pct_mid"] <= max_spread_pct)
    else:
        quote_filter = (~table["has_bid_ask"]) | (table["spread_pct_mid"] <= max_spread_pct)

    filtered = table[base_filter & liquidity_filter & quote_filter].copy()
    return filtered.reset_index(drop=True)


def summarize_option_chain_quality(raw_table, filtered_table):
    raw_count = len(raw_table)
    filtered_count = len(filtered_table)
    removed_count = raw_count - filtered_count
    kept_pct = filtered_count / raw_count if raw_count else 0.0
    return {
        "raw_count": int(raw_count),
        "filtered_count": int(filtered_count),
        "removed_count": int(removed_count),
        "kept_pct": float(kept_pct),
    }


def matched_option_chain_prices(calls, puts):
    calls = add_mid_prices(calls)
    puts = add_mid_prices(puts)
    calls["strike"] = pd.to_numeric(calls["strike"], errors="coerce")
    puts["strike"] = pd.to_numeric(puts["strike"], errors="coerce")
    call_cols = calls[["strike", "midPrice", "impliedVolatility"]].rename(
        columns={"midPrice": "call_mid", "impliedVolatility": "call_yfinance_iv"}
    )
    put_cols = puts[["strike", "midPrice", "impliedVolatility"]].rename(
        columns={"midPrice": "put_mid", "impliedVolatility": "put_yfinance_iv"}
    )
    merged = pd.merge(call_cols, put_cols, on="strike", how="inner")
    merged = merged.dropna(subset=["strike", "call_mid", "put_mid"])
    merged = merged[(merged["call_mid"] > 0) & (merged["put_mid"] > 0)]
    return merged.sort_values("strike").reset_index(drop=True)

# put call parity
def estimate_forward_price(matched_prices, risk_free_rate, time_to_maturity):
    if time_to_maturity <= 0:
        raise ValueError("time_to_maturity must be positive.")

    required_columns = {"strike", "call_mid", "put_mid"}
    missing_columns = required_columns.difference(matched_prices.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"matched_prices is missing required columns: {missing}")

    table = matched_prices.copy()
    for column in ["strike", "call_mid", "put_mid"]:
        table[column] = pd.to_numeric(table[column], errors="coerce")
    table = table.dropna(subset=["strike", "call_mid", "put_mid"])
    table = table[(table["strike"] > 0) & (table["call_mid"] > 0) & (table["put_mid"] > 0)]
    if table.empty:
        raise ValueError("No matched call/put prices are available to estimate forward price.")

    table["call_put_diff_abs"] = (table["call_mid"] - table["put_mid"]).abs()
    reference = table.sort_values(["call_put_diff_abs", "strike"]).iloc[0]
    discount_growth = math.exp(float(risk_free_rate) * float(time_to_maturity))
    forward = float(reference["strike"] + discount_growth * (reference["call_mid"] - reference["put_mid"]))

    if not math.isfinite(forward) or forward <= 0:
        raise ValueError("Estimated forward price must be positive.")

    return {
        "F": forward,
        "reference_strike": float(reference["strike"]),
        "call_mid": float(reference["call_mid"]),
        "put_mid": float(reference["put_mid"]),
        "call_put_diff": float(reference["call_mid"] - reference["put_mid"]),
        "risk_free_growth": discount_growth,
    }


def build_vix_svix_inputs(calls, puts, risk_free_rate, time_to_maturity):
    matched = matched_option_chain_prices(calls, puts)
    forward = estimate_forward_price(matched, risk_free_rate, time_to_maturity)
    return {
        "K_list": matched["strike"].astype(float).tolist(),
        "call_price_list": matched["call_mid"].astype(float).tolist(),
        "put_price_list": matched["put_mid"].astype(float).tolist(),
        "F": forward["F"],
        "forward": forward,
        "matched_prices": matched,
    }


def build_option_inputs(
    ticker,
    strike,
    risk_free_rate,
    time_to_maturity,
    dividend_yield=0.0,
    period="1y",
    interval="1d",
    start=None,
    end=None,
    auto_adjust=True,
):
    history = download_price_history(
        ticker=ticker,
        period=period,
        interval=interval,
        start=start,
        end=end,
        auto_adjust=auto_adjust,
    )
    return {
        "S": latest_close(history),
        "K": float(strike),
        "r": float(risk_free_rate),
        "q": float(dividend_yield),
        "sigma": estimate_annualized_volatility(history),
        "T": float(time_to_maturity),
        "history": history,
    }
