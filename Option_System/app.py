"""Streamlit app for live option quotes, Greeks, backtests, and risk views."""

from datetime import date
import importlib.util
from pathlib import Path
import sys
from importlib.machinery import SourceFileLoader

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
IMPLIED_VOL_ROOT = PROJECT_ROOT / "Implied_Volatility"
if str(IMPLIED_VOL_ROOT) not in sys.path:
    sys.path.insert(0, str(IMPLIED_VOL_ROOT))

from Market_Data.yfinance_data import (
    add_mid_prices,
    download_price_history,
    estimate_forward_price,
    estimate_annualized_volatility,
    fetch_option_chain,
    filter_option_chain_by_quality,
    latest_close,
    matched_option_chain_prices,
    summarize_option_chain_quality,
)
from Option_System.analytics import (
    black_scholes_greeks,
    crr_greeks_by_bump,
    crr_option_price,
    implied_volatility_from_price,
    option_price_from_bs,
)
from Option_System.strategy_engine import (
    backtest_metrics,
    build_chain_strategy_legs,
    estimate_strategy_margin,
    payoff_grid,
    rolling_strategy_backtest,
)
from Option_System.research import (
    build_research_chain_table,
    event_straddle_analysis,
    mispricing_scanner,
    paper_alerts,
    strategy_robustness_grid,
    surface_summary,
    tear_sheet_metrics,
    volatility_surface_table,
)
from Risk_Management.risk_matrix import OptionLeg, build_risk_matrix, plot_risk_matrix
from Risk_Management.var_es import ewma_var_es_summary, historical_var_es_summary
from Risk_Management.vol_curve_monitor import plot_vol_curve_monitor
from iv_smile import IV_smile_arrays, fit_svi_smile


