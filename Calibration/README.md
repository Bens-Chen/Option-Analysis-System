# Estimation and Calibration

This folder contains volatility estimation and implied volatility calibration notes.

## Mean Estimation

Two return averages are often confused:

- Geometric log return: estimates the lognormal drift adjustment
- Arithmetic return: estimates the simple average growth rate

When assuming a lognormal stock-price model, this distinction matters because:

$$
E[\ln(S_T/S_0)]
$$

and

$$
\ln(E[S_T/S_0])
$$

are not the same quantity.

## Implied Volatility

Historical volatility is backward-looking. Option prices often imply a forward-looking volatility.

Implied volatility solves:

$$
f(\sigma_{imp}) = c(S_0,K,r,q,\sigma_{imp},T) - C_{market} = 0
$$

`implied_volatility.py` includes numerical methods such as:

- bisection method
- Newton method

## Volatility Smile

Black-Scholes assumes constant volatility, but market implied volatility often changes across strikes and maturities. This creates volatility smiles or smirks.

Possible models for richer volatility dynamics include stochastic volatility, GARCH-family models, HAR-style realized volatility models, and jump extensions.
