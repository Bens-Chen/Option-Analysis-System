# Option-Pricing

This repository is some introductions and codes of different methods and some techniques to price options.

## Standard Methods
### Black-Scholes

The most tyipical one with closed form. If options' payoff aren't the same as vanilla call or put, we can still use a simple way (compared to derive from PDE)Martingale Pricing Method to get it's closed form.

Martingale Pricing Method is an alternative method to derive Black-Scholes like formulas.The most difficult part is how to change P measure to Q measure, however, due to RNVR, we know that P measure is equivalent to Q measure when pricing.Then by applying Girsanov Theorem and some calculations we can easily get the closed form of any European options.

### CRR 

One can seem to be the most versatile to price not only European,American , but also some other exotic options like: Asian,Lookback....Although the logic is similar, the code are different when pricing different option.

Here are two simple versions to pricing European and American with different required Quadratic time
O(n^2) and O(n)

### Monte-Carlo

Different to the previous two methods,Monte-Carlo can't derice exact price, but can give users a confidence interval.This method is more like a method to validate or assure ur outcome is reasonable.

In addition, in order to get a more narrow interval ,we can use some variance reduction methods, such as moment matching, antithetic variate approach, control variates and Emperical Martingale Simulations(EMS).

Here's easy introduction of each variane reduction method.
- Moment Matching: Matching the first two moments of the SND,mean equals to 0, variance equal to 1

- Antithetic Variate Approach: Get mean equals to 0, the logic is to sample first half, then latter half will be the negaitve of first half.

- Control Variates[Kemna and Vorst(1990)]: A more complicated method. It requires u to get a similar, relevent underlying asset or derivative.Over all, u need to asumme  W = X+B(Y-u), and find Y which has mean equals to u, and Var(W) = Var(X) + 2BCov(X,Y) + B^2 *Var(Y) ,where 2BCov(X,Y) + B^2 *Var(Y) < 0.The first difficulty is  find the true mean of Y (not sample mean) and the second is decide B because B = Cov(X,Y)/Var(Y), but due to X and Y are both dependent on drawn samples, the estimators might be affected.

-  EMS[Duan and Siminato(1998)]: a method performs better than others when pricing path dependent options.The logic is to adjust price to conform to martingale.


### Finite Difference

This method is proposed to solve PDE.It has two way ,one is Implicit, the other is Explicit

Similar to CRR, we divide discretize time but also Stock price,Fij means option price when time i and stock price j, and if the grid is small enough, it is equivalent to derive closed form.

- Implicit: node Fi+1,j derived from Fi,j+1 , Fi,j , Fi, j-1 three nodes.
 $$aj*Fi,j+1 +bj*Fi,j+cj*Fi,j-1 = Fi+1,j$$
 aj = 
 bj = 
 cj = 



## Advanced Methods
### CRR combined with Black-Scholes(to achieve faster convergence)
### Combinatorial methods (like BS could only be applied on European)



## Exotic Options








