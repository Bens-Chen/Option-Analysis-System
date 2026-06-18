# Market Data

This folder connects the project to real market data through `yfinance`.

## Data Source

All live market data in this project comes from `yfinance`.

Useful fields include:

- stock price history
- available option expirations
- call and put option chains
- bid, ask, last price, volume, open interest, and implied volatility when Yahoo Finance provides them

## Quote Quality Filter

Option chains can contain stale or thin quotes. Before using option prices for IV smile, VIX, SVIX, or strategy analysis, `yfinance_data.py` can apply simple filters:

- remove rows with invalid strike or price
- calculate mid price from bid/ask when both are available
- calculate bid/ask spread as a percentage of mid price
- optionally require bid/ask quotes
- optionally require minimum volume or open interest

The filter is intentionally simple. It does not claim a quote is tradable; it only removes obvious bad inputs before the pricing models use them.

## Historical Option Chain Limitation

`yfinance` does not provide a complete historical option-chain database for this project. Because of that, the option-system backtest does not reconstruct old option chains or old IV surfaces.

The backtest replays the current relative option structure through historical underlying prices. This is useful for learning payoff behavior, but it should not be read as a production-grade historical option backtest.
