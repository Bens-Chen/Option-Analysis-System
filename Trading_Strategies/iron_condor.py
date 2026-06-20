"""Iron condor strategy payoff functions."""

from .payoffs import call_payoff, put_payoff


def short_iron_condor_profit(
    stock_price,
    long_put_strike,
    short_put_strike,
    short_call_strike,
    long_call_strike,
    long_put_premium,
    short_put_premium,
    short_call_premium,
    long_call_premium,
):
    if not (long_put_strike < short_put_strike < short_call_strike < long_call_strike):
        raise ValueError(
            "strikes must satisfy long_put < short_put < short_call < long_call."
        )

    payoff = (
        put_payoff(stock_price, long_put_strike)
        - put_payoff(stock_price, short_put_strike)
        - call_payoff(stock_price, short_call_strike)
        + call_payoff(stock_price, long_call_strike)
    )
    initial_cost = (
        long_put_premium
        - short_put_premium
        - short_call_premium
        + long_call_premium
    )
    return payoff - initial_cost


def long_iron_condor_profit(
    stock_price,
    long_put_strike,
    short_put_strike,
    short_call_strike,
    long_call_strike,
    long_put_premium,
    short_put_premium,
    short_call_premium,
    long_call_premium,
):
    return -short_iron_condor_profit(
        stock_price,
        long_put_strike,
        short_put_strike,
        short_call_strike,
        long_call_strike,
        long_put_premium,
        short_put_premium,
        short_call_premium,
        long_call_premium,
    )
