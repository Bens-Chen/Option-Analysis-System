import math
from  scipy.stats import norm  # pip install scipy

def BS(S,K,r,q,sigma,T):
    d1 = (math.log(S/K)+(r-q+(1/2)*sigma**2)*T)/(sigma*math.sqrt(T))
    d2 = d1 - sigma*math.sqrt(T)
    BS_callprice = S*math.exp(-q*T)*norm.cdf(d1)-K*math.exp(-r*T)*norm.cdf(d2)
    BS_putprice = K*math.exp(-r*T)*norm.cdf(-d2)-S*math.exp(-q*T)*norm.cdf(-d1)
    return BS_callprice, BS_putprice
