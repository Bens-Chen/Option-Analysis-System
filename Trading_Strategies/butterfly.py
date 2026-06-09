from .payoffs import call_payoff


def call_butterfly_profit(
    stock_price,
    lower_strike,
    middle_strike,
    upper_strike,
    lower_call_premium,
    middle_call_premium,
    upper_call_premium,
):
    payoff = (
        call_payoff(stock_price, lower_strike)
        - 2 * call_payoff(stock_price, middle_strike)
        + call_payoff(stock_price, upper_strike)
    )
    initial_cost = lower_call_premium - 2 * middle_call_premium + upper_call_premium
    return payoff - initial_cost


def asymmetric_call_butterfly_profit(
    stock_price,
    lower_strike,
    middle_strike,
    upper_strike,
    lower_call_premium,
    middle_call_premium,
    upper_call_premium,
    lower_quantity=1,
    middle_quantity=-3,
    upper_quantity=2,
):
    payoff = (
        lower_quantity * call_payoff(stock_price, lower_strike)
        + middle_quantity * call_payoff(stock_price, middle_strike)
        + upper_quantity * call_payoff(stock_price, upper_strike)
    )
    initial_cost = (
        lower_quantity * lower_call_premium
        + middle_quantity * middle_call_premium
        + upper_quantity * upper_call_premium
    )
    return payoff - initial_cost
