from datetime import date
import importlib.util
from pathlib import Path
import sys
from importlib.machinery import SourceFileLoader

import matplotlib.pyplot as plt
import numpy as np
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
from Implied_Volatility.iv_surface import current_otm_surface_iv
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
from Risk_Management.var_es import ewma_var_es_summary, historical_var_es_summary, iv_smoothed_var_es_summary
from Risk_Management.vol_curve_monitor import plot_vol_curve_monitor, vol_curve_diagnostics
from iv_smile import IV_smile_arrays, fit_svi_smile


def _load_vix_svix_module():
    module_path = IMPLIED_VOL_ROOT / "vix_svix"
    loader = SourceFileLoader("vix_svix_module", str(module_path))
    spec = importlib.util.spec_from_loader("vix_svix_module", loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIX_SVIX_MODULE = _load_vix_svix_module()
CRR_STEPS = 500


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
    history = _cached_price_history(ticker, "10y")
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
        "ticker": ticker,
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
    chain_table = context["chain_table"]
    selected = chain_table.loc[chain_table["contractSymbol"] == selected_symbol].iloc[0].to_dict()
    spot = context["spot"]
    historical_vol = context["historical_vol"]
    T = _days_to_years(context["expiration"])
    market_price = _mid_price(selected)
    yfinance_iv = float(selected.get("impliedVolatility", 0) or 0)
    try:
        forward = estimate_forward_price(context["matched_chain"], risk_free_rate, T)["F"]
    except Exception:
        forward = spot
    try:
        model_volatility, model_volatility_source = current_otm_surface_iv(
            context["calls_with_mid"],
            context["puts_with_mid"],
            forward,
            float(selected["strike"]),
            T,
        )
    except ValueError:
        model_volatility = historical_vol
        model_volatility_source = "Newey-West volatility"

    try:
        model_iv = implied_volatility_from_price(
            market_price,
            spot,
            float(selected["strike"]),
            risk_free_rate,
            dividend_yield,
            T,
            option_kind,
            pricing_model="BS",
        )
        iv_note = ""
    except ValueError as exc:
        model_iv = historical_vol
        iv_note = f"Could not solve market implied IV from market price. Newey-West volatility is shown instead. Detail: {exc}"

    if option_style == "American":
        model_price = crr_option_price(
            spot,
            float(selected["strike"]),
            risk_free_rate,
            dividend_yield,
            model_volatility,
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
            model_volatility,
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
            model_volatility,
            T,
            option_kind,
        )
        greeks = black_scholes_greeks(
            spot,
            float(selected["strike"]),
            risk_free_rate,
            dividend_yield,
            model_volatility,
            T,
            option_kind,
        )

    market_iv_for_price = yfinance_iv if yfinance_iv > 0 else model_iv
    market_iv_price = None
    if market_iv_for_price > 0:
        if option_style == "American":
            market_iv_price = crr_option_price(
                spot,
                float(selected["strike"]),
                risk_free_rate,
                dividend_yield,
                market_iv_for_price,
                T,
                option_kind,
                option_style="American",
                steps=CRR_STEPS,
            )
        else:
            market_iv_price = option_price_from_bs(
                spot,
                float(selected["strike"]),
                risk_free_rate,
                dividend_yield,
                market_iv_for_price,
                T,
                option_kind,
            )

    return {
        "selected": selected,
        "T": T,
        "market_price": market_price,
        "yfinance_iv": yfinance_iv,
        "model_iv": model_iv,
        "model_volatility": model_volatility,
        "model_volatility_source": model_volatility_source,
        "historical_volatility": historical_vol,
        "model_price": model_price,
        "market_iv_price": market_iv_price,
        "market_iv_source": "yfinance IV" if yfinance_iv > 0 else "solved IV",
        "greeks": greeks,
        "iv_note": iv_note,
    }


def _render_contract_quote(context, analytics, active_ticker, option_style):
    st.subheader("Selected Contract Quote")
    quote_cols = st.columns(5)
    quote_cols[0].metric("yfinance price", f"{analytics['market_price']:.4f}")
    quote_cols[1].metric(f"{option_style} surface price", f"{analytics['model_price']:.4f}")
    quote_cols[2].metric("Market-IV price", _format_metric(analytics["market_iv_price"], "{:.4f}"))
    quote_cols[3].metric("Surface IV", f"{analytics['model_volatility']:.2%}")
    quote_cols[4].metric("yfinance IV", f"{analytics['yfinance_iv']:.2%}" if analytics["yfinance_iv"] > 0 else "N/A")
    if analytics["iv_note"]:
        st.warning(analytics["iv_note"])
    st.caption(
        f"Surface price uses {analytics['model_volatility_source']}. Market-IV price uses {analytics['market_iv_source']}."
    )

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


def _live_iv_surface_points(context, max_expirations=10):
    selected_expiration = context["expiration"]
    expirations = [selected_expiration]
    expirations.extend([expiration for expiration in context["expirations"] if expiration != selected_expiration])
    rows = []

    for expiration in expirations[:max_expirations]:
        chain = context["chain"] if expiration == selected_expiration else _cached_option_chain(context["ticker"], expiration)
        calls = add_mid_prices(chain["calls"])
        puts = add_mid_prices(chain["puts"])
        matched = matched_option_chain_prices(calls, puts)
        days_to_expiration = max((pd.to_datetime(expiration).date() - date.today()).days, 1)
        try:
            forward = estimate_forward_price(matched, risk_free_rate, days_to_expiration / 365)["F"]
        except Exception:
            forward = context["spot"]

        for option_kind, table in [("put", puts), ("call", calls)]:
            if table.empty:
                continue
            strikes = pd.to_numeric(table["strike"], errors="coerce")
            ivs = pd.to_numeric(table["impliedVolatility"], errors="coerce")
            valid = strikes.gt(0) & ivs.gt(0) & ivs.le(5.0) & np.isfinite(strikes) & np.isfinite(ivs)
            if option_kind == "put":
                valid &= strikes.lt(forward)
            else:
                valid &= strikes.gt(forward)
            nodes = pd.DataFrame(
                {
                    "expiration": expiration,
                    "days_to_expiration": days_to_expiration,
                    "strike": strikes[valid].astype(float),
                    "impliedVolatility": ivs[valid].astype(float),
                    "option_kind": option_kind,
                }
            )
            rows.append(nodes)

    if not rows:
        return pd.DataFrame()
    surface = pd.concat(rows, ignore_index=True)
    if surface.empty:
        return surface
    return (
        surface.groupby(["expiration", "days_to_expiration", "strike"], as_index=False)
        .agg({"impliedVolatility": "median", "option_kind": "first"})
        .sort_values(["days_to_expiration", "strike"])
        .reset_index(drop=True)
    )


def _plot_iv_surface(surface, selected_strike, selected_days, selected_iv):
    fig = plt.figure(figsize=(10, 7))
    try:
        ax = fig.add_subplot(111, projection="3d", computed_zorder=False)
    except AttributeError:
        ax = fig.add_subplot(111, projection="3d")

    x = surface["strike"].to_numpy(dtype=float)
    y = surface["days_to_expiration"].to_numpy(dtype=float)
    z = surface["impliedVolatility"].to_numpy(dtype=float) * 100
    if len(surface) >= 6 and len(np.unique(x)) >= 3 and len(np.unique(y)) >= 2:
        ax.plot_trisurf(x, y, z, cmap="viridis", alpha=0.62, linewidth=0.2, zorder=1)
    ax.scatter(x, y, z, color="#1f77b4", s=16, alpha=0.60, label="OTM IV nodes", zorder=2)

    selected_z = float(selected_iv) * 100
    ax.scatter(
        [selected_strike],
        [selected_days],
        [selected_z],
        color="red",
        s=90,
        marker="o",
        depthshade=False,
        label="Selected contract",
        zorder=100,
    )
    ax.set_xlabel("Strike", labelpad=6)
    ax.set_ylabel("DTE", labelpad=6)
    ax.set_zlabel("IV (%)", labelpad=6)
    ax.set_title("IV Surface")
    ax.view_init(elev=24, azim=-132)
    ax.tick_params(axis="both", which="major", labelsize=8, pad=1)
    ax.tick_params(axis="z", which="major", labelsize=8, pad=1)
    ax.legend(loc="upper left", fontsize=8, frameon=True)
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.94)
    return fig


