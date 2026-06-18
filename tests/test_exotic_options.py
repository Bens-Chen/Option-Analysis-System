from Exotic_Options.barrier_option import monte_carlo_barrier_option
from Exotic_Options.binary_option import (
    asset_or_nothing_binary_price,
    cash_or_nothing_binary_price,
)
from Methods.black_scholes import BS


def test_cash_or_nothing_binary_call_is_between_zero_and_discounted_cash():
    price = cash_or_nothing_binary_price(100, 100, 0.04, 0.0, 0.2, 1.0, "call", 10)

    assert 0 < price < 10


def test_cash_and_asset_binary_replicate_vanilla_call():
    S = 100
    K = 100
    r = 0.04
    q = 0.0
    sigma = 0.2
    T = 1.0

    asset_binary = asset_or_nothing_binary_price(S, K, r, q, sigma, T, "call")
    cash_binary = cash_or_nothing_binary_price(S, K, r, q, sigma, T, "call", K)
    vanilla_call, _ = BS(S, K, r, q, sigma, T)

    assert abs((asset_binary - cash_binary) - vanilla_call) < 1e-10


def test_knock_in_and_knock_out_sum_close_to_vanilla_call():
    S = 100
    K = 100
    barrier = 90
    r = 0.04
    q = 0.0
    sigma = 0.2
    T = 1.0
    seed = 42

    down_out, _ = monte_carlo_barrier_option(
        S, K, barrier, r, q, sigma, T, "call", "down-and-out", 80, 30000, seed
    )
    down_in, _ = monte_carlo_barrier_option(
        S, K, barrier, r, q, sigma, T, "call", "down-and-in", 80, 30000, seed
    )
    vanilla_call, _ = BS(S, K, r, q, sigma, T)

    assert abs((down_out + down_in) - vanilla_call) < 0.35
