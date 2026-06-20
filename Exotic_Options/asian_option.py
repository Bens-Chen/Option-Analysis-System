"""Asian option pricing by analytic approximation and simulation."""

import math
import numpy as np
import copy


def geometric_sum(ratio, terms):
    if terms <= 0:
        return 0.0
    if abs(ratio - 1.0) < 1e-12:
        return float(terms)
    return ratio * (1 - ratio**terms) / (1 - ratio)


def interpolate_option_value(next_A, next_payoff, target_average):
    if target_average >= next_A[0]:
        return next_payoff[0]
    if target_average <= next_A[-1]:
        return next_payoff[-1]

    for idx in range(len(next_A) - 1):
        upper_A = next_A[idx]
        lower_A = next_A[idx + 1]
        if lower_A <= target_average <= upper_A:
            weight_upper = (target_average - lower_A) / (upper_A - lower_A)
            weight_lower = 1.0 - weight_upper
            return weight_upper * next_payoff[idx] + weight_lower * next_payoff[idx + 1]

    return next_payoff[-1]

def asian_call(St, K, r, q, sigma, t, T_minus_t, M, n, S_avet):
    dt = T_minus_t / n
    u = math.exp(sigma * math.sqrt(dt))
    d = math.exp(-sigma * math.sqrt(dt))
    p = (math.exp((r - q) * dt) - d) / (u - d)
    discount_factor = math.exp(-r * dt)
    # S_avet includes St, so the number of observed prices must also include St.
    n_past = max(round(t / dt) + 1, 1)

    A_max = np.zeros((n+1, n+1))
    A_min = np.zeros((n+1, n+1))

    for i in range(n+1):
        for j in range(i+1):
            up_moves = i - j
            A_max[i][j] = (S_avet * n_past+ St * geometric_sum(u, up_moves)+ St * (u**up_moves) * geometric_sum(d, j)) / (n_past + i)
            A_min[i][j] = (S_avet * n_past+ St * geometric_sum(d, j)+ St * (d**j) * geometric_sum(u, up_moves)) / (n_past + i)

    A      = [[[0.0 for _ in range(M+1)] for _ in range(n+1)] for _ in range(n+1)]
    Payoff = [[[0.0 for _ in range(M+1)] for _ in range(n+1)] for _ in range(n+1)]

    for i in range(n+1):
        for j in range(i+1):
            for k in range(M+1):
                if abs(A_max[i][j] - A_min[i][j]) < 1e-12:
                    A[i][j][k] = A_max[i][j]
                else:
                    A[i][j][k] = ((M - k) / M) * A_max[i][j] + (k / M) * A_min[i][j]
                Payoff[i][j][k] = max(A[i][j][k] - K, 0)

    # European
    euro_Payoff = copy.deepcopy(Payoff)

    for i in range(n-1, -1, -1):
        for j in range(i+1):
            for k in range(M+1):
                A_u = ((n_past + i) * A[i][j][k] + St * u**(i+1-j) * d**j) / (n_past + i + 1)
                A_d = ((n_past + i) * A[i][j][k] + St * u**(i-j) * d**(j+1)) / (n_past + i + 1)

                C_u = interpolate_option_value(A[i+1][j], euro_Payoff[i+1][j], A_u)
                C_d = interpolate_option_value(A[i+1][j+1], euro_Payoff[i+1][j+1], A_d)

                euro_Payoff[i][j][k] = discount_factor * (p * C_u + (1-p) * C_d)

    # American
    amer_Payoff = copy.deepcopy(Payoff)

    for i in range(n-1, -1, -1):
        for j in range(i+1):
            for k in range(M+1):
                A_u = ((n_past + i) * A[i][j][k] + St * u**(i+1-j) * d**j) / (n_past + i + 1)
                A_d = ((n_past + i) * A[i][j][k] + St * u**(i-j) * d**(j+1)) / (n_past + i + 1)

                C_u = interpolate_option_value(A[i+1][j], amer_Payoff[i+1][j], A_u)
                C_d = interpolate_option_value(A[i+1][j+1], amer_Payoff[i+1][j+1], A_d)

                hold_value = discount_factor * (p * C_u + (1-p) * C_d)
                exercise_value = Payoff[i][j][k]
                amer_Payoff[i][j][k] = max(exercise_value, hold_value)

    return euro_Payoff[0][0][0], amer_Payoff[0][0][0]


def monte_carlo_asian_call(St, K, r, q, sigma, t, T_minus_t, n, S_avet, num_simulations, num_repetitions):
    np.random.seed(55)
    dt = T_minus_t / n
    n_past = max(round(t / dt) + 1, 1)

    Z = np.random.standard_normal((num_repetitions, num_simulations, n))
    log_returns = (r - q - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z
    S_paths = St * np.exp(np.cumsum(log_returns, axis=2)) 
    S_ave_path = (S_avet * n_past + np.sum(S_paths, axis=2)) / (n_past + n)

    payoff = np.maximum(S_ave_path - K, 0)
    discounted_payoff = np.exp(-r * T_minus_t) * payoff
    batch_prices = np.mean(discounted_payoff, axis=1)
    MC_price = np.mean(batch_prices)
    MC_se = np.std(batch_prices, ddof=1)

    return MC_price, MC_se