def _render_greek_letters(context, analytics):
    st.subheader("Greek Letters")
    greeks = analytics["greeks"]
    metric_cols = st.columns(5)
    metric_cols[0].metric("Delta", f"{greeks['delta']:.4f}")
    metric_cols[1].metric("Gamma", f"{greeks['gamma']:.4f}")
    metric_cols[2].metric("Theta/day", f"{greeks['theta_per_day']:.4f}")
    metric_cols[3].metric("Vega", f"{greeks['vega']:.4f}")
    metric_cols[4].metric("Rho", f"{greeks['rho']:.4f}")
    if "model_price" in greeks:
        st.caption(f"CRR American model price using current surface volatility: {greeks['model_price']:.4f}")

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
        comparison_cols[0].metric("Selected implied IV", f"{analytics['model_iv']:.2%}")
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

    try:
        surface = _live_iv_surface_points(context)
        if surface.empty:
            st.info("Not enough live OTM IV nodes to draw an IV surface.")
        else:
            selected = analytics["selected"]
            selected_iv = analytics["yfinance_iv"] if analytics["yfinance_iv"] > 0 else analytics["model_volatility"]
            selected_days = int(round(analytics["T"] * 365))
            st.pyplot(
                _plot_iv_surface(
                    surface,
                    float(selected["strike"]),
                    selected_days,
                    selected_iv,
                )
            )
    except Exception as exc:
        st.warning(f"Could not build IV surface from the available option chains: {exc}")


