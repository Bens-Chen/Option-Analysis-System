import numpy as np
import pandas as pd

from Trading_Strategies.butterfly import call_butterfly_profit
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

    raise ValueError(f"Unknown strategy: {strategy_name}")


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
    elif np.isfinite(iv_ratio) and iv_ratio <= 0.9:
        add("Long Straddle", 75, "IV is low versus historical volatility, so long-volatility structures receive higher educational score.")
        add("Long Strangle", 68, "Lower premium can help, but the underlying must move farther to break even.")
    else:
        add("Single Option", 55, "IV is close to historical volatility, so the view depends more on direction and strike selection.")

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


def payoff_grid(spot, legs, width=0.35, points=101):
    prices = np.linspace(spot * (1 - width), spot * (1 + width), points)
    profit = strategy_profit(prices, legs)
    return pd.DataFrame({"stock_price": prices, "strategy_profit": profit})
