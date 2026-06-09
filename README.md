# Option Pricing

This repository contains introductions and Python implementations of option pricing methods.

At the end , I will present a  system which can quickly give user the accurate price interval or spot ,greek letters and simple strategy recommendation(including backtest result).

## Features

- Closed-form Black-Scholes pricing for European call and put options
- CRR binomial tree pricing for European and American options
- Monte Carlo pricing with confidence interval components
- Finite difference methods for option pricing PDEs
- Exotic option examples: Asian, Lookback, and Rainbow options
- Implied volatility calibration notes and code
- Greak letters introduction and caluculation
- Option trading strategies
- Option Trading System 

## Installation

Clone the repository and install the dependencies:

```bash
git clone https://github.com/Bens-Chen/Option-Pricing-.git
cd Option-Pricing-
pip install -r requirements.txt
```

## Quick Start

Run the Black-Scholes example:

```bash
python examples/black_scholes_example.py
```

Expected output:

```text
Call price: 10.4506
Put price: 5.5735
```

You can also run:

```bash
python examples/crr_example.py
python examples/monte_carlo_example.py
```

## Project Structure

```text
Calibration/
  implied_volatility.py
Exotic_Options/
  asian_option.py
  lookback_option.py
  rainbow_option.py
Methods/
  black_scholes.py
  crr.py
  finite_difference.py
  monte_carlo.py
examples/
  black_scholes_example.py
  crr_example.py
  monte_carlo_example.py
tests/
  test_black_scholes.py
  test_crr.py
```

## Tests

Run the test suite with:

```bash
pytest
```

## Disclaimer

This project is for educational purposes only and should not be used as financial advice or as a production trading system.

## Methods
### Black-Scholes

The Black-Scholes prices for a European call and put with dividend yield are:

$$
C = S e^{-qT} N(d_1) - K e^{-rT} N(d_2)
$$

$$
P = K e^{-rT} N(-d_2) - S e^{-qT} N(-d_1)
$$

where:

$$
d_1 = \frac{\ln(S/K) + (r - q + 0.5\sigma^{2})T}{\sigma\sqrt{T}}
$$

$$
d_2 = d_1 - \sigma\sqrt{T}
$$

$N(x)$ is the cumulative distribution function of the standard normal distribution.

The most tyipical one with closed form. If options' payoff aren't the same as vanilla call or put, we can still use a simple way (compared to derive from PDE)Martingale Pricing Method to get it's closed form.

Martingale Pricing Method is an alternative method to derive Black-Scholes like formulas.The most difficult part is how to change P measure to Q measure, however, due to RNVR, we know that P measure is equivalent to Q measure when pricing.Then by applying Girsanov Theorem and some calculations we can easily get the closed form of any European options.

### CRR 

One can seem to be the most versatile to price not only European,American , but also some other exotic options like: Asian,Lookback....Although the logic is similar, the code are different when pricing different option.

Here are two simple versions  with different dimension usage
- $n^{2}$
- $n$

And also here provide other methods similar to CRR or be combined with CRR.
- Combinatorial(only European)
- Binomial Black-Scholes: Apply BS formula on $n-1$ step, we can easily reduce the time to converge 

### Monte-Carlo

Different to the previous two methods,Monte-Carlo can't derice exact price, but can give users a confidence interval.This method is more like a method to validate or assure ur outcome is reasonable.

In addition, in order to get a more narrow interval ,we can use some variance reduction methods, such as moment matching, antithetic variate approach, control variates and Emperical Martingale Simulations(EMS).

Here's easy introduction of each variane reduction method.
#### Moment Matching: 

Matching the first two moments of the SND,mean equals to 0, variance equal to 1

#### Antithetic Variate Approach: 

Get mean equals to 0, the logic is to sample first half, then latter half will be the negaitve of first half.

#### Control Variates[Kemna and Vorst(1990)]:

 A more complicated method. It requires u to get a similar, relevent underlying asset or derivative.Over all, u need to asumme $W = X + \beta(Y - \mu)$, and find $Y$ which has mean equals to $\mu$, and