def _load_vix_svix_module():
    """Load the extensionless VIX/SVIX module kept in Implied_Volatility."""

    module_path = IMPLIED_VOL_ROOT / "vix_svix"
    loader = SourceFileLoader("vix_svix_module", str(module_path))
    spec = importlib.util.spec_from_loader("vix_svix_module", loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIX_SVIX_MODULE = _load_vix_svix_module()
CRR_STEPS = 10000


@st.cache_data(ttl=900)
def _cached_price_history(ticker, period):
    return download_price_history(ticker, period=period)


@st.cache_data(ttl=900)
def _cached_option_chain(ticker, expiration=None):
    return fetch_option_chain(ticker, expiration)


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


def _load_market_context(
    ticker,
    expiration,
    option_kind,
    max_spread_pct,
    min_open_interest,
    min_volume,
    require_bid_ask,
):
    """Fetch price history and the current option chain used by all app pages."""

    history = _cached_price_history(ticker, "5y")
    spot = latest_close(history)
    historical_vol = estimate_annualized_volatility(history)
    chain_preview = _cached_option_chain(ticker)
    expirations = chain_preview["expirations"]
    selected_expiration = expiration or expirations[0]
    chain = _cached_option_chain(ticker, selected_expiration)

    calls_with_mid = filter_option_chain_by_quality(
        chain["calls"],
        max_spread_pct=max_spread_pct,
        min_open_interest=min_open_interest,
        min_volume=min_volume,
        require_bid_ask=require_bid_ask,
    )
    puts_with_mid = filter_option_chain_by_quality(
        chain["puts"],
        max_spread_pct=max_spread_pct,
        min_open_interest=min_open_interest,
        min_volume=min_volume,
        require_bid_ask=require_bid_ask,
    )
    if calls_with_mid.empty or puts_with_mid.empty:
        st.warning("The quote-quality filter removed all calls or puts. Raw yfinance rows are used instead.")
        calls_with_mid = add_mid_prices(chain["calls"])
        puts_with_mid = add_mid_prices(chain["puts"])

    chain_table = calls_with_mid if option_kind == "call" else puts_with_mid
    chain_table = chain_table.copy()
    chain_table["option_kind"] = option_kind
    chain_table["distance_from_spot"] = (chain_table["strike"] - spot).abs()
    chain_table = chain_table.sort_values("distance_from_spot").reset_index(drop=True)

    return {
        "history": history,
        "spot": spot,
        "historical_vol": historical_vol,
        "expirations": expirations,
        "expiration": selected_expiration,
        "chain": chain,
        "calls_with_mid": calls_with_mid,
        "puts_with_mid": puts_with_mid,
        "matched_chain": matched_option_chain_prices(calls_with_mid, puts_with_mid),
        "chain_table": chain_table,
    }


def _selected_contract_analytics(context, selected_symbol, option_kind, option_style, risk_free_rate, dividend_yield):
    """Compute pricing, IV, and Greeks for the selected option contract."""

    chain_table = context["chain_table"]
    selected = chain_table.loc[chain_table["contractSymbol"] == selected_symbol].iloc[0].to_dict()
    spot = context["spot"]
    historical_vol = context["historical_vol"]
    T = _days_to_years(context["expiration"])
    market_price = _mid_price(selected)
    yfinance_iv = float(selected.get("impliedVolatility", 0) or 0)
    pricing_model = "CRR" if option_style == "American" else "BS"

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
        iv_note = ""
    except ValueError as exc:
        model_iv = historical_vol
        iv_note = f"Could not solve model IV from market price. Historical volatility is used instead. Detail: {exc}"

    if option_style == "American":
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
        model_price = option_price_from_bs(
            spot,
            float(selected["strike"]),
            risk_free_rate,
            dividend_yield,
            historical_vol,
            T,
            option_kind,
        )
        greeks = black_scholes_greeks(
            spot,
            float(selected["strike"]),
            risk_free_rate,
            dividend_yield,
            model_iv,
            T,
            option_kind,
        )

    return {
        "selected": selected,
        "T": T,
        "market_price": market_price,
        "yfinance_iv": yfinance_iv,
        "model_iv": model_iv,
        "model_price": model_price,
        "greeks": greeks,
        "iv_note": iv_note,
    }


def _render_contract_quote(context, analytics, active_ticker, option_style):
    """Render the selected contract quote and nearby yfinance contracts."""

    st.subheader("Selected Contract Quote")
    quote_cols = st.columns(4)
    quote_cols[0].metric("yfinance price", f"{analytics['market_price']:.4f}")
    quote_cols[1].metric(f"{option_style} model price", f"{analytics['model_price']:.4f}")
    quote_cols[2].metric("yfinance IV", f"{analytics['yfinance_iv']:.2%}" if analytics["yfinance_iv"] > 0 else "N/A")
    quote_cols[3].metric("model IV", f"{analytics['model_iv']:.2%}")
    if analytics["iv_note"]:
        st.warning(analytics["iv_note"])

    selected = analytics["selected"]
    meta_cols = st.columns(4)
    meta_cols[0].metric("Spot", f"{context['spot']:.2f}")
    meta_cols[1].metric("Strike", f"{float(selected['strike']):.2f}")
    meta_cols[2].metric("Expiration", context["expiration"])
    meta_cols[3].metric("Historical vol", f"{context['historical_vol']:.2%}")

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
    st.write(f"{active_ticker} nearby option contracts")
    st.dataframe(context["chain_table"][display_cols].head(25), use_container_width=True)


def _render_greek_letters(context, analytics):
    """Render single-contract Greeks plus IV smile and VIX/SVIX indicators."""

    st.subheader("Greek Letters")
    greeks = analytics["greeks"]
    metric_cols = st.columns(5)
    metric_cols[0].metric("Delta", f"{greeks['delta']:.4f}")
    metric_cols[1].metric("Gamma", f"{greeks['gamma']:.4f}")
    metric_cols[2].metric("Theta/day", f"{greeks['theta_per_day']:.4f}")
    metric_cols[3].metric("Vega", f"{greeks['vega']:.4f}")
    metric_cols[4].metric("Rho", f"{greeks['rho']:.4f}")
    if "model_price" in greeks:
        st.caption(f"CRR American model price using model IV: {greeks['model_price']:.4f}")

    st.subheader("IV Smile and VIX/SVIX")
    try:
        indicator_result = VIX_SVIX_MODULE.VIX_SVIX(
            St=context["spot"],
            r=risk_free_rate,
            T=analytics["T"],
            K_list=context["matched_chain"]["strike"].tolist(),
            call_price_list=context["matched_chain"]["call_mid"].tolist(),
            put_price_list=context["matched_chain"]["put_mid"].tolist(),
        )
        comparison_cols = st.columns(4)
        comparison_cols[0].metric("Selected model IV", f"{analytics['model_iv']:.2%}")
        comparison_cols[1].metric("VIX", f"{indicator_result['VIX']['vix']:.2f}")
        comparison_cols[2].metric("SVIX", f"{indicator_result['SVIX']['svix']:.2f}")
        comparison_cols[3].metric("VIX - SVIX", f"{indicator_result['VIX']['vix'] - indicator_result['SVIX']['svix']:.2f}")
    except Exception as exc:
        st.warning(f"Could not calculate VIX/SVIX from this option chain: {exc}")

    try:
        chain_table = context["chain_table"]
        smile_x, smile_iv = IV_smile_arrays(
            S=context["spot"],
            K_list=chain_table["strike"].astype(float).tolist(),
            r=risk_free_rate,
            q=dividend_yield,
            T=analytics["T"],
            market_price_list=chain_table["midPrice"].astype(float).tolist(),
            option_kind=option_kind,
            skip_errors=True,
        )
        forward = estimate_forward_price(context["matched_chain"], risk_free_rate, analytics["T"])["F"]
        svi = fit_svi_smile(smile_x, smile_iv, forward, analytics["T"])
        fig, ax = plt.subplots()
        ax.scatter(smile_x, smile_iv * 100, label="Market IV", s=18)
        ax.plot(svi["smooth_strikes"], svi["smooth_iv"] * 100, label="SVI fit", linewidth=2)
        ax.axvline(context["spot"], color="gray", linestyle="--", linewidth=1)
        ax.set_xlabel("Strike")
        ax.set_ylabel("Implied volatility (%)")
        ax.set_title("IV Smile")
        ax.legend()
        st.pyplot(fig)
    except Exception as exc:
        st.warning(f"Could not build SVI IV smile for this option chain: {exc}")


def _build_strategy_legs(strategy, selected, chain, other_strike, ratio_quantity=2):
    """Convert the selected strategy name into option legs for payoff/backtest."""

    if strategy == "Custom":
        custom_text = st.text_area(
            "CSV columns: option_kind,side,strike,premium,quantity",
            value="call,long,100,5,1\nput,long,95,4,1",
        )
        custom_rows = [line.split(",") for line in custom_text.splitlines() if line.strip()]
        return [
            {
                "option_kind": row[0].strip(),
                "side": row[1].strip(),
                "strike": float(row[2]),
                "premium": float(row[3]),
                "quantity": int(row[4]),
            }
            for row in custom_rows
        ]

    return build_chain_strategy_legs(
        strategy,
        selected,
        chain["calls"],
        chain["puts"],
        other_strike=other_strike,
        ratio_quantity=ratio_quantity,
    )


def _format_metric(value, fmt="{:.2f}", missing="N/A"):
    if pd.isna(value):
        return missing
    return fmt.format(value)


def _portfolio_greeks(legs, spot, risk_free_rate, dividend_yield, volatility, time_to_maturity, contract_multiplier):
    """Aggregate leg Greeks into one strategy-level Greek exposure."""

    totals = {"delta": 0.0, "gamma": 0.0, "theta_per_day": 0.0, "vega": 0.0, "rho": 0.0}
    for leg in legs:
        greeks = black_scholes_greeks(
            spot,
            float(leg["strike"]),
            risk_free_rate,
            dividend_yield,
            volatility,
            time_to_maturity,
            leg["option_kind"],
        )
        side = 1 if leg["side"] == "long" else -1
        scale = side * int(leg.get("quantity", 1)) * contract_multiplier
        for key in totals:
            totals[key] += float(greeks[key]) * scale
    return totals


def _render_portfolio_greeks(legs, context, analytics, contract_multiplier):
    """Show portfolio Greeks beside the chosen backtest strategy."""

    greeks = _portfolio_greeks(
        legs,
        context["spot"],
        risk_free_rate,
        dividend_yield,
        analytics["model_iv"],
        analytics["T"],
        contract_multiplier,
    )
    st.subheader("Strategy Greeks")
    greek_cols = st.columns(5)
    greek_cols[0].metric("Delta", f"{greeks['delta']:.2f}")
    greek_cols[1].metric("Gamma", f"{greeks['gamma']:.4f}")
    greek_cols[2].metric("Theta/day", f"{greeks['theta_per_day']:.2f}")
    greek_cols[3].metric("Vega", f"{greeks['vega']:.2f}")
    greek_cols[4].metric("Rho", f"{greeks['rho']:.2f}")
    st.caption(
        "Strategy Greeks are the sum of each leg's Greek after long/short sign, quantity, and contract multiplier. "
        "This uses BS Greeks with the selected contract's model IV as a portfolio approximation."
    )


def _backtest_diagnostics(metrics, backtest, holding_days, non_overlapping):
    """Create short warnings when backtest metrics may be misleading."""

    notes = []
    if metrics["win_rate"] >= 0.70:
        notes.append("Win rate is high. Check whether the strategy is selling tail risk or benefiting from scaled current premiums.")
    if metrics["win_rate"] <= 0.40:
        notes.append("Win rate is low. The payoff may need larger underlying moves or better strike selection.")
    if metrics["return_on_capital"] > 0.20:
        notes.append("Return on capital is unusually high. Validate transaction costs, bid/ask execution, and the scenario-backtest assumption.")
    if metrics["expected_shortfall_95"] > abs(metrics["var_95"]) * 1.5:
        notes.append("Expected shortfall is much larger than VaR, so losses are concentrated in the worst scenarios.")
    if not non_overlapping and holding_days > 1:
        notes.append("Holding-period samples overlap, so Sharpe and win rate can look smoother than independent trades.")
    if backtest["transaction_cost"].sum() > abs(backtest["gross_profit"].sum()) * 0.25:
        notes.append("Transaction costs are a large share of gross P&L. Liquidity and spread assumptions are driving results.")
    return notes


def _render_backtest(
    context,
    analytics,
    holding_days,
    initial_capital,
    non_overlapping,
    slippage_per_contract,
    transaction_cost_per_contract,
    contract_multiplier,
):
    """Render strategy construction, payoff, rolling backtest, and diagnostics."""

    st.subheader("Backtest")
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
            "Long Put Butterfly",
            "Short Put Butterfly",
            "Bull Call Spread",
            "Bear Put Spread",
            "Ratio Call Spread",
            "Short Iron Condor",
            "Long Iron Condor",
            "Custom",
        ],
    )
    ratio_quantity = 2
    if "Butterfly" in strategy:
        other_strike = st.number_input("Butterfly wing width", value=max(float(analytics["selected"]["strike"]) * 0.05, 1.0))
    elif "Strangle" in strategy:
        other_strike = st.number_input("Second strike for strangle", value=float(analytics["selected"]["strike"]) * 1.05)
    elif "Iron Condor" in strategy:
        other_strike = st.number_input("Condor wing width", value=max(float(analytics["selected"]["strike"]) * 0.05, 1.0))
    elif "Spread" in strategy:
        other_strike = st.number_input("Spread width", value=max(float(analytics["selected"]["strike"]) * 0.05, 1.0))
        if strategy == "Ratio Call Spread":
            ratio_quantity = st.number_input("Short call quantity", value=2, min_value=2, step=1)
    else:
        other_strike = None

    legs = _build_strategy_legs(strategy, analytics["selected"], context["chain"], other_strike, ratio_quantity=ratio_quantity)
    st.dataframe(pd.DataFrame(legs), use_container_width=True)
    _render_portfolio_greeks(legs, context, analytics, contract_multiplier)

    grid = payoff_grid(context["spot"], legs)
    backtest = rolling_strategy_backtest(
        context["history"],
        context["spot"],
        legs,
        holding_days=int(holding_days),
        non_overlapping=non_overlapping,
        slippage_per_contract=slippage_per_contract,
        transaction_cost_per_contract=transaction_cost_per_contract,
        contract_multiplier=contract_multiplier,
    )
    margin = estimate_strategy_margin(legs, context["spot"], contract_multiplier=contract_multiplier)
    metrics = backtest_metrics(
        backtest,
        margin,
        initial_capital=initial_capital,
        holding_days=int(holding_days),
    )

    summary_cols = st.columns(6)
    summary_cols[0].metric("Avg PnL", f"{metrics['avg_pnl']:.2f}", f"{metrics['avg_pnl'] / initial_capital:.2%} of capital")
    summary_cols[1].metric("Total PnL", f"{metrics['total_pnl']:.2f}", f"{metrics['return_on_capital']:.2%} of capital")
    summary_cols[2].metric("Win rate", f"{metrics['win_rate']:.2%}", f"{metrics['win_rate'] - 0.50:+.2%} vs 50%")
    summary_cols[3].metric("Sharpe", _format_metric(metrics["sharpe_ratio"]), "annualized")
    summary_cols[4].metric("MDD", f"{metrics['mdd']:.2f}", f"{metrics['mdd_pct']:.2%} of capital")
    summary_cols[5].metric("Return on capital", f"{metrics['return_on_capital']:.2%}", f"{metrics['total_pnl']:.2f} PnL")
    risk_cols = st.columns(4)
    risk_cols[0].metric("Ending equity", f"{metrics['ending_equity']:.2f}", f"{metrics['ending_equity'] - initial_capital:.2f} vs initial")
    risk_cols[1].metric("Margin est.", f"{metrics['margin_estimate']:.2f}", f"{metrics['margin_estimate'] / initial_capital:.2%} of capital")
    risk_cols[2].metric("VaR 95%", f"{metrics['var_95_amount']:.2f}", f"{metrics['var_95']:.2%} of capital")
    risk_cols[3].metric("ES 95%", f"{metrics['expected_shortfall_95_amount']:.2f}", f"{metrics['expected_shortfall_95']:.2%} of capital")

    plot_left, plot_right = st.columns(2)
    with plot_left:
        fig, ax = plt.subplots()
        ax.plot(grid["stock_price"], grid["strategy_profit"])
        ax.axhline(0, color="black", linewidth=1)
        ax.axvline(context["spot"], color="gray", linestyle="--", linewidth=1)
        ax.set_xlabel("Stock price at expiration")
        ax.set_ylabel("Profit")
        ax.set_title("Strategy payoff")
        st.pyplot(fig)

    with plot_right:
        fig, ax = plt.subplots()
        backtest_plot = backtest.copy()
        backtest_plot["cumulative_pnl"] = backtest_plot["strategy_profit"].cumsum()
        backtest_plot["equity"] = initial_capital + backtest_plot["cumulative_pnl"]
        ax.plot(backtest_plot.index, backtest_plot["strategy_profit"], label="Trade PnL", linewidth=1)
        ax.plot(backtest_plot.index, backtest_plot["cumulative_pnl"], label="Cumulative PnL", linewidth=2)
        ax.plot(backtest_plot.index, backtest_plot["equity"], label="Equity", linewidth=1.8, alpha=0.75)
        worst_idx = backtest_plot["strategy_profit"].idxmin()
        best_idx = backtest_plot["strategy_profit"].idxmax()
        ax.scatter([worst_idx], [backtest_plot.loc[worst_idx, "strategy_profit"]], color="#c0392b", zorder=4, label="Worst trade")
        ax.scatter([best_idx], [backtest_plot.loc[best_idx, "strategy_profit"]], color="#1e8449", zorder=4, label="Best trade")
        ax.axhline(0, color="black", linewidth=1)
        ax.set_xlabel("Exit date")
        ax.set_ylabel("PnL")
        ax.set_title("Rolling backtest PnL")
        ax.legend()
        st.pyplot(fig)

    notes = _backtest_diagnostics(metrics, backtest_plot, int(holding_days), non_overlapping)
    if notes:
        st.subheader("Backtest Diagnostics")
        for note in notes:
            st.write(f"- {note}")
    st.caption(
        "Scenario backtest: yfinance does not provide historical option chains here, so the selected current option structure is rescaled through historical underlying prices."
    )
    st.dataframe(backtest_plot.tail(30), use_container_width=True)


