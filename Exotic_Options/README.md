# Exotic Options

This folder contains examples of options whose payoff depends on more than a simple terminal stock price.

## Rainbow Option

`rainbow_option.py` prices an option on multiple underlying assets.

A rainbow call payoff can be written as:

$$
\max(\max(S_1, S_2, \ldots) - K, 0)
$$

Because multiple assets may be correlated, the implementation uses Cholesky decomposition to generate correlated simulations.

Python provides Cholesky decomposition through `numpy.linalg.cholesky()`, but this project keeps the algorithmic idea visible because correlation handling is an important part of multi-asset option pricing.

## Lookback Option

`lookback_option.py` studies path-dependent payoffs that depend on the maximum or minimum stock price during the option life.

For example, a lookback put payoff may be:

$$
\max(S_{\max,\tau} - S_{\tau}, 0)
$$

The key idea is that the payoff depends on the path history, not only the final price.

Here $S_{\max,\tau}$ is the maximum value of $S_u$ for:

$$
u = 0, \Delta t, 2\Delta t, \ldots
$$

Note that $S_{\max}$ is the maximum value of the stock path from 0 to the pricing date $t$. Since $t$ is the pricing date, the implementation still needs to evaluate the future maximum from $t$ to maturity $T$.

This repo includes both CRR-style and Monte Carlo-style ideas for Lookback options.

## Asian Option

`asian_option.py` studies options related to average prices.

Asian or average-style options can be useful when the risk exposure is connected to an average price rather than one terminal price. Their volatility is usually lower than the underlying asset volatility, so they can be cheaper than comparable vanilla options.

The main implementation challenge is tracking or approximating average-price states.

Asian options are useful for investors or hedgers who are exposed to average price risk. They can also be useful in thinly traded markets because using an average price can reduce the effect of price manipulation near one specific terminal date.

A related product is an Average option. For a call-style payoff:

- Average option payoff:

$$
\max(S_{\mathrm{ave},T} - K, 0)
$$

- Asian-style payoff:

$$
\max(S_T - S_{\mathrm{ave},t}, 0)
$$

For simplicity, this project focuses on Average option logic. The difficult part is deriving or approximating each average-price node $A$. Since a previous average value may not appear exactly in the next tree layer, interpolation can be needed.

## Barier Option

`barrier_option.py` prices simple knock-in and knock-out options by Monte Carlo simulation.

A barrier option becomes active or inactive when the underlying asset touches a pre-specified barrier level.

Common types:

- Down-and-out: option expires worthless if the path falls to or below the barrier.
- Up-and-out: option expires worthless if the path rises to or above the barrier.
- Down-and-in: option becomes active only if the path falls to or below the barrier.
- Up-and-in: option becomes active only if the path rises to or above the barrier.

## Binary Option

`binary_option.py` implements Black-Scholes closed-form prices for binary
options.

A cash-or-nothing binary option pays a fixed cash amount if the option finishes
in the money:

$$
\text{Call payoff} = Q \cdot 1_{\{S_T > K\}}
$$

$$
\text{Put payoff} = Q \cdot 1_{\{S_T < K\}}
$$


An asset-or-nothing binary option pays the asset itself if the option finishes
in the money:

The binary formulas are useful for understanding digital payoffs and also for
checking vanilla option decomposition:

$$
C = \text{asset-or-nothing call} - K \times \text{cash-or-nothing call paying 1}
$$
