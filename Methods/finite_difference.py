"""Finite-difference option pricing grids for PDE-based valuation."""

import numpy as np

def finite_diiference_implicit(S0, K, r, q, sigma, T, Smin, Smax, m, n, option_type="european"):

    dt = T / n
    dS = (Smax - Smin) / m

    j_S0 = round((S0 - Smin) / dS)
    S0_index = j_S0 - 1
    S0_index = max(0, min(S0_index, m - 2))

    j_arr = np.arange(1, m, dtype=float)
    S_arr = Smin + j_arr * dS

    j = j_arr
    a = (r - q) / 2 * j * dt  -  0.5 * sigma**2 * j**2 * dt
    b =  1 + sigma**2 * j**2 * dt + r * dt
    c = -(r - q) / 2 * j * dt  -  0.5 * sigma**2 * j**2 * dt

    A = np.zeros((m - 1, m - 1))
    for k in range(m - 1):
        A[k, k] = b[k]
        if k > 0:
            A[k, k - 1] = a[k]
        if k < m - 2:
            A[k, k + 1] = c[k]

    A_inv = np.linalg.inv(A)

    bc_upper_call = m * dS - K
    bc_lower_call = 0.0
    bc_upper_put  = 0.0
    bc_lower_put  = K - Smin

    f_ij_call = np.maximum(S_arr - K, 0.0)
    f_ij_put  = np.maximum(K - S_arr, 0.0)

    
    for _ in range(n):
        rhs_call = f_ij_call.copy()
        rhs_put  = f_ij_put.copy()

        rhs_call[0]  -= a[0]  * bc_lower_call
        rhs_put[0]   -= a[0]  * bc_lower_put
        rhs_call[-1] -= c[-1] * bc_upper_call
        rhs_put[-1]  -= c[-1] * bc_upper_put

        f_ij_call = np.dot(A_inv, rhs_call)
        f_ij_put  = np.dot(A_inv, rhs_put)

        if option_type.lower() == "american":
            f_ij_call = np.maximum(f_ij_call, S_arr - K)
            f_ij_put  = np.maximum(f_ij_put,  K - S_arr)

    return f_ij_call[S0_index], f_ij_put[S0_index]

#-----------------------------------------------------------------------------------------------------
def finite_diiference_explicit(S0, K, r, q, sigma, T, Smin, Smax, m, n, option_type="european"):

    dt = T / n
    dS = (Smax - Smin) / m

    j_max = m - 1
    cfl = sigma**2 * j_max**2 * dt
    if cfl > 1:
        n_min = int(sigma**2 * j_max**2 * T) + 1
        raise ValueError(
            f"Explicit UNSTABLE: sigma^2*j_max^2*dt = {cfl:.4f} > 1. "
            f"Use n >= {n_min}."
        )

    j_S0 = round((S0 - Smin) / dS)
    S0_index = j_S0 - 1
    S0_index = max(0, min(S0_index, m - 2))

    j_arr = np.arange(1, m, dtype=float)
    S_arr = Smin + j_arr * dS

    j = j_arr
    d  = 1 + r * dt
    a_star = (1 / d) * (-0.5 * (r - q) * j * dt + 0.5 * sigma**2 * j**2 * dt)
    b_star = (1 / d) * (1 - sigma**2 * j**2 * dt)
    c_star = (1 / d) * ( 0.5 * (r - q) * j * dt + 0.5 * sigma**2 * j**2 * dt)

    A = np.zeros((m - 1, m - 1))
    for k in range(m - 1):
        A[k, k] = b_star[k]
        if k > 0:
            A[k, k - 1] = a_star[k]
        if k < m - 2:
            A[k, k + 1] = c_star[k]

    bc_upper_call = m * dS - K
    bc_lower_call = 0.0
    bc_upper_put  = 0.0
    bc_lower_put  = K - Smin

    f_ij_call = np.maximum(S_arr - K, 0.0)
    f_ij_put  = np.maximum(K - S_arr, 0.0)

    for _ in range(n):
        rhs_call = f_ij_call.copy()
        rhs_put  = f_ij_put.copy()

        rhs_call[0]  += a_star[0]  * bc_lower_call
        rhs_put[0]   += a_star[0]  * bc_lower_put
        rhs_call[-1] += c_star[-1] * bc_upper_call
        rhs_put[-1]  += c_star[-1] * bc_upper_put

        f_ij_call = np.dot(A, rhs_call)
        f_ij_put  = np.dot(A, rhs_put)

        if option_type.lower() == "american":
            f_ij_call = np.maximum(f_ij_call, S_arr - K)
            f_ij_put  = np.maximum(f_ij_put,  K - S_arr)

    return f_ij_call[S0_index], f_ij_put[S0_index]