$$
\mathrm{Var}(W) = \mathrm{Var}(X) + 2\beta\mathrm{Cov}(X,Y) + \beta^{2}\mathrm{Var}(Y)
$$

where $2\beta\mathrm{Cov}(X,Y) + \beta^{2}\mathrm{Var}(Y) < 0$.
 
 The first difficulty is  find the true mean of $Y$ (not sample mean) and the second is decide $\beta$ because $\beta = \mathrm{Cov}(X,Y)/\mathrm{Var}(Y)$, but due to $X$ and $Y$ are both dependent on drawn samples, the estimators might be affected.

####  EMS[Duan and Siminato(1998)]: 

A method performs better than others when pricing path dependent options.The logic is to adjust price to conform to martingale.


### Finite Difference

This method is proposed to solve PDE.It has two way ,one is Implicit, the other is Explicit

Similar to CRR, we divide discretize time but also Stock price, $F_{i,j}$ means option price when time $i$ and stock price $j$, and if the grid is small enough, it is equivalent to derive closed form.

- Implicit: node $F_{i+1,j}$ derived from $F_{i,j+1}$, $F_{i,j}$, $F_{i,j-1}$ three nodes. 
- Explicit: node $F_{i,j}$ derived from $F_{i+1,j+1}$, $F_{i+1,j}$, $F_{i+1,j-1}$ three nodes.

The implicit method is more robust than explicit because explicit needs an extermely small $\Delta t$ for obtaining convergent results.





## Exotic Options
### Rainbow Option

Rainbow Call's payoff is $\max(\max(S_1,S_2,\ldots) - K, 0)$ and here we will use Monte-Carlo to price and the interesting part is because every asset might have some relationship to others,so we need to introduce Cholesky decompostion to erase their relation.

There is package of Cholesky decomposition in Python(numpy.linalg.cholesky()),but we will still provide the algorithm.

### LookBack Option

Lookback Option is one of path dependent options and Put's payoff is $\max(S_{\max,\tau} - S_{\tau}, 0)$, where $S_{\max,\tau}$ is the maximum value of $S_u$ for $u = 0, \Delta t, 2\Delta t, \ldots$.Here we apply CRR and Monte-Carlo.

Note: $S_{\max}$ is the maximum value of $S_u$ from $0$ to $t$. Since $t$ is our pricing date, we still need to calculate $S_{\max,\tau}$ from $t$ to $T$.

### Asian Option

Asian Option is also a path dependent option.Here are some features of this option:
- Serve as a hadging tool to who will be exposed to the risk of average prices.
- The volatility of Asian is lower than the underlying assets,so it is cheaper and more attractive to some investors.
- Useful in third-traded markets to prevent manipulation

And there is the other option which is similar to Asian:Average Option. Take call as example,Payoff of 

- Average: $\max(S_{\mathrm{ave},T} - K, 0)$

- Asian: $\max(S_T - S_{\mathrm{ave},t}, 0)$

For simplicity, the code will be Average Option

The hardest part is to derive every nodes $A$ and because the average price before might not occur in next step's node, we need to use interpolation.


## Estimation and Calibration
### Mean
- $E(\ln(S_T/S_0))$ : geometic mean of daily returns, derive $\mu - 0.5\sigma^{2}$, correct mean and std when we assume stock price follow lognormal
- $\ln(E[S_T/S_0])$ : arithmetic mean of daily returns,derive $\mu$, not the correct one

### Implied Volatility

Volatility can be easily derived by using past data,however,the volatility of options is considered to has forward looking information.Hence,we can't dirctly use historical $\sigma$ as volatility.

Define Implied voliltility satisfying

$$
f(\sigma_{imp}) = c(S_0,K,r,q,\sigma_{imp},T) - C_{market} = 0
$$

Here two ways to solve.(Assume volatility is a constant)

#### Bisection Method:

