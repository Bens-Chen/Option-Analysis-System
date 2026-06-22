import numpy as np
import pandas as pd

from Option_System.analytics import option_price_from_bs


def option_leg_profit(stock_prices, option_kind, side, strike, premium, quantity=1):
    prices = np.asarray(stock_prices, dtype=float)
    if option_kind == "call":
        payoff = np.maximum(prices - strike, 0.0)
    elif option_kind == "put":
        payoff = np.maximum(strike - prices, 0.0)
    else:
        raise ValueError("option_kind must be 'call' or 'put'.")

    long_profit = payoff - premium
    sign = 1 if side == "long" else -1
    return sign * quantity * long_profit


def strategy_profit(stock_prices, legs):
    prices = np.asarray(stock_prices, dtype=float)
    total = np.zeros_like(prices, dtype=float)
    for leg in legs:
        total += option_leg_profit(
            prices,
            option_kind=leg["option_kind"],
            side=leg["side"],
            strike=float(leg["strike"]),
            premium=float(leg["premium"]),
            quantity=int(leg.get("quantity", 1)),
        )
    return total


def _option_leg_from_row(row, option_kind, side, quantity=1):
    return {
        "option_kind": option_kind,
        "side": side,
        "strike": float(row["strike"]),
        "premium": _market_premium(row),
        "bid": _quote_value(row, "bid"),
        "ask": _quote_value(row, "ask"),
        "lastPrice": _quote_value(row, "lastPrice"),
        "quantity": int(quantity),
    }


def build_chain_strategy_legs(strategy_name, selected_row, calls, puts, other_strike=None, ratio_quantity=2):
    strike = float(selected_row["strike"])
    selected_kind = selected_row["option_kind"]

    if strategy_name == "Single Option":
        return [_option_leg_from_row(selected_row, selected_kind, "long")]

    if strategy_name in {"Long Straddle", "Short Straddle"}:
        side = "long" if strategy_name == "Long Straddle" else "short"
        call_row = _nearest_strike_row(calls, strike)
        put_row = _nearest_strike_row(puts, strike)
        return [
            _option_leg_from_row(call_row, "call", side),
            _option_leg_from_row(put_row, "put", side),
        ]

    if strategy_name in {"Long Strangle", "Short Strangle"}:
        side = "long" if strategy_name == "Long Strangle" else "short"
        second = float(other_strike if other_strike is not None else strike * 1.05)
        put_strike = min(strike, second)
        call_strike = max(strike, second)
        call_row = _nearest_strike_row(calls, call_strike)
        put_row = _nearest_strike_row(puts, put_strike)
        return [
            _option_leg_from_row(put_row, "put", side),
            _option_leg_from_row(call_row, "call", side),
        ]

    if strategy_name in {"Long Call Butterfly", "Short Call Butterfly"}:
        lower_target, upper_target = _butterfly_outer_targets(calls, strike, other_strike)
        lower_call = _nearest_strike_row(calls, lower_target)
        middle_call = _nearest_strike_row(calls, strike)
        upper_call = _nearest_strike_row(calls, upper_target)
        middle_side = "short" if strategy_name == "Long Call Butterfly" else "long"
        wing_side = "long" if strategy_name == "Long Call Butterfly" else "short"
        return [
            _option_leg_from_row(lower_call, "call", wing_side),
            _option_leg_from_row(middle_call, "call", middle_side, quantity=2),
            _option_leg_from_row(upper_call, "call", wing_side),
        ]

    if strategy_name in {"Long Put Butterfly", "Short Put Butterfly"}:
        lower_target, upper_target = _butterfly_outer_targets(puts, strike, other_strike)
        lower_put = _nearest_strike_row(puts, lower_target)
        middle_put = _nearest_strike_row(puts, strike)
        upper_put = _nearest_strike_row(puts, upper_target)
        middle_side = "short" if strategy_name == "Long Put Butterfly" else "long"
        wing_side = "long" if strategy_name == "Long Put Butterfly" else "short"
        return [
            _option_leg_from_row(lower_put, "put", wing_side),
            _option_leg_from_row(middle_put, "put", middle_side, quantity=2),
            _option_leg_from_row(upper_put, "put", wing_side),
        ]

    if strategy_name == "Bull Call Spread":
        width = _spread_width(calls, strike, other_strike)
        lower_call = _nearest_strike_row(calls, strike)
        upper_call = _nearest_strike_row(calls, strike + width)
        _validate_ordered_strikes([lower_call, upper_call], "Bull call spread needs a lower long call and a higher short call.")
        return [
            _option_leg_from_row(lower_call, "call", "long"),
            _option_leg_from_row(upper_call, "call", "short"),
        ]

    if strategy_name == "Bear Put Spread":
        width = _spread_width(puts, strike, other_strike)
        upper_put = _nearest_strike_row(puts, strike)
        lower_put = _nearest_strike_row(puts, strike - width)
        _validate_ordered_strikes([lower_put, upper_put], "Bear put spread needs a lower short put and a higher long put.")
        return [
            _option_leg_from_row(upper_put, "put", "long"),
            _option_leg_from_row(lower_put, "put", "short"),
        ]

    if strategy_name == "Ratio Call Spread":
        width = _spread_width(calls, strike, other_strike)
        short_quantity = max(int(ratio_quantity), 2)
        lower_call = _nearest_strike_row(calls, strike)
        upper_call = _nearest_strike_row(calls, strike + width)
        _validate_ordered_strikes([lower_call, upper_call], "Ratio call spread needs a lower long call and a higher short call.")
        return [
            _option_leg_from_row(lower_call, "call", "long"),
            _option_leg_from_row(upper_call, "call", "short", quantity=short_quantity),
        ]

    if strategy_name in {"Short Iron Condor", "Long Iron Condor"}:
        width = _spread_width(calls, strike, other_strike)
        short_put = _nearest_strike_row(puts, strike - width)
        long_put = _nearest_strike_row(puts, strike - 2 * width)
        short_call = _nearest_strike_row(calls, strike + width)
        long_call = _nearest_strike_row(calls, strike + 2 * width)
        _validate_ordered_strikes(
            [long_put, short_put, short_call, long_call],
            "Iron condor needs four ordered strikes around the selected strike.",
        )
        if strategy_name == "Short Iron Condor":
            return [
                _option_leg_from_row(long_put, "put", "long"),
                _option_leg_from_row(short_put, "put", "short"),
                _option_leg_from_row(short_call, "call", "short"),
                _option_leg_from_row(long_call, "call", "long"),
            ]
        return [
            _option_leg_from_row(long_put, "put", "short"),
            _option_leg_from_row(short_put, "put", "long"),
            _option_leg_from_row(short_call, "call", "long"),
            _option_leg_from_row(long_call, "call", "short"),
        ]

    raise ValueError(f"Unknown strategy: {strategy_name}")


