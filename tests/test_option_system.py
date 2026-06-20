import pandas as pd
import pytest

from Implied_Volatility.iv_surface import current_otm_surface_iv
from Option_System.analytics import black_scholes_greeks, crr_greeks_by_bump, implied_volatility_from_price, option_price_from_bs
from Option_System.research import (
    build_research_chain_table,
    event_straddle_analysis,
    mispricing_scanner,
    paper_alerts,
    surface_summary,
    tear_sheet_metrics,
    volatility_surface_table,
)
from Option_System.strategy_engine import (
    backtest_metrics,
    build_chain_strategy_legs,
    rolling_strategy_backtest,
    strategy_profit,
)


def test_black_scholes_greeks_returns_expected_keys():
    greeks = black_scholes_greeks(
        S=100,
        K=100,
        r=0.04,
        q=0.0,
        sigma=0.2,
        T=30 / 365,
        option_kind="call",
    )

    assert {"delta", "gamma", "theta_per_day", "vega", "rho"} <= set(greeks)


def test_implied_vol_price_roundtrip_matches_market_price():
    market_price = 4.25
    model_iv = implied_volatility_from_price(
        market_price=market_price,
        S=100,
        K=102,
        r=0.04,
        q=0.0,
        T=30 / 365,
        option_kind="call",
    )

    model_price = option_price_from_bs(100, 102, 0.04, 0.0, model_iv, 30 / 365, "call")

    assert model_price == pytest.approx(market_price)


def test_strategy_profit_combines_custom_legs():
    legs = [
        {"option_kind": "call", "side": "long", "strike": 100, "premium": 5, "quantity": 1},
        {"option_kind": "put", "side": "long", "strike": 100, "premium": 4, "quantity": 1},
    ]

    profit = strategy_profit([90, 100, 110], legs)

    assert profit.tolist() == [1.0, -9.0, 1.0]


def test_backtest_metrics_includes_sharpe_mdd_and_margin():
    result = pd.DataFrame({"strategy_profit": [100.0, -40.0, 80.0]})

    metrics = backtest_metrics(result, margin=500)

    assert {"sharpe_ratio", "mdd", "margin_estimate", "return_on_margin"} <= set(metrics)
    assert metrics["margin_estimate"] > 0


def test_rolling_backtest_reprices_strategy_with_model_premiums():
    prices = [100 + index * 0.2 + (index % 5) * 0.1 for index in range(90)]
    history = pd.DataFrame({"Close": prices})
    legs = [
        {
            "option_kind": "call",
            "side": "long",
            "strike": 100,
            "premium": 3,
            "bid": 2.8,
            "ask": 3.2,
            "lastPrice": 3,
            "quantity": 1,
        }
    ]

    result = rolling_strategy_backtest(
        history,
        current_spot=100,
        legs=legs,
        holding_days=2,
        non_overlapping=True,
        slippage_per_contract=0.1,
        transaction_cost_per_contract=0.5,
        contract_multiplier=100,
        risk_free_rate=0.04,
        dividend_yield=0.0,
        time_to_maturity=30 / 365,
        volatility_window=20,
    )

    assert not result.empty
    assert {"model_entry_value", "model_exit_value", "entry_sigma", "exit_sigma", "margin_estimate"} <= set(result.columns)
    assert (result["transaction_cost"] == 1.0).all()
    assert (result["entry_sigma"] > 0).all()


def test_backtest_metrics_uses_initial_capital_returns():
    backtest = pd.DataFrame({"strategy_profit": [100.0, -50.0, 150.0]})

    metrics = backtest_metrics(backtest, margin=500, initial_capital=10000, holding_days=5)

    assert metrics["return_on_capital"] == pytest.approx(0.02)
    assert metrics["ending_equity"] == pytest.approx(10200)
    assert {"mdd_pct", "var_95", "expected_shortfall_95", "var_95_amount", "expected_shortfall_95_amount"} <= set(metrics)
    assert metrics["var_95_amount"] == pytest.approx(metrics["var_95"] * 10000)


def test_current_otm_surface_iv_interpolates_from_otm_nodes():
    calls = pd.DataFrame(
        {
            "strike": [105.0, 110.0, 115.0],
            "impliedVolatility": [0.22, 0.24, 0.27],
        }
    )
    puts = pd.DataFrame(
        {
            "strike": [85.0, 90.0, 95.0],
            "impliedVolatility": [0.31, 0.28, 0.25],
        }
    )

    surface_iv, source = current_otm_surface_iv(calls, puts, forward=100, strike=105)

    assert source == "current OTM IV surface"
    assert 0.20 < surface_iv < 0.30


