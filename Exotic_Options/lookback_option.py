import math
import numpy as np



def Bin_look_back_put(St, r, q, sigma, T_minus_t, Smax, n):
    dt = T_minus_t / n
    p  = (math.exp((r - q) * dt) - math.exp(-sigma * math.sqrt(dt))) / (math.exp(sigma * math.sqrt(dt)) - math.exp(-sigma * math.sqrt(dt)))
    discount = math.exp(-r * dt)


    S_ij = np.zeros((n+1, n+1))
    for i in range(n+1):
        for j in range(i+1):
            S_ij[i][j] = St * math.exp(sigma * math.sqrt(dt) * (2*j - i)) 

    # S max of each terminal node
    S_max = [[set() for _ in range(n+1)] for _ in range(n+1)]
    S_max[0][0].add(max(Smax, St))

    for i in range(n):
        for j in range(i+1):
            for smax in S_max[i][j]:
                # upward
                S_max[i+1][j+1].add(max(smax, S_ij[i+1][j+1]))
                # downward
                S_max[i+1][j].add(max(smax, S_ij[i+1][j]))

    # European
    european_put = [[dict() for _ in range(n+1)] for _ in range(n+1)]

    for j in range(n+1):
        for smax in S_max[n][j]:
            european_put[n][j][smax] = max(smax - S_ij[n][j], 0)

    for i in range(n-1, -1, -1):
        for j in range(i+1):
            for smax in S_max[i][j]:
                S_max_up = max(smax, S_ij[i+1][j+1])   
                S_max_dn = max(smax, S_ij[i+1][j])      
                european_put[i][j][smax] = discount * (p * european_put[i+1][j+1][S_max_up] + (1-p) * european_put[i+1][j][S_max_dn])

    # American
    american_put = [[dict() for _ in range(n+1)] for _ in range(n+1)]

    for j in range(n+1):
        for smax in S_max[n][j]:
            american_put[n][j][smax] = max(smax - S_ij[n][j], 0)

    for i in range(n-1, -1, -1):
        for j in range(i+1):
            for smax in S_max[i][j]:
                S_max_up = max(smax, S_ij[i+1][j+1])
                S_max_dn = max(smax, S_ij[i+1][j])
                hold_value  = discount * (p * american_put[i+1][j+1][S_max_up] + (1-p) * american_put[i+1][j][S_max_dn])
                exercise_value = max(smax - S_ij[i][j], 0)
                american_put[i][j][smax] = max(hold_value, exercise_value)
          

    return european_put[0][0][max(Smax, St)], american_put[0][0][max(Smax, St)]


def Monte_Lookback_put(St, r, q, sigma, T_minus_t, Smax, n, num_simulations, num_repetitions):
    np.random.seed(100)
    dt = T_minus_t / n
    Z = np.random.standard_normal((num_repetitions, num_simulations, n))
    log_returns = (r - q - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z
    S_paths = St * np.exp(np.cumsum(log_returns, axis=2))
    S_max_path = np.maximum(np.max(S_paths, axis=2), max(Smax, St)) 
    S_T = S_paths[:, :, -1]
    payoff = np.maximum(S_max_path - S_T, 0)
    discounted_payoff = np.exp(-r * T_minus_t) * payoff
    batch_prices = np.mean(discounted_payoff, axis=1)
    MC_price = np.mean(batch_prices)
    MC_se = np.std(batch_prices, ddof=1)
    return MC_price, MC_se
