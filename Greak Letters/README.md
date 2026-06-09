# Greek Letters, Hedging, and Trading

This folder contains notes and code for option Greeks, hedging, and selected trading strategies.

## Greek Letters

Greek letters measure how sensitive an option value is to each pricing input.

## Delta

$$
\Delta = \frac{\partial c}{\partial S_0}
$$

Delta measures the option value change for a small change in the underlying price.

- Calls: $0 \leq \Delta \leq 1$
- Puts: $-1 \leq \Delta \leq 0$
- Delta changes sharply near ATM when maturity is close

## Gamma

$$
\Gamma = \frac{\partial^2 c}{\partial S_0^2}
$$

Gamma measures how fast delta changes. Long vanilla calls and puts have positive gamma, and gamma is usually highest near ATM.

## Vega

$$
\nu = \frac{\partial c}{\partial \sigma}
$$

Vega measures sensitivity to volatility. In Black-Scholes, calls and puts have the same positive vega.

## Rho

$$
\rho = \frac{\partial c}{\partial r}
$$

Rho measures sensitivity to the risk-free rate. Calls usually have positive rho, while puts usually have negative rho.

## Theta

Theta is treated as time decay:

$$
\Theta = -\frac{\partial c}{\partial T}
$$

Theta is usually negative for long options because time value decays.

## Relationship among Delta, Gamma, and Theta

The Black-Scholes PDE implies:

$$
\Theta + (r-q)S\Delta + \frac{1}{2}\sigma^2S^2\Gamma = rf
$$

For a delta-neutral portfolio:

$$
\Theta + \frac{1}{2}\sigma^2S^2\Gamma = rf
$$

High gamma is attractive, but it usually comes with faster time decay.

## CRR Greeks

`CRR` estimates Delta, Gamma, and Theta from CRR tree nodes.

It supports:

- European options
- American options through early exercise in the tree
- one-tree Greek estimation
- Pelsser and Vorst extended-tree style estimation

## Monte Carlo Greeks

`Monte-Carlo` implements:

- pathwise method
- likelihood ratio method

These methods estimate Greeks from simulated terminal prices. The current implementation is for European options.

## Dynamic Delta Hedge

Dynamic delta hedging replicates an option by continuously adjusting the stock position:

$$
C_t = \Delta_t S_t - B_t
$$

For a call option issuer, the hedge buys more shares when delta rises and sells shares when delta falls. With continuous rebalancing, constant volatility, and no transaction costs, the hedging cost approaches the Black-Scholes price. In practice, option issuers charge a markup because these assumptions do not hold exactly.

## Trading Strategies

This folder also keeps selected strategy notes.

### Interval Trading

Interval trading is designed for volatile stocks expected to move inside a pre-specified range. The idea is to buy more shares when price falls and sell shares when price rises.

### Butterfly

A butterfly is used when the trader expects the stock price to stay near a middle strike. A call butterfly buys one low-strike call, sells two middle-strike calls, and buys one high-strike call.

### Straddle

A straddle buys or sells a call and a put with the same strike and maturity. Long straddles benefit from large movement; short straddles benefit from calm prices.

### Strangle

A strangle uses a call and a put with different strikes but the same maturity. It is usually cheaper than a straddle but needs a larger move to profit when long.
