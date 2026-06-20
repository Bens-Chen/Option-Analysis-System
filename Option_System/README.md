# Option Analysis System

This folder contains the interactive system for searching option contracts, viewing IV and Greek letters, plotting strategy payoff, and running a model rolling strategy backtest.

Run it with:

```bash
streamlit run Option_System/app.py
```

## What the System Does

1. Search a ticker through `yfinance`.
2. Load available expiration dates and option chains.
3. Apply simple quote-quality filters to the yfinance option chain.
4. Let the user select a call or put contract.
5. Show the contract IV and Black-Scholes Greek letters.
6. Optionally show American-style CRR Greek estimates.
7. Plot the selected strategy payoff.
8. Let the user enter custom option legs.
9. Run a latest-10-year model rolling backtest using yfinance underlying prices and a rolling Newey-West volatility proxy.
10. Build research tables for volatility surface, model mispricing, robustness, tear sheet metrics, event analysis, and paper alerts.

## Research Platform Features

The app now includes a first research-platform layer:

- Volatility surface table: current yfinance IV by expiration and moneyness bucket.
- Surface summary: ATM IV, 90%-110% skew, term-structure slope, and an IV-rank proxy.
- Mispricing scanner: compares yfinance mid price with the project Black-Scholes model price.
- Strategy robustness grid: tests the selected strategy across expirations and moneyness levels.
- Portfolio tear sheet: VaR, CVaR, volatility, best/worst trade, and monthly PnL.
- Event straddle analysis: ATM straddle implied move from the current option chain.
- Paper alerts: rule-based alerts for high IV-rank proxy, steep skew, and large model mispricing.

These features are intentionally table-first. The goal is to make each calculation easy to inspect before adding more visual design.

## Important Limitation

The backtest is a model rolling backtest, not a true historical option-chain backtest.

Each entry date rebuilds the selected strategy by the same strike/spot ratios as the live strategy. It estimates entry and exit option values with Black-Scholes and a rolling Newey-West volatility proxy from yfinance underlying prices. This is more realistic than applying today's contract directly to old prices, but it still does not reconstruct old option chains, historical bid/ask spreads, or historical IV surfaces.

The displayed metrics include average PnL, total PnL, win rate, Sharpe ratio, MDD, estimated margin, return on margin, VaR, and Expected Shortfall. The margin estimate is still approximate, especially for uncovered short-option risk.

The IV-rank value in the app is also a proxy. True IV rank requires historical implied volatility observations. Since yfinance does not provide a complete historical option-chain database here, the app ranks current ATM IV against the current surface range instead.

## Quote Quality Controls

The sidebar includes simple controls for maximum bid/ask spread, minimum open interest, minimum volume, and whether bid/ask quotes are required.

These controls are deliberately lightweight because yfinance coverage varies by ticker. If the filter removes all calls or puts, the app falls back to the raw yfinance rows and shows a warning.


## yfinance Coverage

`yfinance` provides listed Yahoo Finance option chains for supported tickers. These are standard vanilla option contracts with fields such as strike, bid, ask, volume, open interest, and implied volatility.

It does not provide exotic option chains such as Asian, Lookback, or Rainbow options. Those instruments are modeled separately in `Exotic_Options/`.

For American-style behavior, this app can estimate Greeks with the CRR binomial model. Yahoo Finance data itself does not reliably expose a clean `American` or `European` style flag for every contract.
