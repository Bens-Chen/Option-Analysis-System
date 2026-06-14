import numpy as np
import pandas as pd

from Trading_Strategies.straddle import long_straddle_profit, short_straddle_profit
from Trading_Strategies.strangle import long_strangle_profit, short_strangle_profit


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


def build_strategy_legs(strategy_name, spot, chain_row, other_strike=None, other_premium=None):
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


def build_chain_strategy_legs(strategy_name, selected_row, calls, puts, other_strike=None):
    strike = float(selected_row["strike"])
    selected_kind = selected_row["option_kind"]

    if strategy_name == "Single Option":
        return [
            {
                "option_kind": selected_kind,
                "side": "long",
                "strike": strike,
                "premium": _market_premium(selected_row),
                "quantity": 1,
            }
        ]

    if strategy_name in {"Long Straddle", "Short Straddle"}:
        side = "long" if strategy_name == "Long Straddle" else "short"
        call_row = _nearest_strike_row(calls, strike)
        put_row = _nearest_strike_row(puts, strike)
        return [
            {"option_kind": "call", "side": side, "strike": float(call_row["strike"]), "premium": _market_premium(call_row), "quantity": 1},
            {"option_kind": "put", "side": side, "strike": float(put_row["strike"]), "premium": _market_premium(put_row), "quantity": 1},
        ]

    if strategy_name in {"Long Strangle", "Short Strangle"}:
        side = "long" if strategy_name == "Long Strangle" else "short"
        second = float(other_strike if other_strike is not None else strike * 1.05)
        put_strike = min(strike, second)
        call_strike = max(strike, second)
        call_row = _nearest_strike_row(calls, call_strike)
        put_row = _nearest_strike_row(puts, put_strike)
        return [
            {"option_kind": "put", "side": side, "strike": float(put_row["strike"]), "premium": _market_premium(put_row), "quantity": 1},
            {"option_kind": "call", "side": side, "strike": float(call_row["strike"]), "premium": _market_premium(call_row), "quantity": 1},
        ]

    if strategy_name in {"Long Call Butterfly", "Short Call Butterfly"}:
        lower_target, upper_target = _butterfly_outer_targets(calls, strike, other_strike)
        lower_call = _nearest_strike_row(calls, lower_target)
        middle_call = _nearest_strike_row(calls, strike)
        upper_call = _nearest_strike_row(calls, upper_target)
        middle_side = "short" if strategy_name == "Long Call Butterfly" else "long"
        wing_side = "long" if strategy_name == "Long Call Butterfly" else "short"
        return [
            {"option_kind": "call", "side": wing_side, "strike": float(lower_call["strike"]), "premium": _market_premium(lower_call), "quantity": 1},
            {"option_kind": "call", "side": middle_side, "strike": float(middle_call["strike"]), "premium": _market_premium(middle_call), "quantity": 2},
            {"option_kind": "call", "side": wing_side, "strike": float(upper_call["strike"]), "premium": _market_premium(upper_call), "quantity": 1},
        ]

    if strategy_name in {"Long Put Butterfly", "Short Put Butterfly"}:
        lower_target, upper_target = _butterfly_outer_targets(puts, strike, other_strike)
        lower_put = _nearest_strike_row(puts, lower_target)
        middle_put = _nearest_strike_row(puts, strike)
        upper_put = _nearest_strike_row(puts, upper_target)
        middle_side = "short" if strategy_name == "Long Put Butterfly" else "long"
        wing_side = "long" if strategy_name == "Long Put Butterfly" else "short"
        return [
            {"option_kind": "put", "side": wing_side, "strike": float(lower_put["strike"]), "premium": _market_premium(lower_put), "quantity": 1},
            {"option_kind": "put", "side": middle_side, "strike": float(middle_put["strike"]), "premium": _market_premium(middle_put), "quantity": 2},
            {"option_kind": "put", "side": wing_side, "strike": float(upper_put["strike"]), "premium": _market_premium(upper_put), "quantity": 1},
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


def rank_strategy_candidates(spot, historical_volatility, selected_iv, trend_signal):
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


def rolling_strategy_backtest(price_history, current_spot, legs, holding_days=1):
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

    rows = []
    for i in range(len(close) - holding_days):
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
                    "premium": entry_spot * float(leg["premium"]) / current_spot,
                    "quantity": int(leg.get("quantity", 1)),
                }
            )

        profit = float(strategy_profit([terminal_price], rolling_legs)[0])
        margin = estimate_strategy_margin(rolling_legs, entry_spot)
        rows.append(
            {
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_spot": entry_spot,
                "terminal_price": terminal_price,
                "historical_return": terminal_price / entry_spot - 1,
                "strategy_profit": profit,
                "margin_estimate": margin,
            }
        )

    return pd.DataFrame(rows).set_index("exit_date")


def rank_strategies_by_backtest(strategy_results):
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


def estimate_strategy_margin(legs, spot, width=0.8):
    grid = payoff_grid(spot, legs, width=width, points=401)
    worst_profit = float(grid["strategy_profit"].min())
    net_debit = sum(
        (1 if leg["side"] == "long" else -1)
        * float(leg["premium"])
        * int(leg.get("quantity", 1))
        for leg in legs
    )
    debit_margin = max(net_debit, 0.0)
    loss_margin = max(-worst_profit, 0.0)
    return max(debit_margin, loss_margin)


def backtest_metrics(backtest, margin):
    profit = backtest["strategy_profit"].astype(float)
    cumulative_profit = profit.cumsum()
    running_peak = cumulative_profit.cummax()
    drawdown = cumulative_profit - running_peak
    max_drawdown = float(drawdown.min())

    profit_std = float(profit.std(ddof=1))
    sharpe_ratio = np.nan
    if profit_std > 0:
        sharpe_ratio = float(profit.mean() / profit_std)

    return {
        "avg_pnl": float(profit.mean()),
        "total_pnl": float(profit.sum()),
        "win_rate": float((profit > 0).mean()),
        "sharpe_ratio": sharpe_ratio,
        "mdd": max_drawdown,
        "best_scenario": float(profit.max()),
        "worst_scenario": float(profit.min()),
        "margin_estimate": float(margin),
        "return_on_margin": float(profit.mean() / margin) if margin > 0 else np.nan,
    }


def payoff_grid(spot, legs, width=0.35, points=101):
    prices = np.linspace(spot * (1 - width), spot * (1 + width), points)
    profit = strategy_profit(prices, legs)
    return pd.DataFrame({"stock_price": prices, "strategy_profit": profit})
