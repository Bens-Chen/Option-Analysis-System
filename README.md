# Option Pricing

This repository is some introductions and codes of different methods and some techniques to price options.

## Methods
### Black-Scholes

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

 A more complicated method. It requires u to get a similar, relevent underlying asset or derivative.Over all, u need to asumme $W = X + B(Y - \mu)$, and find $Y$ which has mean equals to $\mu$, and

$$
\mathrm{Var}(W) = \mathrm{Var}(X) + 2B\mathrm{Cov}(X,Y) + B^{2}\mathrm{Var}(Y)
$$

where $2B\mathrm{Cov}(X,Y) + B^{2}\mathrm{Var}(Y) < 0$.
 
 The first difficulty is  find the true mean of $Y$ (not sample mean) and the second is decide $B$ because $B = \mathrm{Cov}(X,Y)/\mathrm{Var}(Y)$, but due to $X$ and $Y$ are both dependent on drawn samples, the estimators might be affected.

####  EMS[Duan and Siminato(1998)]: 

A method performs better than others when pricing path dependent options.The logic is to adjust price to conform to martingale.


### Finite Difference

This method is proposed to solve PDE.It has two way ,one is Implicit, the other is Explicit

Similar to CRR, we divide discretize time but also Stock price,$F_{i,j}$ means option price when time $i$ and stock price $j$, and if the grid is small enough, it is equivalent to derive closed form.

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

Here two ways to solve.

#### Bisection Method:

First find $[a_n,b_n]$ such that $f(a_n)f(b_n)<0$. The steps to find $[a_{n+1},b_{n+1}]$ are :
- (1)Calculate $x_n = a_n +(b_n - a_n)/2$
- (2)If $f(a_n)f(x_n) < 0$ => $a_{n+1} = a_n$, $b_{n+1} = x_n$, else $a_{n+1} = x_n$, $b_{n+1} = b_n$


#### Newton's Method:

$$
x_{n+1} = x_n - \frac{f(x_n)}{f'(x_n)}
$$

Based on first order Taylor-Series
