"""Monte Carlo option pricing helpers for simulated terminal payoffs."""

import numpy as np

def Monte_Carlo(S, r, q, sigma, T, K, num_simulations, num_repetitions):
    Z = np.random.standard_normal((num_repetitions, num_simulations))
    ST = S * np.exp((r - q - 0.5 * sigma**2) * T + sigma * np.sqrt(T) * Z)
    
    Call_payoff = np.maximum(ST - K, 0)
    Put_payoff = np.maximum(K - ST, 0)
    C_batch_prices = np.exp(-r * T) * np.mean(Call_payoff, axis=1)
    P_batch_prices = np.exp(-r * T) * np.mean(Put_payoff, axis=1)
    MC_Call_price = np.mean(C_batch_prices)
    MC_Put_price = np.mean(P_batch_prices)
    MC_C_se = np.std(C_batch_prices, ddof=1) 
    MC_P_se = np.std(P_batch_prices, ddof=1)

    return MC_Call_price, MC_Put_price, MC_C_se, MC_P_se

#-Antithetic with Moment Matching-----------------------------------------------------------------------------------
    # n_half = num_of_simulations//2
    # Z = np.random.standard_normal((num_of_repetitions, n_half, num_of_assets))
    # Z_anti = np.concatenate((Z, -Z), axis=1)  -----> Antithetic
    # Mean_Z = np.mean(Z_anti,axis = 1)
    # Std_Z = np.std(Z_anti,axis = 1,ddof =1)
    # Standard_Z = (Z_anti-Mean_Z[:,np.newaxis,:])/Std_Z[:,np.newaxis,:] ------->Moment Matching
