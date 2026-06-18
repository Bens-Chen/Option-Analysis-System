import numpy as np

from Trading_Strategies.butterfly import call_butterfly_profit
from Trading_Strategies.iron_condor import long_iron_condor_profit, short_iron_condor_profit
from Trading_Strategies.interval_trading import interval_position, interval_trade_plan
from Trading_Strategies.spread import (
    bear_put_spread_profit,
    bull_call_spread_profit,
    ratio_call_spread_profit,
)
from Trading_Strategies.straddle import long_straddle_profit, short_straddle_profit
from Trading_Strategies.strangle import long_strangle_profit, short_strangle_profit


def test_interval_position_moves_inverse_to_price():
    assert interval_position(70, 30, 70, 200, 0) == 0
    assert interval_position(30, 30, 70, 200, 0) == 200
    assert interval_position(50, 30, 70, 200, 0) == 100


def test_interval_trade_plan_generates_buy_and_sell_actions():
    plan = interval_trade_plan([70, 60, 65], lower_bound=30, upper_bound=70)

    assert plan[0]["action"] == "hold"
    assert plan[1]["action"] == "buy"
    assert plan[2]["action"] == "sell"


def test_call_butterfly_profit_is_best_near_middle_strike():
    stock_prices = np.array([90, 100, 110])
    profits = call_butterfly_profit(
        stock_prices,
        lower_strike=90,
        middle_strike=100,
        upper_strike=110,
        lower_call_premium=12,
        middle_call_premium=6,
        upper_call_premium=2,
    )

    assert profits[1] > profits[0]
    assert profits[1] > profits[2]


def test_straddle_long_and_short_are_opposites():
    long_profit = long_straddle_profit(120, 100, 8, 6)
    short_profit = short_straddle_profit(120, 100, 8, 6)

    assert long_profit == -short_profit


def test_strangle_long_and_short_are_opposites():
    long_profit = long_strangle_profit(120, 90, 110, 4, 5)
    short_profit = short_strangle_profit(120, 90, 110, 4, 5)

    assert long_profit == -short_profit


def test_bull_call_spread_has_limited_upside():
    assert bull_call_spread_profit(80, 90, 110, 12, 4) == -8
    assert bull_call_spread_profit(130, 90, 110, 12, 4) == 12


def test_bear_put_spread_has_limited_upside():
    assert bear_put_spread_profit(130, 90, 110, 3, 10) == -7
    assert bear_put_spread_profit(70, 90, 110, 3, 10) == 13


def test_ratio_call_spread_can_lose_on_large_up_move():
    stock_prices = np.array([90, 110, 140])
    profits = ratio_call_spread_profit(stock_prices, 100, 115, 8, 3, short_call_quantity=2)

    assert profits[1] > profits[0]
    assert profits[2] < profits[1]


def test_iron_condor_short_and_long_are_opposites():
    short_profit = short_iron_condor_profit(100, 80, 90, 110, 120, 1, 4, 4, 1)
    long_profit = long_iron_condor_profit(100, 80, 90, 110, 120, 1, 4, 4, 1)

    assert short_profit == -long_profit
    assert short_profit > 0