def _build_strategy_legs(strategy, selected, chain, other_strike, ratio_quantity=2):
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
    totals = {"delta": 0.0, "gamma": 0.0, "theta_per_day": 0.0, "vega": 0.0, "rho": 0.0}
    total_quantity = 0
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
        quantity = abs(int(leg.get("quantity", 1)))
        scale = side * quantity
        total_quantity += quantity
        for key in totals:
            totals[key] += float(greeks[key]) * scale
    if total_quantity > 0:
        for key in totals:
            totals[key] /= total_quantity
    return totals


def _render_portfolio_greeks(legs, context, analytics, contract_multiplier):
    greeks = _portfolio_greeks(
        legs,
        context["spot"],
        risk_free_rate,
        dividend_yield,
        analytics["model_volatility"],
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
        risk_free_rate=risk_free_rate,
        dividend_yield=dividend_yield,
        time_to_maturity=analytics["T"],
    )
    margin = float(backtest["margin_estimate"].max())
    metrics = backtest_metrics(
        backtest,
        margin,
        initial_capital=initial_capital,
        holding_days=int(holding_days),
    )

    summary_cols = st.columns(6)
    summary_cols[0].metric("Avg PnL", f"{metrics['avg_pnl']:.2f}")
    summary_cols[1].metric("Total PnL", f"{metrics['total_pnl']:.2f}")
    summary_cols[2].metric("Win rate", f"{metrics['win_rate']:.2%}")
    summary_cols[3].metric("Sharpe", _format_metric(metrics["sharpe_ratio"]))
    summary_cols[4].metric("MDD", f"{metrics['mdd']:.2f}")
    summary_cols[5].metric("Return on capital", f"{metrics['return_on_capital']:.2%}")
    risk_cols = st.columns(4)
    risk_cols[0].metric("Ending equity", f"{metrics['ending_equity']:.2f}")
    risk_cols[1].metric("Margin est.", f"{metrics['margin_estimate']:.2f}")
    risk_cols[2].metric("VaR 95%", f"{metrics['var_95_amount']:.2f}")
    risk_cols[3].metric("ES 95%", f"{metrics['expected_shortfall_95_amount']:.2f}")

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
        ax.set_title("Model rolling backtest PnL")
        ax.legend()
        st.pyplot(fig)

    st.caption(
        "Model rolling backtest: each entry date rebuilds the same moneyness strategy and prices entry/exit options with BS plus a rolling Newey-West volatility proxy from yfinance underlying prices."
    )
    st.caption(
        "In the table, entry_spot and exit_spot are underlying prices. model_entry_value and model_exit_value are the model-estimated option strategy values after side, quantity, and contract multiplier."
    )
    st.dataframe(backtest_plot.tail(30), use_container_width=True)


