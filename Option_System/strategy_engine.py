"""Strategy leg builders, payoff calculations, and scenario backtest utilities."""

import numpy as np
import pandas as pd

from Trading_Strategies.straddle import long_straddle_profit, short_straddle_profit
from Trading_Strategies.strangle import long_strangle_profit, short_strangle_profit


def option_leg_profit(stock_prices, option_kind, side, strike, premium, quantity=1):
    """Calculate one option leg's terminal profit over one or more stock prices."""

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
    """Sum all option-leg profits into a full strategy payoff."""

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


def build_strategy_legs(strategy_name, spot, chain_row, other_strike=None, other_premium=None):
    """Build simple strategy legs from one selected quote row."""

    strike = float(chain_row["strike"])
    premium = _market_premium(chain_row)
    option_kind = chain_row["option_kind"]

    if strategy_name == "Single Option":
        return [{"option_kind": option_kind, "side": "long", "strike": strike, "premium": premium, "quantity": 1}]

    if strategy_name == "Long Straddle":
        return [
            {"option_kind": "call", "side": "long", "strike": strike, "premium": premium, "quantity": 1},
            {"option_kind": "put", "side": "long", "strike": strike, "premium": premium, "quantity": 1},
        ]

    if strategy_name == "Short Straddle":
        return [
            {"option_kind": "call", "side": "short", "strike": strike, "premium": premium, "quantity": 1},
            {"option_kind": "put", "side": "short", "strike": strike, "premium": premium, "quantity": 1},
        ]

    if strategy_name == "Long Strangle":
        upper = float(other_strike or strike * 1.05)
        lower = min(strike, upper)
        upper = max(strike, upper)
        premium2 = float(other_premium if other_premium is not None else premium)
        return [
            {"option_kind": "put", "side": "long", "strike": lower, "premium": premium, "quantity": 1},
            {"option_kind": "call", "side": "long", "strike": upper, "premium": premium2, "quantity": 1},
        ]

    if strategy_name == "Short Strangle":
        upper = float(other_strike or strike * 1.05)
        lower = min(strike, upper)
        upper = max(strike, upper)
        premium2 = float(other_premium if other_premium is not None else premium)
        return [
            {"option_kind": "put", "side": "short", "strike": lower, "premium": premium, "quantity": 1},
            {"option_kind": "call", "side": "short", "strike": upper, "premium": premium2, "quantity": 1},
        ]

    raise ValueError(f"Unknown strategy: {strategy_name}")


def _option_leg_from_row(row, option_kind, side, quantity=1):
    """Normalize a yfinance option-chain row into the internal leg format."""

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
    """Build single-leg, spread, butterfly, strangle, and condor structures."""

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
    """Choose lower and upper strikes around the butterfly body strike."""

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
    """Pick the requested spread width or infer the nearest available spacing."""

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
    """Reject spread structures when quote data cannot provide ordered strikes."""

    strikes = [float(row["strike"]) for row in rows]
    if any(left >= right for left, right in zip(strikes, strikes[1:])):
        raise ValueError(message)


def _nearest_strike_row(chain, strike):
    """Find the option-chain row closest to a target strike."""

    ordered = chain.copy()
    ordered["distance_from_target"] = (ordered["strike"].astype(float) - strike).abs()
    return ordered.sort_values("distance_from_target").iloc[0].to_dict()


def _market_premium(row):
    """Use mid price when possible and fall back to last traded price."""

    bid = float(row.get("bid", 0) or 0)
    ask = float(row.get("ask", 0) or 0)
    last = float(row.get("lastPrice", 0) or 0)
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    return last


def _quote_value(row, column):
    """Read a positive quote value from a row, returning zero if unavailable."""

    try:
        value = float(row.get(column, 0) or 0)
    except (TypeError, ValueError):
        return 0.0
    return value if np.isfinite(value) and value > 0 else 0.0


def _executable_premium(leg, slippage_per_contract=0.0):
    """Approximate executable premium using ask for buys and bid for sells."""

    side = leg["side"]
    bid = float(leg.get("bid", 0) or 0)
    ask = float(leg.get("ask", 0) or 0)
    mid = float(leg.get("premium", 0) or 0)
    slippage = max(float(slippage_per_contract), 0.0)
    if side == "long":
        base = ask if ask > 0 else mid
        return max(base + slippage, 0.0)
    if side == "short":
        base = bid if bid > 0 else mid
        return max(base - slippage, 0.0)
    raise ValueError("side must be 'long' or 'short'.")


def rank_strategy_candidates(spot, historical_volatility, selected_iv, trend_signal):
    """Rank educational strategy candidates from IV level and trend context."""

    iv_ratio = selected_iv / historical_volatility if historical_volatility > 0 else np.nan
    rows = []

    def add(name, score, reason):
        rows.append({"strategy": name, "score": round(score, 2), "reason": reason})

    if np.isfinite(iv_ratio) and iv_ratio >= 1.2:
        add("Short Strangle", 75, "IV is high versus historical volatility, so premium-selling structures receive higher educational score.")
        add("Short Straddle", 65, "High IV helps option sellers, but risk is concentrated if price moves sharply.")
        add("Short Call Butterfly", 52, "High IV can make the short middle calls expensive, but butterfly risk/reward depends strongly on strike spacing.")
    elif np.isfinite(iv_ratio) and iv_ratio <= 0.9:
        add("Long Straddle", 75, "IV is low versus historical volatility, so long-volatility structures receive higher educational score.")
        add("Long Strangle", 68, "Lower premium can help, but the underlying must move farther to break even.")
        add("Long Call Butterfly", 55, "A butterfly can be reviewed when the expected terminal price is near the middle strike.")
    else:
        add("Single Option", 55, "IV is close to historical volatility, so the view depends more on direction and strike selection.")
        add("Long Call Butterfly", 58, "A butterfly fits a range-bound view around the selected middle strike with limited risk.")

    if trend_signal == "bullish":
        add("Single Option", 62, "Underlying price is above its moving average, so bullish structures can be reviewed.")
    elif trend_signal == "bearish":
        add("Single Option", 58, "Underlying price is below its moving average, so bearish structures can be reviewed.")

    return pd.DataFrame(rows).sort_values("score", ascending=False).drop_duplicates("strategy")


