"""Cox-Ross-Rubinstein binomial-tree pricing implementations."""

import math
import numpy as np


def CRR_O_n2(S, K, r, q, sigma, T, num_time_steps, option_type='European'): 
    dt = T/num_time_steps
    u = math.exp(sigma*math.sqrt(dt))
    d = math.exp(-sigma*math.sqrt(dt))
    p = (math.exp((r-q)*dt)-d)/(u-d)

# asset price
    asset_price = np.zeros((num_time_steps+1, num_time_steps+1))
    for i in range(num_time_steps+1):
        for j in range(i+1):
            asset_price[i][j] = S*(u**j)*(d**(i-j))

#option price - Call
    call_option_price = np.zeros((num_time_steps+1, num_time_steps+1))
    for j in range(num_time_steps+1):
        call_option_price[num_time_steps][j] = max(asset_price[num_time_steps][j]-K, 0)
    for i in range(num_time_steps-1, -1, -1):
        for j in range(i+1):
            hold_value = math.exp(-r*dt)*(p*call_option_price[i+1][j+1]+(1-p)*call_option_price[i+1][j])
            if option_type == 'American':
                exercise_value = max(asset_price[i][j] - K, 0)
                call_option_price[i][j] = max(hold_value, exercise_value)
            else:
                call_option_price[i][j] = hold_value

#option price - Put
    put_option_price = np.zeros((num_time_steps+1, num_time_steps+1))
    for j in range(num_time_steps+1):
        put_option_price[num_time_steps][j] = max(K - asset_price[num_time_steps][j], 0)
    for i in range(num_time_steps-1, -1, -1):
        for j in range(i+1):
            hold_value = math.exp(-r*dt)*(p*put_option_price[i+1][j+1]+(1-p)*put_option_price[i+1][j])
            if option_type == 'American':
                exercise_value = max(K - asset_price[i][j], 0)
                put_option_price[i][j] = max(hold_value, exercise_value)
            else:
                put_option_price[i][j] = hold_value

    return call_option_price[0][0], put_option_price[0][0]     

#--------------------------------------------------------------------------------
def CRR_O_n(S, K, r, q, sigma, T, num_time_steps, option_type='European'): 
    dt = T/num_time_steps
    u = math.exp(sigma*math.sqrt(dt))
    d = math.exp(-sigma*math.sqrt(dt))
    p = (math.exp((r-q)*dt)-d)/(u-d)
    discount = math.exp(-r*dt)
    
    # Terminal values for call option
    call_prices = np.zeros(num_time_steps+1)
    for j in range(num_time_steps+1):
        St = S*(u**j)*(d**(num_time_steps-j))
        call_prices[j] =  max(St-K,0)
    
    # Backward induction 
    for i in range(num_time_steps-1, -1,-1):
        for j in range(i+1):
            S_ij = S*(u**j)*(d**(i-j))
            hold_value = discount * (p*call_prices[j+1]+(1-p)*call_prices[j])
            
            if option_type == 'American':
                exercise_value = max(S_ij-K,0)
                call_prices[j] = max(hold_value, exercise_value)
            else:
                call_prices[j] = hold_value

    crr_call = call_prices[0]
    
    # Terminal values for put option
    put_prices = np.zeros(num_time_steps+1)
    for j in range(num_time_steps+1):
        ST = S * (u**j) * (d**(num_time_steps-j))
        put_prices[j] = max(K - ST, 0)
    
    # Backward induction
    for i in range(num_time_steps-1, -1, -1):
        for j in range(i+1):
            S_ij = S * (u**j) * (d**(i-j))
            hold_value = discount * (p * put_prices[j+1] + (1-p) * put_prices[j])
            
            if option_type == 'American':
                exercise_value = max(K - S_ij, 0)
                put_prices[j] = max(hold_value, exercise_value)
            else:
                put_prices[j] = hold_value
    
    crr_put = put_prices[0]
    
    return crr_call, crr_put



#-------------------------------------------------------------------------------
def Combinatorial_european_price(S, K, r, q,sigma, T, n):
    dt = T/n
    u = math.exp(sigma*math.sqrt(dt))
    d = math.exp(-sigma*math.sqrt(dt))
    p = (math.exp((r-q)*dt)-d)/(u-d)
    
    eu_call_price = 0
    eu_put_price = 0

    for i in range(n+1):
        ST = S*(u**i)*(d**(n-i))
        eu_call_price += math.exp(math.lgamma(n+1)-math.lgamma(i+1)-math.lgamma(n-i+1)+i*math.log(p)+(n-i)*math.log((1-p)))*max(ST-K,0)
        eu_put_price += math.exp(math.lgamma(n+1)-math.lgamma(i+1)-math.lgamma(n-i+1)+i*math.log(p)+(n-i)*math.log((1-p)))*max(K-ST,0)
        #The rason why use exp and lgamma (log(x!)) instead of directly calculate is because when C 100 50, it takes a lomg time to compute
    eu_call_price *= math.exp(-r*T)
    eu_put_price *= math.exp(-r*T)

    return  eu_call_price,eu_put_price

#-------------------------------------------------------------------------------------------
def CRR_BS(S, K, r, q, sigma, T, n, option_type='European'):
    dt = T/n
    u = math.exp(sigma*math.sqrt(dt))
    d = math.exp(-sigma*math.sqrt(dt))
    p = (math.exp((r-q)*dt)-d)/(u-d)
    discount = math.exp(-r*dt)
    #Call
    call_prices = np.zeros(n)
    for j in range(n):
        S_ij = S * (u**j) * (d**(n-1-j))  
        call_prices[j] = BS(S_ij, K, r, q, sigma, dt)[0]
    
    # Backward induction 
    for i in range(n-2, -1, -1):
        for j in range(i+1):
            S_ij = S*(u**j)*(d**(i-j))
            hold_value = discount * (p*call_prices[j+1] + (1-p)*call_prices[j])
            if option_type == 'American':
                call_prices[j] = max(hold_value, max(S_ij-K, 0))
            else:
                call_prices[j] = hold_value
    
    crr_call = call_prices[0]
    
    # Put
    put_prices = np.zeros(n)
    for j in range(n):
        S_ij = S * (u**j) * (d**(n-1-j))
        put_prices[j] = BS(S_ij, K, r, q, sigma, dt)[1]

     # Backward induction
    for i in range(n-2, -1, -1):
        for j in range(i+1):
            S_ij = S*(u**j)*(d**(i-j))
            hold_value = discount * (p*put_prices[j+1] + (1-p)*put_prices[j])
            if option_type == 'American':
                put_prices[j] = max(hold_value, max(K-S_ij, 0))
            else:
                put_prices[j] = hold_value
    
    crr_put = put_prices[0]
    
    return crr_call, crr_put







   
