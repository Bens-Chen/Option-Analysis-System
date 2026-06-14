from datetime import date
import importlib.util
import math
from pathlib import Path
import sys
from importlib.machinery import SourceFileLoader

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
IMPLIED_VOL_ROOT = PROJECT_ROOT / "Implied Volatility"
if str(IMPLIED_VOL_ROOT) not in sys.path:
    sys.path.insert(0, str(IMPLIED_VOL_ROOT))

from Market_Data.yfinance_data import (
    add_mid_prices,
    download_price_history,
    estimate_annualized_volatility,
    fetch_option_chain,
    latest_close,
    matched_option_chain_prices,
)
from Option_System.analytics import (
    black_scholes_greeks,
    crr_greeks_by_bump,
    crr_option_price,
    fit_svi_smile,
    implied_volatility_from_price,
    option_price_from_bs,
)
from Option_System.strategy_engine import (
    backtest_metrics,
    build_chain_strategy_legs,
    estimate_strategy_margin,
    historical_scenario_backtest,
    moving_average_trend,
    payoff_grid,
    rank_strategy_candidates,
    rank_strategies_by_backtest,
    rolling_strategy_backtest,
    strategy_profit,
)
from iv_smile import IV_smile_arrays


def _load_vix_svix_module():
    module_path = IMPLIED_VOL_ROOT / "VIX,SVIX"
    loader = SourceFileLoader("vix_svix_module", str(module_path))
    spec = importlib.util.spec_from_loader("vix_svix_module", loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIX_SVIX_MODULE = _load_vix_svix_module()
CRR_STEPS = 10000


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
    history_period = "5y"
    st.caption("Backtest period: latest 5 years")
    holding_days = st.number_input("Scenario holding days", value=20, min_value=1, max_value=252)
    greek_model = st.selectbox("Greek model", ["Black-Scholes European", "CRR American"])
    st.caption(f"CRR steps fixed at n = {CRR_STEPS}")
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
calls_with_mid = add_mid_prices(chain["calls"])
puts_with_mid = add_mid_prices(chain["puts"])
matched_chain = matched_option_chain_prices(chain["calls"], chain["puts"])

left, right = st.columns([2, 1])

with left:
    st.subheader(f"{active_ticker} Option Chain")
    option_kind = st.radio("Option type", ["call", "put"], horizontal=True)
    chain_table = calls_with_mid if option_kind == "call" else puts_with_mid
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
        "midPrice",
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
yfinance_iv = float(selected.get("impliedVolatility", 0) or 0)
pricing_model = "CRR" if greek_model == "CRR American" else "BS"
option_style = "American" if greek_model == "CRR American" else "European"

try:
    model_iv = implied_volatility_from_price(
        market_price,
        spot,
        float(selected["strike"]),
        risk_free_rate,
        dividend_yield,
        T,
        option_kind,
        pricing_model=pricing_model,
        option_style=option_style,
        steps=CRR_STEPS,
    )
except ValueError as exc:
    st.warning(f"Could not solve model IV from market price. Historical volatility is used instead. Detail: {exc}")
    model_iv = historical_vol

if greek_model == "CRR American":
    model_price = crr_option_price(
        spot,
        float(selected["strike"]),
        risk_free_rate,
        dividend_yield,
        historical_vol,
        T,
        option_kind,
        option_style="American",
        steps=CRR_STEPS,
    )
else:
    model_price = option_price_from_bs(
        spot,
        float(selected["strike"]),
        risk_free_rate,
        dividend_yield,
        historical_vol,
        T,
        option_kind,
    )

if greek_model == "CRR American":
    greeks = crr_greeks_by_bump(
        spot,
        float(selected["strike"]),
        risk_free_rate,
        dividend_yield,
        model_iv,
        T,
        option_kind,
        option_style="American",
        steps=CRR_STEPS,
    )
else:
    greeks = black_scholes_greeks(
        spot,
        float(selected["strike"]),
        risk_free_rate,
        dividend_yield,
        model_iv,
        T,
        option_kind,
    )

st.subheader("Selected Contract Analytics")
price_cols = st.columns(4)
price_cols[0].metric("yfinance price", f"{market_price:.4f}")
price_cols[1].metric("model price", f"{model_price:.4f}")
price_cols[2].metric("model IV", f"{model_iv:.2%}")
price_cols[3].metric("yfinance IV", f"{yfinance_iv:.2%}" if yfinance_iv > 0 else "N/A")

metric_cols = st.columns(5)
metric_cols[0].metric("Delta", f"{greeks['delta']:.4f}")
metric_cols[1].metric("Gamma", f"{greeks['gamma']:.4f}")
metric_cols[2].metric("Theta/day", f"{greeks['theta_per_day']:.4f}")
metric_cols[3].metric("Vega/1%", f"{greeks['vega']:.4f}")
metric_cols[4].metric("Rho/1%", f"{greeks['rho']:.4f}")
if "model_price" in greeks:
    st.caption(f"CRR American model price using model IV: {greeks['model_price']:.4f}")

st.subheader("IV Smile, SVI Fit, and VIX-style Indicators")
try:
    indicator_result = VIX_SVIX_MODULE.VIX_SVIX(
        St=spot,
        r=risk_free_rate,
        q=dividend_yield,
        sigma=historical_vol,
        T=T,
        K_list=matched_chain["strike"].tolist(),
        call_price_list=matched_chain["call_mid"].tolist(),
        put_price_list=matched_chain["put_mid"].tolist(),
    )
    selected_iv_for_comparison = model_iv
    comparison_cols = st.columns(4)
    comparison_cols[0].metric("Selected model IV", f"{selected_iv_for_comparison:.2%}")
    comparison_cols[1].metric("VIX-style", f"{indicator_result['VIX']['vix']:.2f}")
    comparison_cols[2].metric("SVIX", f"{indicator_result['SVIX']['svix']:.2f}")
    comparison_cols[3].metric("VIX - SVIX", f"{indicator_result['VIX']['vix'] - indicator_result['SVIX']['svix']:.2f}")
except Exception as exc:
    indicator_result = None
    st.warning(f"Could not calculate VIX/SVIX from this option chain: {exc}")

try:
    smile_prices = chain_table["midPrice"].astype(float).tolist()
    smile_strikes = chain_table["strike"].astype(float).tolist()
    smile_x, smile_iv = IV_smile_arrays(
        S=spot,
        K_list=smile_strikes,
        r=risk_free_rate,
        q=dividend_yield,
        T=T,
        market_price_list=smile_prices,
        option_kind=option_kind,
        skip_errors=True,
    )
    forward = spot * math.exp((risk_free_rate - dividend_yield) * T)
    svi = fit_svi_smile(smile_x, smile_iv, forward, T)
    fig, ax = plt.subplots()
    ax.scatter(smile_x, smile_iv * 100, label="Market BS IV", s=18)
    ax.plot(svi["smooth_strikes"], svi["smooth_iv"] * 100, label="SVI fit", linewidth=2)
    ax.axvline(spot, color="gray", linestyle="--", linewidth=1)
    ax.set_xlabel("Strike")
    ax.set_ylabel("Implied volatility (%)")
    ax.set_title(f"{active_ticker} {option_kind.upper()} IV Smile")
    ax.legend()
    st.pyplot(fig)
    st.caption(f"SVI params: {svi['params']}")
except Exception as exc:
    st.warning(f"Could not build SVI IV smile for this option chain: {exc}")

trend = moving_average_trend(history)

st.subheader("Strategy Selection")
st.caption("Strategy score is based on rolling backtest metrics. It is not financial advice.")

strategy = st.selectbox(
    "Strategy",
    [
        "Single Option",
        "Long Straddle",
        "Short Straddle",
        "Long Strangle",
        "Short Strangle",
        "Long Call Butterfly",
        "Short Call Butterfly",
        "Custom",
    ],
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
    if "Butterfly" in strategy:
        other_strike = st.number_input("Butterfly wing width", value=max(float(selected["strike"]) * 0.05, 1.0))
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
backtest = rolling_strategy_backtest(history, spot, legs, holding_days=int(holding_days))
margin = estimate_strategy_margin(legs, spot)
metrics = backtest_metrics(backtest, margin)

strategy_candidates = [
    "Single Option",
    "Long Straddle",
    "Short Straddle",
    "Long Strangle",
    "Short Strangle",
    "Long Call Butterfly",
    "Short Call Butterfly",
]
strategy_results = {}
ranking_other_strike = locals().get("other_strike", None)
for candidate in strategy_candidates:
    try:
        candidate_legs = build_chain_strategy_legs(
            candidate,
            selected,
            calls_with_mid,
            puts_with_mid,
            other_strike=ranking_other_strike if "Butterfly" in candidate or "Strangle" in candidate else None,
        )
        candidate_backtest = rolling_strategy_backtest(
            history,
            spot,
            candidate_legs,
            holding_days=int(holding_days),
        )
        candidate_margin = estimate_strategy_margin(candidate_legs, spot)
        strategy_results[candidate] = {
            "metrics": backtest_metrics(candidate_backtest, candidate_margin),
            "legs": candidate_legs,
        }
    except Exception:
        continue

if strategy_results:
    ranking = rank_strategies_by_backtest(strategy_results)
    st.dataframe(ranking, use_container_width=True)

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

summary_cols = st.columns(5)
summary_cols[0].metric("Avg PnL", f"{metrics['avg_pnl']:.2f}")
summary_cols[1].metric("Win rate", f"{metrics['win_rate']:.2%}")
summary_cols[2].metric("Sharpe ratio", f"{metrics['sharpe_ratio']:.2f}")
summary_cols[3].metric("MDD", f"{metrics['mdd']:.2f}")
summary_cols[4].metric("Margin est.", f"{metrics['margin_estimate']:.2f}")

more_cols = st.columns(4)
more_cols[0].metric("Total PnL", f"{metrics['total_pnl']:.2f}")
more_cols[1].metric("Return on margin", f"{metrics['return_on_margin']:.2%}")
more_cols[2].metric("Worst scenario", f"{metrics['worst_scenario']:.2f}")
more_cols[3].metric("Best scenario", f"{metrics['best_scenario']:.2f}")

st.dataframe(backtest.tail(30), use_container_width=True)
