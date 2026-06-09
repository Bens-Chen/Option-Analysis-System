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

## Monte Carlo

`monte_carlo.py` implements Monte Carlo pricing for European call and put options.

Monte Carlo does not produce an exact value. It estimates the option value and gives a sampling-error view. It is especially useful when closed-form formulas are difficult or unavailable.

Common variance reduction ideas include:

- moment matching
- antithetic variates
- control variates
- empirical martingale simulation

## Finite Difference

`finite_difference.py` solves option-pricing PDEs by discretizing time and stock price.

The main styles are:

- Explicit method: easier to understand but can require very small time steps for stability
- Implicit method: usually more stable

Finite difference methods are useful when the option value is better described as a PDE grid than as a closed-form formula or tree.
