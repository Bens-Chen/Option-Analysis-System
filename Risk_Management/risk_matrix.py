"""Scenario risk matrix construction and plotting for option portfolios."""

from dataclasses import dataclass

import matplotlib.pyplot as plt
import pandas as pd

from Option_System.analytics import black_scholes_greeks, option_price_from_bs
from .utils import color_risk_matrix_table, format_number


@dataclass(frozen=True)
class OptionLeg:
    """One option position in a simple risk matrix."""

    option_kind: str
    strike: float
    quantity: int
    multiplier: int = 100


def build_risk_matrix(
    legs,
    spot,
    risk_free_rate,
    dividend_yield,
    volatility,
    time_to_maturity,
    price_shocks=None,
):
    """Calculate portfolio P&L and Greeks across underlying price shocks."""

    if price_shocks is None:
        price_shocks = [-0.40, -0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20, 0.40]

    base_value = _portfolio_value(
        legs, spot, risk_free_rate, dividend_yield, volatility, time_to_maturity
    )
    rows = []

    for shock in price_shocks:
        shocked_spot = spot * (1 + shock)
        shocked_value = _portfolio_value(
            legs, shocked_spot, risk_free_rate, dividend_yield, volatility, time_to_maturity
        )
        greeks = _portfolio_greeks(
            legs, shocked_spot, risk_free_rate, dividend_yield, volatility, time_to_maturity
        )
        rows.append(
            {
                "shock": shock,
                "underlying_price": shocked_spot,
                "pnl": shocked_value - base_value,
                **greeks,
            }
        )

    return pd.DataFrame(rows)


def plot_risk_matrix(risk_matrix, title="P&L with base price shocks"):
    """Plot a P&L scenario line and a Greeks table like a trading risk matrix."""

    table_rows = ["pnl", "delta", "gamma", "theta", "vega", "rho"]
    labels = [f"p:{shock:+.0%}" for shock in risk_matrix["shock"]]
    table_values = []
    table_numeric_values = []
    for row in table_rows:
        values = risk_matrix[row].to_numpy(dtype=float)
        if row == "pnl":
            table_values.append([format_number(value) for value in values])
            table_numeric_values.append(values)
        else:
            table_values.append([f"{value:.2f}%" for value in values])
            table_numeric_values.append(values)

    fig, (ax_line, ax_table) = plt.subplots(
        2,
        1,
        figsize=(12, 7),
        gridspec_kw={"height_ratios": [3, 1.7]},
        constrained_layout=True,
    )

    ax_line.plot(
        risk_matrix["shock"] * 100,
        risk_matrix["pnl"],
        color="#7f3b2e",
        linewidth=2.5,
        marker="o",
        markersize=4,
    )
    ax_line.axhline(0, color="#5d6d7e", linewidth=1)
    ax_line.set_title(title)
    ax_line.set_xlabel("Underlying price shock (%)")
    ax_line.set_ylabel("P&L")
    ax_line.grid(True, alpha=0.35)

    ax_table.axis("off")
    table = ax_table.table(
        cellText=table_values,
        rowLabels=table_rows,
        colLabels=labels,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.3)
    color_risk_matrix_table(table, table_rows, pd.DataFrame(table_numeric_values).to_numpy())

    return fig


def build_demo_risk_matrix():
    """Create a long-straddle-style demo risk matrix."""

    legs = [
        OptionLeg("call", strike=100, quantity=10),
        OptionLeg("put", strike=100, quantity=10),
    ]
    return build_risk_matrix(
        legs=legs,
        spot=100,
        risk_free_rate=0.04,
        dividend_yield=0.0,
        volatility=0.24,
        time_to_maturity=45 / 365,
    )


def _portfolio_value(legs, spot, risk_free_rate, dividend_yield, volatility, time_to_maturity):
    value = 0.0
    for leg in legs:
        price = option_price_from_bs(
            spot,
            leg.strike,
            risk_free_rate,
            dividend_yield,
            volatility,
            time_to_maturity,
            leg.option_kind,
        )
        value += price * leg.quantity * leg.multiplier
    return value


def _portfolio_greeks(legs, spot, risk_free_rate, dividend_yield, volatility, time_to_maturity):
    totals = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    for leg in legs:
        greeks = black_scholes_greeks(
            spot,
            leg.strike,
            risk_free_rate,
            dividend_yield,
            volatility,
            time_to_maturity,
            leg.option_kind,
        )
        scale = leg.quantity * leg.multiplier
        totals["delta"] += greeks["delta"] * scale
        totals["gamma"] += greeks["gamma"] * scale
        totals["theta"] += greeks["theta_per_day"] * scale
        totals["vega"] += greeks["vega"] * scale
        totals["rho"] += greeks["rho"] * scale
    return totals