def _live_vol_curve_nodes(context):
    """Build OTM IV nodes from the live option chain for the vol curve monitor."""

    rows = []
    forward = context["spot"]
    for option_kind, table in [("call", context["calls_with_mid"]), ("put", context["puts_with_mid"])]:
        if table.empty:
            continue
        for _, row in table.iterrows():
            strike = float(row.get("strike", 0) or 0)
            iv = float(row.get("impliedVolatility", 0) or 0)
            if strike <= 0 or iv <= 0:
                continue
            if option_kind == "put" and strike > forward:
                continue
            if option_kind == "call" and strike < forward:
                continue
            rows.append(
                {
                    "expiry": context["expiration"],
                    "strike": strike,
                    "implied_volatility": iv,
                    "option_kind": option_kind,
                }
            )
    return pd.DataFrame(rows)


def _historical_price_shocks(history, holding_days):
    """Use historical holding-period moves to pick symmetric risk shocks."""

    close = history["Close"].dropna().astype(float)
    returns = close.pct_change(int(holding_days)).dropna()
    if len(returns) < 20:
        return [-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20]
    magnitudes = returns.abs().quantile([0.25, 0.50, 0.75, 0.90, 0.95]).dropna()
    shock_sizes = sorted({round(float(value), 4) for value in magnitudes if value > 0})
    shocks = sorted({0.0} | {-value for value in shock_sizes} | set(shock_sizes))
    return shocks


