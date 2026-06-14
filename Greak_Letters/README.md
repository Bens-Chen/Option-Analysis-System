# Greek Letters and Hedging

This folder contains notes and code for option Greeks (BS greek excluded) and hedging.

## Greek Letters

Greek letters measure how sensitive an option value is to each pricing input.

## Delta

$$
\Delta = \frac{\partial c}{\partial S_0}
$$

Delta measures the option value change for a small change in the underlying price.

- Calls: $\Delta = e^{-qT}N(d_1)$, so $0 \leq \Delta \leq 1$.
- Puts: $\Delta = e^{-qT}[N(d_1)-1]$, so $-1 \leq \Delta \leq 0$.
- Near maturity, call delta is close to 1 when ITM and close to 0 when OTM.
- Near maturity, put delta is close to -1 when ITM and close to 0 when OTM.
- Delta changes sharply near ATM when maturity is close.

The first step of the call delta derivation is:

$$
\frac{\partial d_1}{\partial S_0}=\frac{\partial d_2}{\partial S_0}=\frac{1}{S_0\sigma\sqrt{T}}
$$

## Gamma

$$
\Gamma = \frac{\partial^2 c}{\partial S_0^2}
$$

Gamma measures how fast delta changes. Long vanilla calls and puts have positive gamma, and gamma is usually highest near ATM.

- Calls and puts have the same gamma in Black-Scholes.
- Gamma is always positive for long vanilla calls and puts.
- The gamma curve is similar to a probability density function because $\phi(d_1)$ appears in the formula.
- When time to maturity is short, gamma becomes more peaked around ATM because delta changes almost discontinuously near maturity.

## Vega

$$
\nu = \frac{\partial c}{\partial \sigma}
$$

Vega measures sensitivity to volatility. In Black-Scholes, calls and puts have the same positive vega.

- Higher volatility increases option value because the chance of favorable outcomes increases.
- Vega is usually largest around ATM.
- Vega becomes smaller near maturity because volatility has less time to affect the terminal stock price.
- Vega and gamma have similar density-function-shaped curves.

## Rho

$$
\rho = \frac{\partial c}{\partial r}
$$

Rho measures sensitivity to the risk-free rate. Calls usually have positive rho, while puts usually have negative rho.

- For calls, rho is usually positive because a higher $r$ increases the risk-neutral growth effect and lowers the present value of the strike.
- For puts, rho is usually negative because a higher $r$ lowers the present value of the put payoff.

## Theta

Theta is treated as time decay:

$$
\Theta = -\frac{\partial c}{\partial T}
$$

Theta is usually negative for long options because time value decays.

- American calls and puts have negative theta in the PDF's discussion.
- European puts are not always negative because interest rates and dividends can offset time decay.
- ATM options usually have the most negative theta because their time value decays fastest.

## Relationship among Delta, Gamma, and Theta

The Black-Scholes PDE implies:

$$
\Theta + (r-q)S\Delta + \frac{1}{2}\sigma^2S^2\Gamma = rf
$$

For a delta-neutral portfolio $\Delta$ = 0 :

$$
\Theta + \frac{1}{2}\sigma^2S^2\Gamma = rf
$$

High gamma is attractive, but it usually comes with faster time decay.



## CRR Greeks

`CRR` estimates Delta, Gamma, and Theta from CRR tree nodes.


Here introduce two CRR methods:

- one-tree Greek estimation
- Pelsser and Vorst extended-tree style estimation

The CRR one-tree method can estimate only:

- $\Delta$
- $\Gamma$
- $\Theta$

The estimates are taken from nearby tree nodes. This avoids pricing the whole option multiple times, but the estimates are not exactly today's Greeks unless the number of steps is large.

The Pelsser and Vorst extended tree improves the node layout for Greek estimation, but it is still mainly applicable to $\Delta$, $\Gamma$, and $\Theta$.


## Monte Carlo Greeks

`Monte-Carlo` implements:

- pathwise method
- likelihood ratio method

These methods estimate Greeks from simulated terminal prices. The current implementation is for European options.

Finite-difference Monte Carlo can use common random variables, but the simulation must be repeated. The pathwise and likelihood methods reduce repeated simulation cost.

### Pathwise Method

The pathwise method differentiates the simulated payoff path with respect to the input. It is intuitive because it follows how a parameter changes $S_T$ and therefore changes the payoff.

For vanilla payoffs, gamma is more delicate because the payoff is not twice differentiable at the strike. The implementation uses a common-random-number finite difference for gamma.

### Likelihood Method

The likelihood ratio method differentiates the probability density of $S_T$ instead of directly differentiating the payoff. It can estimate Greeks by multiplying the discounted payoff by a score function.

The current implementation supports European call and put Greeks:

- Delta
- Gamma
- Vega
- Rho
- Theta

## Dynamic Delta Hedge

Dynamic delta hedging replicates an option by continuously adjusting the stock position:

$$
C_t = \Delta_t S_t - B_t
$$

For a call option issuer, the hedge buys more shares when delta rises and sells shares when delta falls. With continuous rebalancing, constant volatility, and no transaction costs, the hedging cost approaches the Black-Scholes price. In practice, option issuers charge a markup because these assumptions do not hold exactly.

If a call option is underpriced, an inverted delta hedge can reverse the dynamic delta hedge logic. The idea is to buy the cheap call and trade the underlying in the opposite way to exploit the pricing gap.