def _butterfly_outer_targets(calls, middle_strike, requested_width=None):
    strikes = sorted(float(strike) for strike in calls["strike"].dropna().unique())
    lower_strikes = [strike for strike in strikes if strike < middle_strike]
    upper_strikes = [strike for strike in strikes if strike > middle_strike]
    if not lower_strikes or not upper_strikes:
        raise ValueError("Butterfly spread needs strikes below and above the selected middle strike.")

    if requested_width is None:
        return lower_strikes[-1], upper_strikes[0]

    width = abs(float(requested_width))
    if width == 0:
        return lower_strikes[-1], upper_strikes[0]
    return middle_strike - width, middle_strike + width


def _spread_width(chain, anchor_strike, requested_width=None):
    strikes = sorted(float(strike) for strike in chain["strike"].dropna().unique())
    if len(strikes) < 2:
        raise ValueError("Spread strategies need at least two available strikes.")
    if requested_width is not None:
        width = abs(float(requested_width))
        if width > 0:
            return width
    distances = [abs(strike - anchor_strike) for strike in strikes if strike != anchor_strike]
    return min(distances) if distances else max(anchor_strike * 0.05, 1.0)


def _validate_ordered_strikes(rows, message):
    strikes = [float(row["strike"]) for row in rows]
    if any(left >= right for left, right in zip(strikes, strikes[1:])):
        raise ValueError(message)


def _nearest_strike_row(chain, strike):
    ordered = chain.copy()
    ordered["distance_from_target"] = (ordered["strike"].astype(float) - strike).abs()
    return ordered.sort_values("distance_from_target").iloc[0].to_dict()


def _market_premium(row):
    bid = float(row.get("bid", 0) or 0)
    ask = float(row.get("ask", 0) or 0)
    last = float(row.get("lastPrice", 0) or 0)
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    return last


def _quote_value(row, column):
    try:
        value = float(row.get(column, 0) or 0)
    except (TypeError, ValueError):
        return 0.0
    return value if np.isfinite(value) and value > 0 else 0.0


