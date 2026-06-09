# Pricing Methods

This folder contains the core pricing engines used by the project.

## Black-Scholes

`black_scholes.py` implements closed-form European call and put prices with dividend yield.

The Black-Scholes prices are:

$$
C = S e^{-qT} N(d_1) - K e^{-rT} N(d_2)
$$

$$
P = K e^{-rT} N(-d_2) - S e^{-qT} N(-d_1)
$$

where:

$$
d_1 = \frac{\ln(S/K) + (r - q + 0.5\sigma^2)T}{\sigma\sqrt{T}}
$$

$$
d_2 = d_1 - \sigma\sqrt{T}
$$

Black-Scholes is the cleanest starting point because it gives a closed-form benchmark for European vanilla options.

It is the most typical closed-form pricing model. If an option payoff is not the same as a vanilla call or put, the pricing formula may still be derived by martingale pricing instead of directly solving a PDE.

Martingale pricing is another way to derive Black-Scholes-style formulas. The hard part is changing from the real-world probability measure to the risk-neutral measure. Under risk-neutral valuation, the pricing measure treats discounted asset prices as martingales, so European option values can be derived from discounted expected payoff.

## CRR Binomial Tree

`crr.py` implements CRR binomial tree pricing.

CRR is useful because it can handle:

- European options
- American options with early exercise
- some exotic options when the tree state is extended

The folder includes:

- `CRR_O_n2`: a full two-dimensional tree implementation
- `CRR_O_n`: a memory-efficient one-dimensional implementation
- `Combinatorial_european_price`: a European-only combinatorial version
- `CRR_BS`: a hybrid binomial Black-Scholes method

The project keeps two basic CRR implementations with different memory usage:

- $O(n^2)$ tree storage
- $O(n)$ rolling array storage

CRR is one of the most versatile methods in this repo. It can price European and American options, and it can be adapted to some exotic options such as Asian or Lookback options. The pricing logic is similar across products, but the state variables and code structure can become different when the payoff is path dependent.

Related CRR-style ideas:

- Combinatorial method: useful for European options
- Binomial Black-Scholes: apply the Black-Scholes formula near the last step to reduce convergence time

## Monte Carlo

`monte_carlo.py` implements Monte Carlo pricing for European call and put options.

Monte Carlo does not produce an exact value. It estimates the option value and gives a sampling-error view. It is especially useful when closed-form formulas are difficult or unavailable.

Common variance reduction ideas include:

- moment matching
- antithetic variates
- control variates
- empirical martingale simulation

### Moment Matching

Moment matching adjusts the simulated standard normal samples so that the sample mean is close to 0 and the sample variance is close to 1.

### Antithetic Variates

The idea is to sample half of the random shocks first, then use their negatives as the other half. This helps stabilize the sample mean around 0.

### Control Variates

Control variates use a related random variable with a known true mean to reduce variance. A common setup is:

$$
W = X + \beta(Y - \mu)
$$

where $Y$ has known mean $\mu$.

The variance is:

$$
\mathrm{Var}(W) = \mathrm{Var}(X) + 2\beta\mathrm{Cov}(X,Y) + \beta^2\mathrm{Var}(Y)
$$

The goal is to choose $Y$ and $\beta$ so that the additional terms reduce total variance. The difficulty is finding a relevant $Y$ with a known true mean and estimating a stable $\beta$.

### Empirical Martingale Simulation

Empirical Martingale Simulation adjusts simulated paths so that the simulated price process better respects the martingale condition. It can be useful for path-dependent option pricing.

## Finite Difference

`finite_difference.py` solves option-pricing PDEs by discretizing time and stock price.

The main styles are:

- Explicit method: easier to understand but can require very small time steps for stability
- Implicit method: usually more stable

Finite difference methods are useful when the option value is better described as a PDE grid than as a closed-form formula or tree.

The grid notation $F_{i,j}$ means the option price at time step $i$ and stock-price node $j$.

- Implicit method: node $F_{i+1,j}$ is derived from $F_{i,j+1}$, $F_{i,j}$, and $F_{i,j-1}$.
- Explicit method: node $F_{i,j}$ is derived from $F_{i+1,j+1}$, $F_{i+1,j}$, and $F_{i+1,j-1}$.

The implicit method is generally more robust because the explicit method can require an extremely small $\Delta t$ to converge.
