# Option Analysis System

This folder contains the interactive system for searching option contracts, viewing IV and Greek letters, plotting strategy payoff, and running a simple historical scenario backtest.

Run it with:

```bash
streamlit run Option_System/app.py
```

## What the System Does

1. Search a ticker through `yfinance`.
2. Load available expiration dates and option chains.
3. Let the user select a call or put contract.
4. Show the contract IV and Black-Scholes Greek letters.
5. Optionally show American-style CRR Greek estimates.
6. Plot the selected strategy payoff.
7. Rank common strategies with a simple educational score.
8. Let the user enter custom option legs.
9. Run a latest-5-year historical scenario backtest using past underlying returns.

## Important Limitation

The backtest is a scenario backtest, not a full historical option-chain backtest.

It uses historical stock returns and applies those moves to the current option strategy. This is useful for learning payoff behavior, but it does not reconstruct old option chains, bid/ask spreads, or historical IV surfaces.

The displayed metrics include average PnL, total PnL, win rate, Sharpe ratio, MDD, estimated margin, return on margin, worst scenario, and best scenario. The margin estimate is based on the strategy payoff grid, so uncovered short-option risk is only approximated inside the plotted scenario range.

## Strategy Scoring

The strategy score is intentionally simple:

- If current IV is much higher than historical volatility, short-premium strategies receive a higher educational score.
- If current IV is much lower than historical volatility, long-volatility strategies receive a higher educational score.
- If the stock is above or below moving averages, directional single-option ideas receive a small adjustment.

This is not financial advice. It is a learning tool for comparing option structures.

## yfinance Coverage

`yfinance` provides listed Yahoo Finance option chains for supported tickers. These are standard vanilla option contracts with fields such as strike, bid, ask, volume, open interest, and implied volatility.

It does not provide exotic option chains such as Asian, Lookback, or Rainbow options. Those instruments are modeled separately in `Exotic_Options/`.

For American-style behavior, this app can estimate Greeks with the CRR binomial model. Yahoo Finance data itself does not reliably expose a clean `American` or `European` style flag for every contract.
