"""Vertical and ratio spread payoff functions."""

from .payoffs import call_payoff, put_payoff


def bull_call_spread_profit(stock_price, lower_strike, upper_strike, lower_call_premium, upper_call_premium):

    payoff = call_payoff(stock_price, lower_strike) - call_payoff(stock_price, upper_strike)
    initial_cost = lower_call_premium - upper_call_premium
    return payoff - initial_cost


def bear_put_spread_profit(stock_price, lower_strike, upper_strike, lower_put_premium, upper_put_premium):

    payoff = put_payoff(stock_price, upper_strike) - put_payoff(stock_price, lower_strike)
    initial_cost = upper_put_premium - lower_put_premium
    return payoff - initial_cost


def ratio_call_spread_profit(stock_price,lower_strike,upper_strike,lower_call_premium,upper_call_premium,short_call_quantity):
    if short_call_quantity <= 1:
        raise ValueError("short_call_quantity should be larger than 1 for a ratio spread.")

    payoff = call_payoff(stock_price, lower_strike) - short_call_quantity * call_payoff(stock_price, upper_strike)
    initial_cost = lower_call_premium - short_call_quantity * upper_call_premium
    return payoff - initial_cost
