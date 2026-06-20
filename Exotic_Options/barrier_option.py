"""Barrier option pricing by path simulation."""

import numpy as np


def monte_carlo_barrier_option(S,K,barrier,r,q,sigma,T,option_kind="call",barrier_type="down-and-out",n=252,num_simulations=10000,seed=100,num_repetitions=20):

    np.random.seed(1000)
    dt = T / n
    z = np.random.standard_normal((num_repetitions, num_simulations, n))
    log_returns = (r - q - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
    paths = S * np.exp(np.cumsum(log_returns, axis=2))
    initial_prices = np.full((num_repetitions, num_simulations, 1), S)
    paths = np.concatenate([initial_prices, paths], axis=2)

    if barrier_type.startswith("down"):
        touched = np.min(paths, axis=2) <= barrier
    else:
        touched = np.max(paths, axis=2) >= barrier

    active = ~touched if barrier_type.endswith("out") else touched
    terminal = paths[:, :, -1]
    if option_kind == "call":
        vanilla_payoff = np.maximum(terminal - K, 0.0)
    else:
        vanilla_payoff = np.maximum(K - terminal, 0.0)

    payoff = np.where(active, vanilla_payoff, 0.0)
    discounted_payoff = np.exp(-r * T) * payoff
    batch_prices = np.mean(discounted_payoff, axis=1)
    MC_price = np.mean(batch_prices)
    MC_se = np.std(batch_prices, ddof=1)
    return MC_price, MC_se
