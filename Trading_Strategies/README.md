# Trading Strategies

This folder contains selected trading strategy notes from the Greek Letters, Hedging, and Trading chapter.

The strategy code is split by topic:

```text
Trading_Strategies/
  adr_arbitrage.py
  butterfly.py
  interval_trading.py
  payoffs.py
  straddle.py
  strangle.py
```

## Interval Trading

Interval trading is designed for volatile stocks expected to move inside a pre-specified range. The idea is to buy more shares when price falls and sell shares when price rises.

The strategy relies more on a volatility or range view than on a directional return forecast. If the stock price breaks out of the interval, the strategy pauses until the price moves back into the range.

Example position rule:

| Stock price | Holding shares |
| ---: | ---: |
| 70 | 0 |
| 65 | 25 |
| 60 | 50 |
| 55 | 75 |
| 50 | 100 |
| 45 | 125 |
| 40 | 150 |
| 35 | 175 |
| 30 | 200 |

Code:

```python
from Trading_Strategies.interval_trading import interval_trade_plan

prices = [70, 65, 60, 55, 50]
plan = interval_trade_plan(prices)
```

## Butterfly

A butterfly is used when the trader expects the stock price to stay near a middle strike. A call butterfly buys one low-strike call, sells two middle-strike calls, and buys one high-strike call.

Using calls:

- Buy one call with lower strike $K_1$.
- Sell two calls with middle strike $K_2$.
- Buy one call with higher strike $K_3$.
- $K_2$ is usually the midpoint between $K_1$ and $K_3$.

The same structure can also be built with puts.

The strategy has limited downside and limited upside. It performs best when the terminal stock price is close to $K_2$. If the net payoff is positive after transaction costs for every possible terminal stock price, it becomes an arbitrage opportunity.

An asymmetric butterfly changes the number of options when strikes are not equally spaced. For example, with $K_1=5800$, $K_2=6000$, and $K_3=6100$:

- Buy one call at $K_1=5800$.
- Sell three calls at $K_2=6000$.
- Buy two calls at $K_3=6100$.

Code:

```python
import numpy as np
from Trading_Strategies.butterfly import call_butterfly_profit

stock_prices = np.array([80, 90, 100, 110, 120])
profit = call_butterfly_profit(
    stock_prices,
    lower_strike=90,
    middle_strike=100,
    upper_strike=110,
    lower_call_premium=12,
    middle_call_premium=6,
    upper_call_premium=2,
)
```

## Straddle

A straddle buys or sells a call and a put with the same strike and maturity. Long straddles benefit from large movement; short straddles benefit from calm prices.

Long straddle:

- Buy one call and one put with the same strike $K$ and maturity $T$.
- Usually choose $K$ close to the current stock price.
- Profits when the stock price moves far enough away from $K$ in either direction.
- The main cost is the total premium paid for both options.

Short straddle:

- Sell one call and one put with the same strike $K$ and maturity $T$.
- Profits when the stock price stays close to $K$.
- The risk is large if the stock price moves strongly in either direction.

Code:

```python
from Trading_Strategies.straddle import long_straddle_profit, short_straddle_profit

long_profit = long_straddle_profit(120, strike=100, call_premium=8, put_premium=6)
short_profit = short_straddle_profit(120, strike=100, call_premium=8, put_premium=6)
```

## Strangle

A strangle uses a call and a put with different strikes but the same maturity. It is usually cheaper than a straddle but needs a larger move to profit when long.

Long strangle:

- Buy one put at $K_1$ and one call at $K_2$.
- Profits when the stock price moves significantly outside the two strikes.
- Compared with a long straddle, it is usually cheaper but needs a larger price move.

Short strangle:

- Sell one put at $K_1$ and one call at $K_2$.
- Profits when the stock price remains roughly inside $[K_1,K_2]$.
- It is often used to bet that the maximum price movement will not exceed the strike range.

Code:

```python
from Trading_Strategies.strangle import long_strangle_profit, short_strangle_profit

long_profit = long_strangle_profit(
    120,
    put_strike=90,
    call_strike=110,
    put_premium=4,
    call_premium=5,
)
short_profit = short_strangle_profit(
    120,
    put_strike=90,
    call_strike=110,
    put_premium=4,
    call_premium=5,
)
```

## ADR and Local Share Arbitrage

The PDF also discusses arbitrage between an ADR and its local stock share, using TSMC as the example.

Suppose:

- One ADR can be exchanged for 5 local shares.
- One ADR price is US$8.
- One local share price is NT$40.
- Exchange rate is US$1 = NT$30.

Then:

$$
\text{ADR value in NTD} = 8 \times 30 = 240
$$

$$
\text{Local share package value} = 5 \times 40 = 200
$$

$$
\text{Premium ratio} = \frac{240-200}{200}=20\%
$$

The trading logic is mean reversion of the premium ratio:

- If the premium ratio is high, the ADR is relatively expensive. Buy local shares and short ADR.
- If the premium ratio is low, the ADR is relatively cheap. Short local shares and buy ADR.
- Close the position when the premium ratio returns to its long-term average.

The main risk is that the estimated long-term average premium ratio may be wrong. The band also involves a tradeoff: if it is too wide, trades occur too rarely; if it is too narrow, transaction costs may consume the profit.

Code:

```python
from Trading_Strategies.adr_arbitrage import adr_premium_ratio, adr_signal

premium = adr_premium_ratio(
    adr_price_usd=8,
    local_share_price=40,
    shares_per_adr=5,
    exchange_rate=30,
)

signal = adr_signal(
    premium_ratio=premium,
    long_term_average=0.20,
    upper_bound=0.25,
    lower_bound=0.15,
)
```
