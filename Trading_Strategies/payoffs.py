"""Basic option payoff primitives used by strategy modules."""

import numpy as np


def call_payoff(stock_price, strike):
    return np.maximum(np.asarray(stock_price, dtype=float) - strike, 0.0)


def put_payoff(stock_price, strike):
    return np.maximum(strike - np.asarray(stock_price, dtype=float), 0.0)
