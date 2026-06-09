# Exotic Options

This folder contains examples of options whose payoff depends on more than a simple terminal stock price.

## Rainbow Option

`rainbow_option.py` prices an option on multiple underlying assets.

A rainbow call payoff can be written as:

$$
\max(\max(S_1, S_2, \ldots) - K, 0)
$$

Because multiple assets may be correlated, the implementation uses Cholesky decomposition to generate correlated simulations.

## Lookback Option

`lookback_option.py` studies path-dependent payoffs that depend on the maximum or minimum stock price during the option life.

For example, a lookback put payoff may be:

$$
\max(S_{\max,T} - S_T, 0)
$$

The key idea is that the payoff depends on the path history, not only the final price.

## Asian Option

`asian_option.py` studies options related to average prices.

Asian or average-style options can be useful when the risk exposure is connected to an average price rather than one terminal price. Their volatility is usually lower than the underlying asset volatility, so they can be cheaper than comparable vanilla options.

The main implementation challenge is tracking or approximating average-price states.
