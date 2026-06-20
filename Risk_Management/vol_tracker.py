"""Volatility time-series tracker for realized-volatility monitoring."""

from datetime import datetime, timedelta

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def build_demo_vol_tracker(periods=120):
    """Create demo intraday changes for ATM vol and underlying prices."""

    times = [datetime(2026, 6, 18, 9, 30) + timedelta(minutes=3 * i) for i in range(periods)]
    rng = np.random.default_rng(7)
    rows = []
    instruments = [
        ("ES", "2026-09-18", 0.23, 5900),
        ("NQ", "2026-09-18", 0.27, 21400),
    ]

    for symbol, expiry, base_vol, base_price in instruments:
        vol_change = np.cumsum(rng.normal(0, 0.002, periods))
        price_change = np.cumsum(rng.normal(0, 0.0012, periods))
        jump_index = periods // 2
        vol_change[jump_index:] -= 0.025 if symbol == "ES" else 0.018
        price_change[jump_index:] += 0.004 if symbol == "ES" else 0.003
        for time, vol_move, price_move in zip(times, vol_change, price_change):
            rows.append(
                {
                    "timestamp": time,
                    "underlying": symbol,
                    "expiry": expiry,
                    "atm_vol": base_vol + vol_move,
                    "underlying_price": base_price * (1 + price_move),
                }
            )
    return pd.DataFrame(rows)


def plot_vol_tracker(tracker, value="atm_vol", change_on_day=True):
    """Plot vol or underlying changes for several underlyings/expiries."""

    if value not in {"atm_vol", "underlying_price"}:
        raise ValueError("value must be 'atm_vol' or 'underlying_price'.")

    fig, (ax_line, ax_table) = plt.subplots(
        2,
        1,
        figsize=(13, 7),
        gridspec_kw={"height_ratios": [3, 1]},
        constrained_layout=True,
    )

    summary_rows = []
    for (underlying, expiry), group in tracker.groupby(["underlying", "expiry"]):
        group = group.sort_values("timestamp")
        series = group[value].astype(float)
        plotted = series - series.iloc[0] if change_on_day else series
        if value == "atm_vol":
            plotted = plotted * 100
        label = f"{underlying} {expiry}"
        ax_line.plot(group["timestamp"], plotted, linewidth=1.8, label=label)
        summary_rows.append(
            {
                "underlying": underlying,
                "expiry": expiry,
                "current": series.iloc[-1],
                "change": series.iloc[-1] - series.iloc[0],
                "min": series.min(),
                "max": series.max(),
            }
        )

    axis_label = "ATM vol change (vol pts)" if value == "atm_vol" and change_on_day else value
    ax_line.set_title("Vol Curve - Vol Tracker")
    ax_line.set_xlabel("Time")
    ax_line.set_ylabel(axis_label)
    ax_line.grid(True, alpha=0.3)
    ax_line.legend(loc="best")
    ax_line.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    summary = pd.DataFrame(summary_rows)
    ax_table.axis("off")
    table_text = summary.copy()
    for column in ["current", "change", "min", "max"]:
        scale = 100 if value == "atm_vol" else 1
        table_text[column] = table_text[column].map(lambda number: f"{number * scale:,.3f}")
    table = ax_table.table(
        cellText=table_text.to_numpy(),
        colLabels=table_text.columns,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.2)

    return fig
