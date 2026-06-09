import pandas as pd

from Market_Data.yfinance_data import estimate_annualized_volatility, latest_close


def test_latest_close_reads_last_valid_close():
    history = pd.DataFrame({"Close": [100.0, None, 105.0]})

    assert latest_close(history) == 105.0


def test_estimate_annualized_volatility_from_close_prices():
    history = pd.DataFrame({"Close": [100.0, 102.0, 101.0, 104.0]})

    assert estimate_annualized_volatility(history) > 0
