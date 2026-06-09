# Trading Strategies

This folder contains selected trading strategy notes from the Greek Letters, Hedging, and Trading chapter.


## Interval Trading

Interval trading is designed for volatile stocks expected to move inside a pre-specified range. The idea is to buy more shares when price falls and sell shares when price rises.

The strategy relies more on a volatility or range view than on a directional return forecast. If the stock price breaks out of the interval, the strategy pauses until the price moves back into the range.



## Butterfly

A butterfly is used when the trader expects the stock price to stay near a middle strike. A call butterfly buys one low-strike call, sells two middle-strike calls, and buys one high-strike call.

Using calls:

- Buy one call with lower strike $K_1$.
- Sell two calls with middle strike $K_2$.
- Buy one call with higher strike $K_3$.
- $K_2$ is usually the midpoint between $K_1$ and $K_3$.

The same structure can also be built with puts.

The strategy has limited downside and limited upside. It performs best when the terminal stock price is close to $K_2$. If the net payoff is positive after transaction costs for every possible terminal stock price, it becomes an arbitrage opportunity.


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




