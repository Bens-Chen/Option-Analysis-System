import pandas as pd

from Option_System.analytics import black_scholes_greeks
from Option_System.strategy_engine import historical_scenario_backtest, strategy_profit


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
