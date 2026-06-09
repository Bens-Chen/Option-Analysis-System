import pandas as pd

from Option_System.analytics import black_scholes_greeks, crr_greeks_by_bump
from Option_System.strategy_engine import (
    backtest_metrics,
    build_chain_strategy_legs,
    estimate_strategy_margin,
    historical_scenario_backtest,
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


def test_strategy_profit_combines_custom_legs():
    legs = [
        {"option_kind": "call", "side": "long", "strike": 100, "premium": 5, "quantity": 1},
        {"option_kind": "put", "side": "long", "strike": 100, "premium": 4, "quantity": 1},
    ]

    profit = strategy_profit([90, 100, 110], legs)

    assert profit.tolist() == [1.0, -9.0, 1.0]


def test_historical_scenario_backtest_returns_profit_column():
    history = pd.DataFrame({"Close": [100, 101, 102, 99, 103, 105]})
    legs = [{"option_kind": "call", "side": "long", "strike": 100, "premium": 3, "quantity": 1}]

    result = historical_scenario_backtest(history, spot=100, legs=legs, holding_days=1)

    assert "strategy_profit" in result.columns
    assert not result.empty


def test_backtest_metrics_includes_sharpe_mdd_and_margin():
    history = pd.DataFrame({"Close": [100, 101, 102, 99, 103, 105]})
    legs = [{"option_kind": "call", "side": "long", "strike": 100, "premium": 3, "quantity": 1}]
    result = historical_scenario_backtest(history, spot=100, legs=legs, holding_days=1)
    margin = estimate_strategy_margin(legs, spot=100)

    metrics = backtest_metrics(result, margin)

    assert {"sharpe_ratio", "mdd", "margin_estimate", "return_on_margin"} <= set(metrics)
    assert metrics["margin_estimate"] > 0


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
