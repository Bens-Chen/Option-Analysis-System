"""Straddle strategy payoff functions."""

from .payoffs import call_payoff, put_payoff


def long_straddle_profit(stock_price, strike, call_premium, put_premium):
    payoff = call_payoff(stock_price, strike) + put_payoff(stock_price, strike)
    initial_cost = call_premium + put_premium
    return payoff - initial_cost


def short_straddle_profit(stock_price, strike, call_premium, put_premium):
    return -long_straddle_profit(stock_price, strike, call_premium, put_premium)