def _render_risk_management(context, analytics):
    """Render scenario risk matrix, VaR/ES, and volatility curve monitor."""

    st.subheader("Risk Management")
    selected = analytics["selected"]
    risk_legs = [
        OptionLeg(option_kind=option_kind, strike=float(selected["strike"]), quantity=1),
    ]
    matrix = build_risk_matrix(
        risk_legs,
        spot=context["spot"],
        risk_free_rate=risk_free_rate,
        dividend_yield=dividend_yield,
        volatility=analytics["model_iv"],
        time_to_maturity=analytics["T"],
        price_shocks=_historical_price_shocks(context["history"], holding_days),
    )
    st.pyplot(plot_risk_matrix(matrix, title="Selected Contract P&L and Greeks Risk Matrix"))

    returns = context["history"]["Close"].pct_change().dropna()
    var_summary = historical_var_es_summary(returns, confidence_level=0.95, portfolio_value=context["spot"])
    try:
        filtered_summary = ewma_var_es_summary(returns, confidence_level=0.95, portfolio_value=context["spot"])
    except ValueError:
        filtered_summary = var_summary
    risk_cols = st.columns(4)
    risk_cols[0].metric("Historical VaR 95%", f"{var_summary['var']:.2f}")
    risk_cols[1].metric("Expected Shortfall 95%", f"{var_summary['expected_shortfall']:.2f}")
    risk_cols[2].metric("EWMA VaR 95%", f"{filtered_summary['var']:.2f}")
    risk_cols[3].metric("EWMA ES 95%", f"{filtered_summary['expected_shortfall']:.2f}")

    st.subheader("Vol Curve Monitor")
    curves = _live_vol_curve_nodes(context)
    if len(curves) >= 4:
        st.pyplot(plot_vol_curve_monitor(curves, expiry=context["expiration"], forward=context["spot"]))
        st.caption(
            "Smoothed IV shows the fitted smile across strikes; Curvature highlights where the smile bends sharply, which can indicate skew concentration, sparse quotes, or noisy IV nodes."
        )
    else:
        st.info("Not enough live OTM IV nodes from the current yfinance chain to draw a curve monitor.")


