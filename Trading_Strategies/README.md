# Trading Strategies

This folder contains selected trading strategy notes from the Greek Letters, Hedging, and Trading chapter.

## Spread(Bull, Bear, Ratio)

`spread.py` implements common spread payoff diagrams.

A spread combines options with different strikes. The goal is usually to trade
a directional view with capped risk, or to express a relative-volatility view
with less premium than buying a single option.

### Bull  Spread

A bull spread is used when the trader expects a moderate price increase.
Example: bull call spread

- Buy one call with lower strike $K_1$.
- Sell one call with higher strike $K_2$.
- The initial premium is reduced by selling the higher-strike call.
- Maximum profit is capped when the stock price is above $K_2$.
- Maximum loss is the net premium paid.


### Bear Spread

A bear spread is used when the trader expects a moderate price decrease.
Example: bear put spread

- Buy one put with higher strike $K_2$.
- Sell one put with lower strike $K_1$.
- Maximum profit is capped when the stock price is below $K_1$.
- Maximum loss is the net premium paid.


### Ratio Call Spread

A ratio call spread buys fewer low-strike calls and sells more high-strike calls.
The common version buys one call and sells two higher-strike calls.

This can create a low-cost or credit structure, but it has large upside risk
because the extra short call is uncovered after the upper strike.


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

## Iron Condor

The common short iron condor is a range-bound income strategy:

- Buy one far OTM put at $K_1$.
- Sell one put at $K_2$.
- Sell one call at $K_3$.
- Buy one far OTM call at $K_4$.
- The strikes satisfy $K_1 < K_2 < K_3 < K_4$.

The strategy receives net premium at initiation. It performs best when the
terminal stock price stays between the two short strikes $K_2$ and $K_3$.
Risk is limited because the far put and far call cap the tail losses.