def rolling_strategy_backtest(
    price_history,
    current_spot,
    legs,
    holding_days=1,
    non_overlapping=True,
    slippage_per_contract=0.0,
    transaction_cost_per_contract=0.65,
    contract_multiplier=1,
    risk_free_rate=0.04,
    dividend_yield=0.0,
    time_to_maturity=30 / 365,
    volatility_window=60,
    trading_days=252,
):
    """Run a model rolling backtest from yfinance underlying prices.

    Each entry date rebuilds the strategy with the same strike/spot ratios as
    the selected live strategy. Entry and exit option values are estimated with
    Black-Scholes and a rolling Newey-West realized-volatility proxy because
    yfinance does not provide historical option chains.
    """

    close = price_history["Close"].dropna().astype(float)
    if holding_days < 1:
        raise ValueError("holding_days must be at least 1.")
    if len(close) <= holding_days + volatility_window:
        raise ValueError("Not enough price history for rolling backtest.")
    if current_spot <= 0:
        raise ValueError("current_spot must be positive.")
    if contract_multiplier <= 0:
        raise ValueError("contract_multiplier must be positive.")
    if time_to_maturity <= 0:
        raise ValueError("time_to_maturity must be positive.")
    if volatility_window < 5:
        raise ValueError("volatility_window must be at least 5.")

    rows = []
    step = holding_days if non_overlapping else 1
    round_trip_cost = 2 * max(float(transaction_cost_per_contract), 0.0)
    slippage = max(float(slippage_per_contract), 0.0)
    log_returns = np.log(close / close.shift(1)).dropna()
    for i in range(volatility_window, len(close) - holding_days, step):
        entry_date = close.index[i]
        exit_date = close.index[i + holding_days]
        entry_spot = float(close.iloc[i])
        exit_spot = float(close.iloc[i + holding_days])
        entry_sigma = _rolling_realized_volatility(log_returns.iloc[i - volatility_window : i], trading_days)
        exit_sigma = _rolling_realized_volatility(log_returns.iloc[i + holding_days - volatility_window : i + holding_days], trading_days)
        remaining_time = time_to_maturity - holding_days / 365

        rolling_entry_legs = []
        model_entry_value = 0.0
        model_exit_value = 0.0
        gross_profit = 0.0
        for leg in legs:
            quantity = abs(int(leg.get("quantity", 1)))
            side = 1 if leg["side"] == "long" else -1
            strike = entry_spot * float(leg["strike"]) / current_spot
            entry_value = option_price_from_bs(
                entry_spot,
                strike,
                risk_free_rate,
                dividend_yield,
                entry_sigma,
                time_to_maturity,
                leg["option_kind"],
            )
            if remaining_time > 0:
                exit_value = option_price_from_bs(
                    exit_spot,
                    strike,
                    risk_free_rate,
                    dividend_yield,
                    exit_sigma,
                    remaining_time,
                    leg["option_kind"],
                )
            else:
                exit_value = _intrinsic_value(exit_spot, strike, leg["option_kind"])

            model_entry_value += side * entry_value * quantity * contract_multiplier
            model_exit_value += side * exit_value * quantity * contract_multiplier
            gross_profit += side * (exit_value - entry_value) * quantity * contract_multiplier
            gross_profit -= 2 * slippage * quantity * contract_multiplier
            rolling_entry_legs.append(
                {
                    "option_kind": leg["option_kind"],
                    "side": leg["side"],
                    "strike": strike,
                    "premium": entry_value,
                    "quantity": quantity,
                }
            )

        contracts = sum(abs(int(leg.get("quantity", 1))) for leg in legs)
        transaction_cost = round_trip_cost * contracts
        profit = gross_profit - transaction_cost
        margin = estimate_strategy_margin(rolling_entry_legs, entry_spot, contract_multiplier=contract_multiplier)
        rows.append(
            {
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_spot": entry_spot,
                "exit_spot": exit_spot,
                "historical_return": exit_spot / entry_spot - 1,
                "entry_sigma": entry_sigma,
                "exit_sigma": exit_sigma,
                "model_entry_value": model_entry_value,
                "model_exit_value": model_exit_value,
                "gross_profit": gross_profit,
                "transaction_cost": transaction_cost,
                "strategy_profit": profit,
                "margin_estimate": margin,
            }
        )

    return pd.DataFrame(rows).set_index("exit_date")


