# Option Analysis System

This folder contains the interactive system for searching option contracts, viewing IV and Greek letters, plotting strategy payoff, and running a simple historical scenario backtest.

Run it with:

```bash
streamlit run Option_System/app.py
```

## What the App Does

1. Search a ticker through `yfinance`.
2. Load available expiration dates and option chains.
3. Let the user select a call or put contract.
4. Show the contract IV and Black-Scholes Greek letters.
5. Plot the selected strategy payoff.
6. Rank common strategies with a simple educational score.
7. Let the user enter custom option legs.
8. Run a historical scenario backtest using past underlying returns.

## Important Limitation

The backtest is a scenario backtest, not a full historical option-chain backtest.

It uses historical stock returns and applies those moves to the current option strategy. This is useful for learning payoff behavior, but it does not reconstruct old option chains, bid/ask spreads, or historical IV surfaces.

## Strategy Scoring

The strategy score is intentionally simple:

- If current IV is much higher than historical volatility, short-premium strategies receive a higher educational score.
- If current IV is much lower than historical volatility, long-volatility strategies receive a higher educational score.
- If the stock is above or below moving averages, directional single-option ideas receive a small adjustment.

This is not financial advice. It is a learning tool for comparing option structures.