st.set_page_config(page_title="Option Analysis System", layout="wide")
st.title("Option Analysis System")

with st.sidebar:
    page = st.selectbox(
        "Menu",
        ["Contract Quote", "Backtest", "Greek Letters", "Risk Management"],
    )
    ticker = st.text_input("Ticker", value="AAPL").upper().strip()
    option_style = st.selectbox("Exercise style", ["European", "American"])
    option_kind = st.radio("Option type", ["call", "put"], horizontal=True)
    risk_free_rate = st.number_input("Risk-free rate", value=0.04, step=0.005, format="%.4f")
    dividend_yield = st.number_input("Dividend yield", value=0.00, step=0.005, format="%.4f")
    holding_days = st.number_input("Backtest holding days", value=20, min_value=1, max_value=252)
    initial_capital = st.number_input("Initial capital", value=100000.0, min_value=1.0, step=1000.0)
    contract_multiplier = st.number_input("Contract multiplier", value=100, min_value=1, step=1)
    transaction_cost_per_contract = st.number_input("Commission per contract", value=0.65, min_value=0.0, step=0.05)
    slippage_per_contract = st.number_input("Slippage per contract", value=0.01, min_value=0.0, step=0.01)
    non_overlapping = st.checkbox("Use non-overlapping backtest trades", value=True)
    st.caption(f"American pricing uses CRR steps fixed at n = {CRR_STEPS}")
    st.divider()
    max_spread_pct = st.slider("Max bid/ask spread", 0.05, 2.00, 0.50, 0.05)
    min_open_interest = st.number_input("Min open interest", value=0, min_value=0, step=10)
    min_volume = st.number_input("Min volume", value=0, min_value=0, step=10)
    require_bid_ask = st.checkbox("Require bid/ask quotes", value=False)

if not ticker:
    st.stop()

try:
    preview_chain = _cached_option_chain(ticker)
    expiration = st.selectbox("Expiration", preview_chain["expirations"])
    context = _load_market_context(
        ticker,
        expiration,
        option_kind,
        max_spread_pct,
        min_open_interest,
        min_volume,
        require_bid_ask,
    )
except Exception as exc:
    st.error(str(exc))
    st.stop()

contracts = context["chain_table"]["contractSymbol"].tolist()
if not contracts:
    st.error("No valid contracts are available after filtering.")
    st.stop()

selected_symbol = st.selectbox("Contract", contracts)
analytics = _selected_contract_analytics(
    context,
    selected_symbol,
    option_kind,
    option_style,
    risk_free_rate,
    dividend_yield,
)

if page == "Contract Quote":
    _render_contract_quote(context, analytics, ticker, option_style)
elif page == "Backtest":
    _render_backtest(
        context,
        analytics,
        holding_days,
        initial_capital,
        non_overlapping,
        slippage_per_contract,
        transaction_cost_per_contract,
        contract_multiplier,
    )
elif page == "Greek Letters":
    _render_greek_letters(context, analytics)
else:
    _render_risk_management(context, analytics)
