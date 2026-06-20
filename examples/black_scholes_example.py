"""Example script for running the Black-Scholes pricing function."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from Methods.black_scholes import BS


def main():
    stock_price = 100
    strike_price = 100
    risk_free_rate = 0.05
    dividend_yield = 0.0
    volatility = 0.2
    time_to_maturity = 1

    call_price, put_price = BS(
        stock_price,
        strike_price,
        risk_free_rate,
        dividend_yield,
        volatility,
        time_to_maturity,
    )

    print(f"Call price: {call_price:.4f}")
    print(f"Put price: {put_price:.4f}")


if __name__ == "__main__":
    main()
