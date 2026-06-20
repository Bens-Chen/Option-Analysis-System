"""Strangle strategy payoff functions."""

from .payoffs import call_payoff, put_payoff


def long_strangle_profit(
    stock_price,
    put_strike,
    call_strike,
    put_premium,
    call_premium,
):
    if put_strike >= call_strike:
        raise ValueError("put_strike should be smaller than call_strike.")

    payoff = put_payoff(stock_price, put_strike) + call_payoff(stock_price, call_strike)
    initial_cost = put_premium + call_premium
    return payoff - initial_cost


def short_strangle_profit(
    stock_price,
    put_strike,
    call_strike,
    put_premium,
    call_premium,
):
    return -long_strangle_profit(
        stock_price,
        put_strike,
        call_strike,
        put_premium,
        call_premium,
    )
