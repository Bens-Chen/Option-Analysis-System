# Option Analysis System

This repository is an option related project. It introduces classic pricing methods, calibration tools, exotic option examples, Greek-letter estimation, hedging ideas, selected trading strategies, risk-management tools, and Python backtests.

## Features

- Methods: Black-Scholes, CRR, Monte Carlo and Finite Difference
- Greek Letters estimation
- Implied volatility calibration(IV smile and surface)
- Exotic option : Binary,Barrier, Asian, Lookback, and Rainbow options
- Option Trading Strategies
- Market Data: yfinance connection for price history, option chains, IV, and contract search
- Interactive Option System 
- Risk Management: scenario risk matrix, VaR/Expected Shortfall, volatility curve monitor, and volatility tracker

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

The Streamlit app includes contract quotes, Greek letters, strategy backtests, and risk-management views.

Run tests:

```bash
pytest
```

## Project Structure

```text
Exotic_Options/
  README.md                  # exotic option notes
  asian_option.py
  barrier_option.py
  binary_option.py
  rainbow_option.py
  lookback_option.py

Greak_Letters/
  README.md                  # Greeks and hedging notes
  crr_greak
  monte_carlo_greek

Implied_Volatility/
  README.md                  # implied volatility, IV smile, VIX, and SVIX notes
  constant_IV.py
  iv_smile.py
  vix_svix

Market_Data/
  README.md                  # yfinance data connection notes
  yfinance_data.py

Methods/
  README.md                  # core pricing method notes
  black_scholes.py
  crr.py
  finite_difference.py
  monte_carlo.py

Option_System/
  README.md                  # interactive option search and strategy system
  api.py
  analytics.py
  app.py
  research.py
  strategy_engine.py

Risk_Management/
  README.md                  # risk metrics, volatility tracking, and visuals
  risk_matrix.py             
  risk_visuals.py            
  utils.py                   
  var_es.py                  
  vol_curve_monitor.py       
  vol_tracker.py            

Trading_Strategies/
  README.md                  # interval, butterfly, straddle, strangle, spreads...
  butterfly.py
  iron_condor.py
  interval_trading.py
  payoffs.py
  spread.py
  straddle.py
  strangle.py

examples/
  black_scholes_example.py
  crr_example.py
  monte_carlo_example.py
  yfinance_black_scholes_example.py

tests/
  test_black_scholes.py
  test_crr.py
  test_exotic_options.py
  test_iv_smile.py
  test_option_api.py
  test_option_system.py
  test_risk_management.py
  test_trading_strategies.py
  test_vix_svix.py
  test_yfinance_data.py
```

## Reading Order

1. Start with `Methods/README.md` to understand the pricing methods.
2. Read `Market_Data/README.md` to see how real market data is pulled from yfinance.
3. Read `Implied_Volatility/README.md` for implied volatility, IV smile, VIX, and SVIX.
4. Read `Greak_Letters/README.md` for Greeks and hedging.
5. Read `Trading_Strategies/README.md` for selected trading strategies.
6. Read `Risk_Management/README.md` for VaR/ES, scenario matrices, volatility curve monitoring, and volatility tracking.
7. Read `Option_System/README.md` for the interactive option-search, backtest, research, and risk dashboard.
8. Check `examples/` and `tests/` to see how the code is used.

## Disclaimer

This project is for educational purposes only. It is not financial advice and should not be used as a production trading system.