def _live_vol_curve_nodes(context):
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
    close = history["Close"].dropna().astype(float)
    returns = close.pct_change(int(holding_days)).dropna()
    if len(returns) < 20:
        return [-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20]
    magnitudes = returns.abs().quantile([0.25, 0.50, 0.75, 0.90, 0.95]).dropna()
    shock_sizes = sorted({round(float(value), 4) for value in magnitudes if value > 0})
    shocks = sorted({0.0} | {-value for value in shock_sizes} | set(shock_sizes))
    return shocks


def _render_risk_management(context, analytics):
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
        volatility=analytics["model_volatility"],
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
    try:
        iv_summary = iv_smoothed_var_es_summary(
            returns,
            annualized_volatility=analytics["model_volatility"],
            confidence_level=0.95,
            portfolio_value=context["spot"],
        )
    except ValueError:
        iv_summary = var_summary
    risk_cols = st.columns(6)
    risk_cols[0].metric("Historical VaR 95%", f"{var_summary['var']:.2f}")
    risk_cols[1].metric("Expected Shortfall 95%", f"{var_summary['expected_shortfall']:.2f}")
    risk_cols[2].metric("EWMA VaR 95%", f"{filtered_summary['var']:.2f}")
    risk_cols[3].metric("EWMA ES 95%", f"{filtered_summary['expected_shortfall']:.2f}")
    risk_cols[4].metric("IV-smoothed VaR 95%", f"{iv_summary['var']:.2f}")
    risk_cols[5].metric("IV-smoothed ES 95%", f"{iv_summary['expected_shortfall']:.2f}")

    st.subheader("Vol Curve Monitor")
    curves = _live_vol_curve_nodes(context)
    if len(curves) >= 4:
        st.pyplot(plot_vol_curve_monitor(curves, expiry=context["expiration"], forward=context["spot"]))
        diagnostics, curve_summary = vol_curve_diagnostics(curves, expiry=context["expiration"], forward=context["spot"])
        curve_cols = st.columns(4)
        curve_cols[0].metric("ATM IV", f"{curve_summary['atm_iv_pct']:.2f}%")
        curve_cols[1].metric("IV range", f"{curve_summary['iv_range_pct']:.2f} vol pts")
        curve_cols[2].metric("Max |curvature|", f"{curve_summary['max_abs_curvature']:.4f}")
        curve_cols[3].metric("ATM strike", f"{curve_summary['atm_strike']:.2f}")
        st.caption(
            "Curvature is the second derivative of the fitted IV smile. Large absolute curvature marks strikes where IV bends sharply; that can indicate skew concentration, noisy quotes, sparse strikes, or local relative-value points for spreads and butterflies."
        )
        display_curve = diagnostics.sort_values("abs_curvature", ascending=False).head(8)
        st.dataframe(
            display_curve[
                ["strike", "moneyness", "curve_zone", "iv_pct", "slope_per_strike", "curvature", "abs_curvature"]
            ],
            use_container_width=True,
        )
    else:
        st.info("Not enough live OTM IV nodes from the current yfinance chain to draw a curve monitor.")


st.set_page_config(page_title="Option Analysis System", layout="wide")
st.title("Option Analysis System")

with st.sidebar:
    page = st.selectbox(
        "Menu",
        ["Contract Quote", "Backtest", "Greek Letters & IV Smile/Surface", "Risk Management"],
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
    st.caption(f"American pricing uses CRR steps fixed at n = {CRR_STEPS} for interactive speed")
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
elif page == "Greek Letters & IV Smile/Surface":
    _render_greek_letters(context, analytics)
else:
    _render_risk_management(context, analytics)
