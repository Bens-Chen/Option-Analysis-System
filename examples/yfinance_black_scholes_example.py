"""Example script that prices a yfinance option input with Black-Scholes."""

from Market_Data.yfinance_data import build_option_inputs
from Methods.black_scholes import BS


inputs = build_option_inputs(
    ticker="AAPL",
    strike=200,
    risk_free_rate=0.04,
    dividend_yield=0.0,
    time_to_maturity=30 / 365,
    period="1y",
)

call_price, put_price = BS(
    inputs["S"],
    inputs["K"],
    inputs["r"],
    inputs["q"],
    inputs["sigma"],
    inputs["T"],
)

print(f"Spot: {inputs['S']:.2f}")
print(f"Historical volatility: {inputs['sigma']:.2%}")
print(f"Call price: {call_price:.4f}")
print(f"Put price: {put_price:.4f}")
