# Option Pricing 

This repository is an option-pricing project. It introduces classic pricing methods, calibration tools, exotic option examples, Greek-letter estimation, hedging ideas, and selected trading strategies with Python implementations(including backtest).

## Features

- Methods: Black-Scholes, CRR, Monte Carlo and Finite Difference
- Greek Letters estimation
- Implied volatility calibration
- Exotic option : Asian, Lookback, and Rainbow options
- Option Trading Strateies 
- Market Data: yfinance connection for price history, option chains, IV, and contract search
- Interactive Option System 

## Installation

```bash
git clone git@github.com:Bens-Chen/Option-Pricing.git
cd Option-Pricing
pip install -r requirements.txt
```

## Quick Start

Run the pricing examples:

```bash
python examples/black_scholes_example.py
python examples/crr_example.py
python examples/monte_carlo_example.py
python examples/yfinance_black_scholes_example.py
```

Run the interactive option analysis system:

```bash
streamlit run Option_System/app.py
```

Run tests:

```bash
pytest
```

## Project Structure

```text
Implied_Volatility/
  README.md                  # implied volatility, IV smile, VIX, and SVIX notes
  constant_IV.py
  iv_smile.py
  VIX,SVIX

Exotic_Options/
  README.md                  # Asian, Lookback, and Rainbow option notes
  asian_option.py
  lookback_option.py
  rainbow_option.py

Greak_Letters/
  README.md                  # Greeks and hedging notes
  CRR                        # CRR Greek calculations
  Monte-Carlo                # pathwise and likelihood Monte Carlo Greeks

Market_Data/
  README.md                  # yfinance data connection notes
  yfinance_data.py

Option_System/
  README.md                  # interactive option search and strategy system
  analytics.py
  strategy_engine.py
  app.py

Trading_Strategies/
  README.md                  # interval, butterfly, straddle, strangle
  butterfly.py
  interval_trading.py
  payoffs.py
  straddle.py
  strangle.py

Methods/
  README.md                  # core pricing method notes
  black_scholes.py
  crr.py
  finite_difference.py
  monte_carlo.py

examples/
  black_scholes_example.py
  crr_example.py
  monte_carlo_example.py
  yfinance_black_scholes_example.py

tests/
  test_black_scholes.py
  test_crr.py
  test_option_system.py
  test_yfinance_data.py
```

## Reading Order

1. Start with `Methods/README.md` to understand the pricing methods.
2. Read `Market_Data/README.md` to see how real market data is pulled from yfinance.
3. Read `Implied_Volatility/README.md` for implied volatility, IV smile, VIX, and SVIX.
4. Read `Greak_Letters/README.md` for Greeks and hedging.
5. Read `Trading_Strategies/README.md` for selected trading strategies.
6. Read `Option_System/README.md` for the interactive option-search system.
7. Check `examples/` and `tests/` to see how the code is used.

## Disclaimer

This project is for educational purposes only. It is not financial advice and should not be used as a production trading system.