def moving_average_trend(price_history, short_window=20, long_window=60):
    """Classify a simple price trend from short and long moving averages."""

    close = price_history["Close"].dropna()
    if len(close) < long_window:
        return "neutral"
    short_ma = close.tail(short_window).mean()
    long_ma = close.tail(long_window).mean()
    if short_ma > long_ma:
        return "bullish"
    if short_ma < long_ma:
        return "bearish"
    return "neutral"


def historical_scenario_backtest(price_history, spot, legs, holding_days=20):
    """Apply historical holding-period returns to the current strategy payoff."""

    close = price_history["Close"].dropna().astype(float)
    returns = close.pct_change(holding_days).dropna()
    terminal_prices = spot * (1 + returns.to_numpy())
    profit = strategy_profit(terminal_prices, legs)

    return pd.DataFrame(
        {
            "historical_return": returns.to_numpy(),
            "scenario_terminal_price": terminal_prices,
            "strategy_profit": profit,
        },
        index=returns.index,
    )


def rolling_strategy_backtest(
    price_history,
    current_spot,
    legs,
    holding_days=1,
    non_overlapping=True,
    slippage_per_contract=0.0,
    transaction_cost_per_contract=0.65,
    contract_multiplier=1,
):
    """Re-enter the same relative option structure through history.

    yfinance does not provide historical option chains here, so each leg is
    scaled by current strike/spot and premium/spot. This keeps the selected
    DTE rolling through the historical stock path.
    """
    close = price_history["Close"].dropna().astype(float)
    if holding_days < 1:
        raise ValueError("holding_days must be at least 1.")
    if len(close) <= holding_days:
        raise ValueError("Not enough price history for rolling backtest.")
    if current_spot <= 0:
        raise ValueError("current_spot must be positive.")
    if contract_multiplier <= 0:
        raise ValueError("contract_multiplier must be positive.")

    rows = []
    step = holding_days if non_overlapping else 1
    round_trip_cost = 2 * max(float(transaction_cost_per_contract), 0.0)
    for i in range(0, len(close) - holding_days, step):
        entry_date = close.index[i]
        exit_date = close.index[i + holding_days]
        entry_spot = float(close.iloc[i])
        terminal_price = float(close.iloc[i + holding_days])

        rolling_legs = []
        for leg in legs:
            rolling_legs.append(
                {
                    "option_kind": leg["option_kind"],
                    "side": leg["side"],
                    "strike": entry_spot * float(leg["strike"]) / current_spot,
                    "premium": entry_spot * _executable_premium(leg, slippage_per_contract) / current_spot,
                    "quantity": int(leg.get("quantity", 1)),
                }
            )

        gross_profit = float(strategy_profit([terminal_price], rolling_legs)[0]) * contract_multiplier
        contracts = sum(abs(int(leg.get("quantity", 1))) for leg in rolling_legs)
        transaction_cost = round_trip_cost * contracts
        profit = gross_profit - transaction_cost
        margin = estimate_strategy_margin(rolling_legs, entry_spot, contract_multiplier=contract_multiplier)
        rows.append(
            {
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_spot": entry_spot,
                "terminal_price": terminal_price,
                "historical_return": terminal_price / entry_spot - 1,
                "gross_profit": gross_profit,
                "transaction_cost": transaction_cost,
                "strategy_profit": profit,
                "margin_estimate": margin,
            }
        )

    return pd.DataFrame(rows).set_index("exit_date")


def rank_strategies_by_backtest(strategy_results):
    """Rank strategies from already-computed backtest metrics."""

    rows = []
    for strategy_name, result in strategy_results.items():
        metrics = result["metrics"]
        sharpe = metrics.get("sharpe_ratio", np.nan)
        return_on_margin = metrics.get("return_on_margin", np.nan)
        mdd = metrics.get("mdd", np.nan)
        win_rate = metrics.get("win_rate", np.nan)
        score = 0.0
        if np.isfinite(sharpe):
            score += sharpe * 35
        if np.isfinite(return_on_margin):
            score += return_on_margin * 100
        if np.isfinite(win_rate):
            score += win_rate * 25
        if np.isfinite(mdd):
            score += mdd * 0.05
        rows.append(
            {
                "strategy": strategy_name,
                "score": round(float(score), 2),
                "sharpe_ratio": sharpe,
                "mdd": mdd,
                "margin_estimate": metrics.get("margin_estimate", np.nan),
                "return_on_margin": return_on_margin,
                "win_rate": win_rate,
                "avg_pnl": metrics.get("avg_pnl", np.nan),
            }
        )
    return pd.DataFrame(rows).sort_values("score", ascending=False)


def estimate_strategy_margin(legs, spot, width=0.8, contract_multiplier=1):
    """Estimate risk capital from payoff loss, debit paid, and short-option margin."""

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
    """Approximate short-option margin using a Reg-T style risk formula."""

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
    """Summarize rolling strategy P&L into common backtest risk metrics."""

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
    """Create terminal stock prices and strategy profits for payoff charts."""

    prices = np.linspace(spot * (1 - width), spot * (1 + width), points)
    profit = strategy_profit(prices, legs)
    return pd.DataFrame({"stock_price": prices, "strategy_profit": profit})
