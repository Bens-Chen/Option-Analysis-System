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


def estimate_annualized_volatility(price_history, column="Close", trading_days=252):
    close = price_history[column].dropna().astype(float)
    if len(close) < 3:
        raise ValueError("At least three close prices are required to estimate volatility.")

    log_returns = np.log(close / close.shift(1)).dropna()
    volatility = float(log_returns.std(ddof=1) * math.sqrt(trading_days))
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
    bid = float(row.get("bid", 0) or 0)
    ask = float(row.get("ask", 0) or 0)
    last = float(row.get("lastPrice", 0) or 0)
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    return last


def add_mid_prices(option_table):
    table = option_table.copy()
    table["midPrice"] = table.apply(option_mid_price, axis=1)
    return table


def matched_option_chain_prices(calls, puts):
    calls = add_mid_prices(calls)
    puts = add_mid_prices(puts)
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
