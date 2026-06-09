# Market Data

This folder connects the project to real market data through `yfinance`.

The important design choice is separation:

- `Market_Data/` fetches and cleans market data.
- `Methods/` prices options from explicit inputs such as `S`, `K`, `r`, `q`, `sigma`, and `T`.
- `Option_System/` combines market data, pricing, Greeks, strategies, charts, and backtest-style analysis.

This keeps the pricing formulas testable. The Black-Scholes and CRR functions should not know where the data came from.

## Price History

```python
from Market_Data.yfinance_data import (
    download_price_history,
    latest_close,
    estimate_annualized_volatility,
)

history = download_price_history("AAPL", period="1y")
S = latest_close(history)
sigma = estimate_annualized_volatility(history)
```

## Option Chain

```python
from Market_Data.yfinance_data import fetch_option_chain

chain = fetch_option_chain("AAPL")
calls = chain["calls"]
puts = chain["puts"]
```

`calls` and `puts` include Yahoo Finance fields such as strike, bid, ask, last price, volume, open interest, and implied volatility.