def test_crr_greeks_supports_american_option_style():
    greeks = crr_greeks_by_bump(
        S=100,
        K=100,
        r=0.04,
        q=0.0,
        sigma=0.2,
        T=30 / 365,
        option_kind="put",
        option_style="American",
        steps=50,
    )

    assert {"model_price", "delta", "gamma", "theta_per_day", "vega", "rho"} <= set(greeks)


def test_build_chain_strategy_legs_adds_call_butterfly():
    calls = pd.DataFrame(
        [
            {"strike": 95, "bid": 7.0, "ask": 7.4, "lastPrice": 7.2},
            {"strike": 100, "bid": 4.0, "ask": 4.4, "lastPrice": 4.2},
            {"strike": 105, "bid": 2.0, "ask": 2.4, "lastPrice": 2.2},
        ]
    )
    puts = pd.DataFrame()
    selected = {"strike": 100, "option_kind": "call", "bid": 4.0, "ask": 4.4, "lastPrice": 4.2}

    legs = build_chain_strategy_legs("Long Call Butterfly", selected, calls, puts, other_strike=5)

    assert [leg["quantity"] for leg in legs] == [1, 2, 1]
    assert [leg["side"] for leg in legs] == ["long", "short", "long"]


def test_build_chain_strategy_legs_adds_put_butterfly():
    calls = pd.DataFrame()
    puts = pd.DataFrame(
        [
            {"strike": 95, "bid": 2.0, "ask": 2.4, "lastPrice": 2.2},
            {"strike": 100, "bid": 4.0, "ask": 4.4, "lastPrice": 4.2},
            {"strike": 105, "bid": 7.0, "ask": 7.4, "lastPrice": 7.2},
        ]
    )
    selected = {"strike": 100, "option_kind": "put", "bid": 4.0, "ask": 4.4, "lastPrice": 4.2}

    legs = build_chain_strategy_legs("Long Put Butterfly", selected, calls, puts, other_strike=5)

    assert [leg["option_kind"] for leg in legs] == ["put", "put", "put"]
    assert [leg["quantity"] for leg in legs] == [1, 2, 1]
    assert [leg["side"] for leg in legs] == ["long", "short", "long"]


def _sample_spread_chains():
    calls = pd.DataFrame(
        [
            {"strike": 90, "bid": 12.0, "ask": 12.4, "lastPrice": 12.2},
            {"strike": 95, "bid": 8.0, "ask": 8.4, "lastPrice": 8.2},
            {"strike": 100, "bid": 5.0, "ask": 5.4, "lastPrice": 5.2},
            {"strike": 105, "bid": 2.5, "ask": 2.9, "lastPrice": 2.7},
            {"strike": 110, "bid": 1.1, "ask": 1.5, "lastPrice": 1.3},
        ]
    )
    puts = pd.DataFrame(
        [
            {"strike": 90, "bid": 1.0, "ask": 1.4, "lastPrice": 1.2},
            {"strike": 95, "bid": 2.0, "ask": 2.4, "lastPrice": 2.2},
            {"strike": 100, "bid": 4.0, "ask": 4.4, "lastPrice": 4.2},
            {"strike": 105, "bid": 7.0, "ask": 7.4, "lastPrice": 7.2},
            {"strike": 110, "bid": 11.0, "ask": 11.4, "lastPrice": 11.2},
        ]
    )
    selected = {"strike": 100, "option_kind": "call", "bid": 5.0, "ask": 5.4, "lastPrice": 5.2}
    return calls, puts, selected


def test_build_chain_strategy_legs_adds_bull_call_spread():
    calls, puts, selected = _sample_spread_chains()

    legs = build_chain_strategy_legs("Bull Call Spread", selected, calls, puts, other_strike=5)

    assert [leg["option_kind"] for leg in legs] == ["call", "call"]
    assert [leg["strike"] for leg in legs] == [100.0, 105.0]
    assert [leg["side"] for leg in legs] == ["long", "short"]


def test_build_chain_strategy_legs_adds_bear_put_spread():
    calls, puts, selected = _sample_spread_chains()

    legs = build_chain_strategy_legs("Bear Put Spread", selected, calls, puts, other_strike=5)

    assert [leg["option_kind"] for leg in legs] == ["put", "put"]
    assert [leg["strike"] for leg in legs] == [100.0, 95.0]
    assert [leg["side"] for leg in legs] == ["long", "short"]


