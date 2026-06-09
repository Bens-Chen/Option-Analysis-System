from datetime import date
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Market_Data.yfinance_data import (
    download_price_history,
    estimate_annualized_volatility,
    fetch_option_chain,
    latest_close,
)
from Option_System.analytics import black_scholes_greeks, implied_volatility_from_price
from Option_System.strategy_engine import (
    build_chain_strategy_legs,
    historical_scenario_backtest,
    moving_average_trend,
    payoff_grid,
    rank_strategy_candidates,
    strategy_profit,
)


def _mid_price(row):
    bid = float(row.get("bid", 0) or 0)
    ask = float(row.get("ask", 0) or 0)
    last = float(row.get("lastPrice", 0) or 0)
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    return last


def _days_to_years(expiration):
    expiry = pd.to_datetime(expiration).date()
    days = max((expiry - date.today()).days, 1)
    return days / 365


st.set_page_config(page_title="Option Analysis System", layout="wide")
st.title("Option Analysis System")

with st.sidebar:
    ticker = st.text_input("Ticker", value="AAPL").upper().strip()
    risk_free_rate = st.number_input("Risk-free rate", value=0.04, step=0.005, format="%.4f")
    dividend_yield = st.number_input("Dividend yield", value=0.00, step=0.005, format="%.4f")
    history_period = st.selectbox("History period", ["6mo", "1y", "2y", "5y"], index=1)
    holding_days = st.number_input("Scenario holding days", value=20, min_value=1, max_value=252)
    load_data = st.button("Load Market Data", type="primary")

if not ticker:
    st.stop()

if load_data:
    st.session_state["loaded_ticker"] = ticker

active_ticker = st.session_state.get("loaded_ticker", ticker)

try:
    history = download_price_history(active_ticker, period=history_period)
    spot = latest_close(history)
    historical_vol = estimate_annualized_volatility(history)
    chain_preview = fetch_option_chain(active_ticker)
except Exception as exc:
    st.error(str(exc))
    st.stop()

expirations = chain_preview["expirations"]
expiration = st.selectbox("Expiration", expirations)
chain = fetch_option_chain(active_ticker, expiration)

left, right = st.columns([2, 1])

with left:
    st.subheader(f"{active_ticker} Option Chain")
    option_kind = st.radio("Option type", ["call", "put"], horizontal=True)
    chain_table = chain["calls"] if option_kind == "call" else chain["puts"]
    chain_table = chain_table.copy()
    chain_table["option_kind"] = option_kind
    chain_table["distance_from_spot"] = (chain_table["strike"] - spot).abs()
    chain_table = chain_table.sort_values("distance_from_spot")
    display_cols = [
        "contractSymbol",
        "strike",
        "bid",
        "ask",
        "lastPrice",
        "impliedVolatility",
        "volume",
        "openInterest",
    ]
    st.dataframe(chain_table[display_cols].head(40), use_container_width=True)

with right:
    st.subheader("Market Inputs")
    st.metric("Spot", f"{spot:.2f}")
    st.metric("Historical volatility", f"{historical_vol:.2%}")
    st.line_chart(history["Close"])

contracts = chain_table["contractSymbol"].tolist()
selected_symbol = st.selectbox("Select contract", contracts)
selected = chain_table.loc[chain_table["contractSymbol"] == selected_symbol].iloc[0].to_dict()

T = _days_to_years(expiration)
market_price = _mid_price(selected)
selected_iv = float(selected.get("impliedVolatility", 0) or 0)
if selected_iv <= 0 and market_price > 0:
    selected_iv = implied_volatility_from_price(
        market_price,
        spot,
        float(selected["strike"]),
        risk_free_rate,
        dividend_yield,
        T,
        option_kind,
    )

greeks = black_scholes_greeks(
    spot,
    float(selected["strike"]),
    risk_free_rate,
    dividend_yield,
    selected_iv,
    T,
    option_kind,
)

st.subheader("Selected Contract Analytics")
metric_cols = st.columns(6)
metric_cols[0].metric("IV", f"{selected_iv:.2%}")
metric_cols[1].metric("Delta", f"{greeks['delta']:.4f}")
metric_cols[2].metric("Gamma", f"{greeks['gamma']:.4f}")
metric_cols[3].metric("Theta/day", f"{greeks['theta_per_day']:.4f}")
metric_cols[4].metric("Vega/1%", f"{greeks['vega']:.4f}")
metric_cols[5].metric("Rho/1%", f"{greeks['rho']:.4f}")

trend = moving_average_trend(history)
ranking = rank_strategy_candidates(spot, historical_vol, selected_iv, trend)

st.subheader("Strategy Selection")
st.caption("Educational scoring only. It is not financial advice.")
st.dataframe(ranking, use_container_width=True)

strategy = st.selectbox(
    "Strategy",
    ["Single Option", "Long Straddle", "Short Straddle", "Long Strangle", "Short Strangle", "Custom"],
)

if strategy == "Custom":
    st.write("Enter one row per option leg.")
    custom_text = st.text_area(
        "CSV columns: option_kind,side,strike,premium,quantity",
        value="call,long,100,5,1\nput,long,95,4,1",
    )
    custom_rows = [line.split(",") for line in custom_text.splitlines() if line.strip()]
    legs = [
        {
            "option_kind": row[0].strip(),
            "side": row[1].strip(),
            "strike": float(row[2]),
            "premium": float(row[3]),
            "quantity": int(row[4]),
        }
        for row in custom_rows
    ]
else:
    other_strike = st.number_input("Second strike for strangle", value=float(selected["strike"]) * 1.05)
    legs = build_chain_strategy_legs(
        strategy,
        selected,
        chain["calls"],
        chain["puts"],
        other_strike=other_strike,
    )

legs_df = pd.DataFrame(legs)
st.dataframe(legs_df, use_container_width=True)

grid = payoff_grid(spot, legs)
backtest = historical_scenario_backtest(history, spot, legs, holding_days=int(holding_days))

plot_left, plot_right = st.columns(2)
with plot_left:
    fig, ax = plt.subplots()
    ax.plot(grid["stock_price"], grid["strategy_profit"])
    ax.axhline(0, color="black", linewidth=1)
    ax.axvline(spot, color="gray", linestyle="--", linewidth=1)
    ax.set_xlabel("Stock price at expiration")
    ax.set_ylabel("Profit")
    ax.set_title("Strategy payoff")
    st.pyplot(fig)

with plot_right:
    fig, ax = plt.subplots()
    ax.hist(backtest["strategy_profit"], bins=30)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_xlabel("Scenario profit")
    ax.set_ylabel("Count")
    ax.set_title("Historical scenario backtest")
    st.pyplot(fig)

summary_cols = st.columns(4)
summary_cols[0].metric("Avg scenario PnL", f"{backtest['strategy_profit'].mean():.2f}")
summary_cols[1].metric("Win rate", f"{(backtest['strategy_profit'] > 0).mean():.2%}")
summary_cols[2].metric("Worst scenario", f"{backtest['strategy_profit'].min():.2f}")
summary_cols[3].metric("Best scenario", f"{backtest['strategy_profit'].max():.2f}")

st.dataframe(backtest.tail(30), use_container_width=True)
