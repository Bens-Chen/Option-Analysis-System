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

More explicitly:

- $E(\ln(S_T/S_0))$: geometric mean of daily log returns. Under a lognormal model, it is connected to $\mu - 0.5\sigma^2$.
- $\ln(E[S_T/S_0])$: arithmetic-return view. It is connected to $\mu$, but it is not the same object as the expected log return.

This distinction matters when estimating parameters for a lognormal stock-price process.

## Implied Volatility

Historical volatility is backward-looking. Option prices often imply a forward-looking volatility.

Implied volatility solves:

$$
f(\sigma_{imp}) = c(S_0,K,r,q,\sigma_{imp},T) - C_{market} = 0
$$

`implied_volatility.py` includes numerical methods such as:

- bisection method
- Newton method

### Bisection Method

First find an interval $[a_n,b_n]$ such that:

$$
f(a_n)f(b_n) < 0
$$

Then calculate:

$$
x_n = a_n + \frac{b_n-a_n}{2}
$$

If:

$$
f(a_n)f(x_n) < 0
$$

then set:

$$
a_{n+1}=a_n,\quad b_{n+1}=x_n
$$

Otherwise set:

$$
a_{n+1}=x_n,\quad b_{n+1}=b_n
$$

### Newton Method

Newton's method uses a first-order Taylor approximation:

$$
x_{n+1} = x_n - \frac{f(x_n)}{f'(x_n)}
$$

It is often faster than bisection, but it can be less stable if the initial guess is poor or the derivative is small.

## Volatility Smile

Black-Scholes assumes constant volatility, but market implied volatility often changes across strikes and maturities. This creates volatility smiles or smirks.

Possible models for richer volatility dynamics include stochastic volatility, GARCH-family models, HAR-style realized volatility models, and jump extensions.

Examples of volatility models that can be used to forecast or describe implied volatility include:

- SV
- SVJ
- SVJJ
- GARCH
- GJR-GARCH
- GARCH-MIDAS
- HAR-RV-CJ

## Stochastic Volatility

Stochastic volatility models relax the Black-Scholes assumption that volatility is constant. Instead, volatility is treated as another state variable that can move over time.