def test_build_chain_strategy_legs_adds_ratio_call_spread():
    calls, puts, selected = _sample_spread_chains()

    legs = build_chain_strategy_legs("Ratio Call Spread", selected, calls, puts, other_strike=5, ratio_quantity=3)

    assert [leg["option_kind"] for leg in legs] == ["call", "call"]
    assert [leg["side"] for leg in legs] == ["long", "short"]
    assert [leg["quantity"] for leg in legs] == [1, 3]


def test_build_chain_strategy_legs_adds_short_iron_condor():
    calls, puts, selected = _sample_spread_chains()

    legs = build_chain_strategy_legs("Short Iron Condor", selected, calls, puts, other_strike=5)

    assert [leg["option_kind"] for leg in legs] == ["put", "put", "call", "call"]
    assert [leg["strike"] for leg in legs] == [90.0, 95.0, 105.0, 110.0]
    assert [leg["side"] for leg in legs] == ["long", "short", "short", "long"]


def _sample_option_chains():
    calls = pd.DataFrame(
        {
            "contractSymbol": ["C95", "C100", "C105"],
            "strike": [95.0, 100.0, 105.0],
            "bid": [8.8, 5.0, 2.8],
            "ask": [9.2, 5.4, 3.2],
            "lastPrice": [9.0, 5.2, 3.0],
            "volume": [100, 100, 100],
            "openInterest": [200, 200, 200],
            "impliedVolatility": [0.32, 0.25, 0.23],
        }
    )
    puts = pd.DataFrame(
        {
            "contractSymbol": ["P95", "P100", "P105"],
            "strike": [95.0, 100.0, 105.0],
            "bid": [2.0, 4.7, 7.5],
            "ask": [2.4, 5.1, 7.9],
            "lastPrice": [2.2, 4.9, 7.7],
            "volume": [100, 100, 100],
            "openInterest": [200, 200, 200],
            "impliedVolatility": [0.30, 0.26, 0.28],
        }
    )
    return {"2026-07-17": {"calls": calls, "puts": puts}, "2026-08-21": {"calls": calls, "puts": puts}}


def test_research_table_supports_surface_and_scanner():
    table = build_research_chain_table(
        _sample_option_chains(),
        spot=100,
        risk_free_rate=0.04,
        dividend_yield=0.0,
        model_volatility=0.20,
    )

    surface = volatility_surface_table(table, option_kind="call")
    scanner = mispricing_scanner(table, min_abs_mispricing=0.01)
    stats = surface_summary(table)

    assert not table.empty
    assert not surface.empty
    assert not scanner.empty
    assert {"atm_iv", "skew_90_110", "term_structure_slope", "iv_rank_proxy"} <= set(stats)
    assert "pricing_signal" in scanner.columns


def test_tear_sheet_metrics_includes_var_and_monthly_pnl():
    backtest = pd.DataFrame(
        {"strategy_profit": [1.0, -2.0, 3.0, -1.0]},
        index=pd.to_datetime(["2026-01-02", "2026-01-03", "2026-02-02", "2026-02-03"]),
    )

    metrics = tear_sheet_metrics(backtest, margin=10)

    assert {"var", "cvar", "monthly_pnl", "best_trade", "worst_trade"} <= set(metrics)
    assert metrics["best_trade"] == 3.0
    assert metrics["worst_trade"] == -2.0


def test_event_analysis_returns_atm_straddle_implied_move():
    chains = _sample_option_chains()["2026-07-17"]
    history = pd.DataFrame(
        {"Close": [100.0, 103.0]},
        index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
    )

    result = event_straddle_analysis(history, spot=100, calls=chains["calls"], puts=chains["puts"], event_date="2026-01-01")

    assert result["atm_strike"] == 100.0
    assert result["implied_move"] > 0
    assert result["actual_next_move"] == pytest.approx(0.03)


def test_paper_alerts_flags_high_iv_and_large_mispricing():
    scanner = pd.DataFrame(
        {
            "pct_mispricing": [0.20],
            "contractSymbol": ["C100"],
            "pricing_signal": ["rich_vs_model"],
        }
    )

    alerts = paper_alerts({"iv_rank_proxy": 0.90, "skew_90_110": 0.12}, scanner)

    assert set(alerts["alert"]) == {"high_iv_rank_proxy", "steep_surface_skew", "large_model_mispricing"}
