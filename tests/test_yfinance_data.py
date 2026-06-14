import math

import numpy as np
import pandas as pd

from Market_Data.yfinance_data import (
    build_vix_svix_inputs,
    estimate_annualized_volatility,
    estimate_forward_price,
    latest_close,
    option_mid_price,
)


def test_latest_close_reads_last_valid_close():
    history = pd.DataFrame({"Close": [100.0, None, 105.0]})

    assert latest_close(history) == 105.0


def test_estimate_annualized_volatility_from_close_prices():
    history = pd.DataFrame({"Close": [100.0, 102.0, 101.0, 104.0]})

    assert estimate_annualized_volatility(history) > 0


def test_option_mid_price_uses_last_price_when_bid_or_ask_is_missing():
    row = pd.Series({"bid": np.nan, "ask": 2.0, "lastPrice": 1.8})

    assert option_mid_price(row) == 1.8


def test_estimate_forward_price_uses_closest_call_put_pair():
    matched = pd.DataFrame(
        {
            "strike": [95.0, 100.0, 105.0],
            "call_mid": [8.0, 5.2, 3.0],
            "put_mid": [2.0, 4.9, 7.5],
        }
    )

    result = estimate_forward_price(matched, risk_free_rate=0.04, time_to_maturity=30 / 365)

    expected_forward = 100.0 + math.exp(0.04 * 30 / 365) * (5.2 - 4.9)
    assert result["reference_strike"] == 100.0
    assert result["F"] == expected_forward


def test_build_vix_svix_inputs_returns_forward_and_clean_price_lists():
    calls = pd.DataFrame(
        {
            "strike": [95.0, 100.0, 105.0],
            "bid": [7.8, 5.0, 2.8],
            "ask": [8.2, 5.4, 3.2],
            "lastPrice": [8.0, 5.1, 3.0],
            "impliedVolatility": [0.3, 0.25, 0.22],
        }
    )
    puts = pd.DataFrame(
        {
            "strike": [95.0, 100.0, 105.0],
            "bid": [1.8, 4.7, 7.3],
            "ask": [2.2, 5.1, 7.7],
            "lastPrice": [2.0, 4.9, 7.5],
            "impliedVolatility": [0.32, 0.26, 0.24],
        }
    )

    inputs = build_vix_svix_inputs(calls, puts, risk_free_rate=0.04, time_to_maturity=30 / 365)

    assert inputs["K_list"] == [95.0, 100.0, 105.0]
    assert inputs["call_price_list"] == [8.0, 5.2, 3.0]
    assert inputs["put_price_list"] == [2.0, 4.9, 7.5]
    assert inputs["F"] == inputs["forward"]["F"]
