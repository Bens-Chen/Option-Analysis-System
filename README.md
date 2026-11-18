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

Clone or download this repository, then enter the project folder:

```bash
cd Option-Analysis-System-main
python -m pip install -r requirements.txt
```

## Quick Start

Run the pricing examples:

```bash
python -m examples.black_scholes_example
python -m examples.crr_example
python -m examples.monte_carlo_example
python -m examples.yfinance_black_scholes_example
```

Run the interactive web app (Option Lab):

```bash
python -m webapp
```

Then open `http://127.0.0.1:8000`. It covers the pricing calculator, US option chains, IV smile/surface,
strategy backtests, risk management, and Taiwan warrants (see "Option Lab web app" below).

Run tests:

```bash
python -m pytest
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
7. Read `Option_System/README.md` for the option-search, backtest, and research logic used by the web app.
8. Check `examples/` and `tests/` to see how the code is used.

## Disclaimer

This project is for educational purposes only. It is not financial advice and should not be used as a production trading system.

## optcore (production core)

The original folders above are the step-by-step learning implementations and are left unchanged.
`optcore/` re-implements the same maths in vectorised NumPy form for real systems
(whole option chains, thousands of Taiwan warrants):

```python
from optcore import bs_price, crr_price, bs_greeks, implied_vol, warrant_iv
from optcore.data import read_tej_terms, read_tej_daily, merge_daily_with_terms
```

- `bs_price`, `crr_price`, `bs_greeks`, `implied_vol` accept scalars or arrays, and handle `T <= 0`.
- `warrant_*` helpers scale by the exercise ratio (TEJ 目前行使比例).
- `optcore.data.tej` reads TEJ warrant terms / daily exports, maps Chinese headers,
  and merges terms point-in-time (no look-ahead after strike resets).
- `tests/test_optcore_*.py` cross-check every function against the learning versions.

Install for development: `pip install -e ".[app,dev]"`.

## Option Lab web app

A new web interface (FastAPI + plain HTML/JS, no Node build step) built on `optcore`:

- **定價計算器**: BS / CRR price, Greeks and price curves, with an exercise-ratio input for warrants
- **美股選擇權**: yfinance chain with our own mid-price IV next to yfinance's, with four sub-pages:
  - 報價與微笑: T-shaped chain, IV smile with SVI fit, VIX / SVIX
  - IV 曲面: 3-D surface across expirations
  - 策略回測: 14 preset strategies + custom legs, payoff, net Greeks, rolling backtest and metrics
  - 風險管理: price-shock risk matrix, historical / EWMA / IV-smoothed VaR and ES, vol-curve curvature monitor
- **台股權證**: upload TEJ daily (+ optional terms) exports; own IV vs TEJ IV, IV by issuer, per-warrant history

```bash
python -m webapp          # then open http://127.0.0.1:8000
```

The old Streamlit app (`Option_System/app.py`) was replaced by this web app; its analysis modules are reused unchanged.

## SinoPac Shioaji downloader

`optcore/data/shioaji_source.py` downloads Taiwan warrant data and caches it as parquet:

- warrant contracts for one underlying (Shioaji has no strike / ratio / expiry: use TEJ terms for those)
- 1-minute K bars for the underlying and every warrant on it (cheap)
- historical ticks with best bid / ask for the most active warrants (expensive: about 0.6 MB per warrant-day
  against a 500 MB daily quota)

```bash
pip install "shioaji==1.5.9"
python -m optcore.data.shioaji_source --underlying 2330 --out ../data/shioaji --env-file /path/to/.env
```

Credentials come from `SJ_API_KEY` / `SJ_SEC_KEY` (or the `--env-file`) and are never stored.
`--max-mb` caps one run's usage; re-running skips everything already on disk, so a run that stopped
at the cap continues where it left off.