def _rolling_realized_volatility(log_returns, trading_days):
    values = pd.Series(log_returns).dropna().astype(float)
    if len(values) < 5:
        raise ValueError("Not enough returns to estimate rolling volatility.")
    lags = max(1, int(np.floor(4 * (len(values) / 100) ** (2 / 9))))
    centered = values.to_numpy() - float(values.mean())
    variance = float(np.mean(centered * centered))
    for lag in range(1, min(lags, len(centered) - 1) + 1):
        autocovariance = float(np.mean(centered[lag:] * centered[:-lag]))
        bartlett_weight = 1 - lag / (lags + 1)
        variance += 2 * bartlett_weight * autocovariance
    volatility = float(np.sqrt(max(variance, 1e-8) * trading_days))
    return max(volatility, 0.01)


def _intrinsic_value(stock_price, strike, option_kind):
    if option_kind == "call":
        return max(stock_price - strike, 0.0)
    if option_kind == "put":
        return max(strike - stock_price, 0.0)
    raise ValueError("option_kind must be 'call' or 'put'.")


def estimate_strategy_margin(legs, spot, width=0.8, contract_multiplier=1):
    grid = payoff_grid(spot, legs, width=width, points=401)
    worst_profit = float(grid["strategy_profit"].min()) * contract_multiplier
    net_debit = sum(
        (1 if leg["side"] == "long" else -1)
        * float(leg["premium"])
        * int(leg.get("quantity", 1))
        for leg in legs
    ) * contract_multiplier
    debit_margin = max(net_debit, 0.0)
    loss_margin = max(-worst_profit, 0.0)
    short_margin = _short_option_margin(legs, spot, contract_multiplier)
    return max(debit_margin, loss_margin, short_margin)


def _short_option_margin(legs, spot, contract_multiplier):
    margin = 0.0
    for leg in legs:
        if leg["side"] != "short":
            continue
        strike = float(leg["strike"])
        premium = float(leg["premium"])
        quantity = abs(int(leg.get("quantity", 1)))
        if leg["option_kind"] == "call":
            out_of_money = max(strike - spot, 0.0)
        elif leg["option_kind"] == "put":
            out_of_money = max(spot - strike, 0.0)
        else:
            continue
        risk_based = premium + max(0.20 * spot - out_of_money, 0.10 * spot)
        margin += risk_based * quantity * contract_multiplier
    return margin


def backtest_metrics(backtest, margin, initial_capital=100000, holding_days=1, trading_days=252):
    profit = backtest["strategy_profit"].astype(float)
    if profit.empty:
        raise ValueError("backtest must contain at least one row.")
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive.")
    if holding_days <= 0:
        raise ValueError("holding_days must be positive.")

    cumulative_profit = profit.cumsum()
    equity = initial_capital + cumulative_profit
    running_peak = equity.cummax()
    drawdown = equity - running_peak
    max_drawdown = float(drawdown.min())

    returns = profit / initial_capital
    returns_std = float(returns.std(ddof=1))
    sharpe_ratio = np.nan
    periods_per_year = trading_days / holding_days
    if returns_std > 0:
        sharpe_ratio = float(returns.mean() / returns_std * np.sqrt(periods_per_year))
    var_95 = float(-returns.quantile(0.05))
    tail_returns = returns[returns <= returns.quantile(0.05)]
    expected_shortfall_95 = float(-tail_returns.mean()) if not tail_returns.empty else np.nan

    return {
        "avg_pnl": float(profit.mean()),
        "total_pnl": float(profit.sum()),
        "win_rate": float((profit > 0).mean()),
        "sharpe_ratio": sharpe_ratio,
        "mdd": max_drawdown,
        "mdd_pct": float(max_drawdown / initial_capital),
        "best_scenario": float(profit.max()),
        "worst_scenario": float(profit.min()),
        "margin_estimate": float(margin),
        "return_on_margin": float(profit.mean() / margin) if margin > 0 else np.nan,
        "return_on_capital": float(profit.sum() / initial_capital),
        "var_95": var_95,
        "expected_shortfall_95": expected_shortfall_95,
        "var_95_amount": float(var_95 * initial_capital),
        "expected_shortfall_95_amount": float(expected_shortfall_95 * initial_capital),
        "ending_equity": float(equity.iloc[-1]),
        "initial_capital": float(initial_capital),
    }


def payoff_grid(spot, legs, width=0.35, points=101):
    prices = np.linspace(spot * (1 - width), spot * (1 + width), points)
    profit = strategy_profit(prices, legs)
    return pd.DataFrame({"stock_price": prices, "strategy_profit": profit})
