"""Piecewise interval-position payoff helper."""

def interval_position(stock_price,lower_bound,upper_bound,lower_shares,upper_shares):
    if stock_price <= lower_bound:
        return float(lower_shares)
    if stock_price >= upper_bound:
        return float(upper_shares)

    slope = (upper_shares - lower_shares) / (upper_bound - lower_bound)
    return float(lower_shares + slope * (stock_price - lower_bound))


def interval_trade_plan(prices,lower_bound,upper_bound,lower_shares=200,upper_shares=0):
    plan = []
    previous_shares = None

    for price in prices:
        target_shares = interval_position(price,lower_bound,upper_bound,lower_shares,upper_shares)

        if previous_shares is None:
            trade_shares = target_shares
        else:
            trade_shares = target_shares - previous_shares

        if trade_shares > 0:
            action = "buy"
        elif trade_shares < 0:
            action = "sell"
        else:
            action = "hold"

        plan.append(
            {
                "price": float(price),
                "target_shares": target_shares,
                "trade_shares": trade_shares,
                "action": action,
            }
        )
        previous_shares = target_shares

    return plan
