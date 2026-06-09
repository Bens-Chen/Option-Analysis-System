import numpy as np

from Trading_Strategies.adr_arbitrage import adr_premium_ratio, adr_signal
from Trading_Strategies.butterfly import call_butterfly_profit
from Trading_Strategies.interval_trading import interval_position, interval_trade_plan
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


def test_adr_arbitrage_signal_for_expensive_adr():
    premium = adr_premium_ratio(
        adr_price_usd=8,
        local_share_price=40,
        shares_per_adr=5,
        exchange_rate=30,
    )
    signal = adr_signal(premium, long_term_average=0.20, upper_bound=0.25, lower_bound=0.15)

    assert premium == 0.20
    assert signal["signal"] == "hold"

    signal = adr_signal(0.26, long_term_average=0.20, upper_bound=0.25, lower_bound=0.15)
    assert signal["signal"] == "long_local_short_adr"