First find $[a_n,b_n]$ such that $f(a_n)f(b_n)<0$. The iterative steps to find $[a_{n+1},b_{n+1}]$ are :
- (1)Calculate $x_n = a_n +(b_n - a_n)/2$
- (2)If $f(a_n)f(x_n) < 0$ => $a_{n+1} = a_n$, $b_{n+1} = x_n$, else $a_{n+1} = x_n$, $b_{n+1} = b_n$


#### Newton's Method:

$$
x_{n+1} = x_n - \frac{f(x_n)}{f'(x_n)}
$$

Based on first order Taylor-Series

Volatility Smile
----
However, impled volatility isn't a constant as Black-Scholes' assumption.It has feature called volatility smile or smirk.Here we introduce Stocahstic Volatilit to lineate the curve of IV.

**If we want to forecast IV,there are some models we can choose including: SV,SVJ,SVJJ,Garch,GJR-Garch,Garch-Midas,HAR-RV-CJ...**


### Stochastic Volatility

## Greak Letters
 
### delta

$\Delta = \frac{\partial c}{\partial S_0}$

notes: the derivations won't be presented here , it can easily gets by deriving $\frac{\partial d_1}{\partial S_0} = \frac{\partial d_2}{\partial S_0} = \frac{1}{S_0 \sigma \sqrt{T}}$ in first step .....

- Calls: $\Delta = \exp(-qT) N(d_1)$, $\Delta$ is 1 when ITM and 0 when OTM

- Puts : $\Delta = \exp(-qT)[N(d_1)-1]$ and will always in -1 - 0, $\Delta$ is -1 when ITM and 0 when OTM

Because $\Delta$ jumps almost between two values, it varies dicountinuosly when near  ATM


### gamma

$\gamma  = \frac{\partial^{2} c}{\partial S_0^{2}}$

- Be same and always positive for both calls and puts.
- The value of $\gamma$ attains highest when ATM because $\Delta$  varies the most when near ATM.
- The kurtosis is because higher for short T.The reason is due to the extreme variation (discountinuos change)of $\delta$ near maturity.


### vega

$\nu  = \frac{\partial c}{\partial \sigma}$

- Be same and always positive for both calls and puts.It implies that higher volatility increase options' price
- When time close to maturity, $\nu$ become smaller. Because there is lesser time for volatility to affect option price
- Similar to $\gamma$ ,both are alike density function.

### rho

$\rho  = \frac{\partial c}{\partial r}$

- Similar to $\Delta$, but not be restricted to 0 - 1 or -1 -0

### theta

$\theta  = \frac{\partial c}{\partial T}$

- Meaure the speed of the option value decay with the passage of time.
- Be always negative for American and European calls, but not for European puts.
- When ATM $\theta$ is most negative, due to fatest time decay .


### The relationship among $\Delta$ , $\gamma$ , $\theta$

By PDE:

$$
\frac{\partial f}{\partial t} + (r-q)S\frac{\partial f}{\partial S} + \frac{1}{2}\sigma^{2}S^{2} \frac{\partial^{2} f}{\partial S^{2}} = rf
$$

and the definitions of $\Delta$ , $\gamma$ and $\theta$ ,we can derie

$$
\theta + (r-q)S\Delta + \frac{1}{2}\sigma^{2}S^{2} \gamma = rf
$$

If we know any three of $\Delta$ , $\gamma$ , $\theta$ and the value of f, we can easily get the unknown one.Moreover, if f represents a delta-neutral porfolio, then

$$
\theta + \frac{1}{2}\sigma^{2}S^{2} \gamma = rf
$$

which implies that for delta-neutral porfolio, higher $\gamma$ and $\theta$ are good feature for option holders.

### Calculations

For European , due to Black-Scholes, we can easily get greek letters.However,what about other types of option. Here are three methods to derive greek letters and how to dynamic delta hedge.

#### CRR[Pelsser and Vorst(1994)]

Only applcable on $\Delta$ , $\gamma$ and $\theta$.

#### Monte-Carlo

Here are two ways :pathwise and likelihood.
Take Eurpoean put as example.

note: huge computation burden due to simulation needs to be performed twice

##### Pathwise


##### Likelihood

#### Dynamic Delta Hedge

## Trading Strategies

## Option Trading System