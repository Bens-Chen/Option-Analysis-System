"""Volatility curve smoothing, curvature checks, and monitor plotting."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline


def build_demo_vol_curves():
    """Build synthetic implied volatility curves for curve-monitor examples."""

    strikes = np.array([80, 85, 90, 95, 100, 105, 110, 115, 120], dtype=float)
    expiries = ["2026-07-17", "2026-08-21", "2026-09-18", "2026-12-18"]
    rows = []
    for i, expiry in enumerate(expiries):
        base = 0.205 + i * 0.012
        skew = -0.0018 + i * 0.0002
        smile = 0.000055 + i * 0.000004
        for strike in strikes:
            iv = base + skew * (strike - 100) + smile * (strike - 100) ** 2
            rows.append({"expiry": expiry, "strike": strike, "implied_volatility": iv})
    return pd.DataFrame(rows)


def plot_vol_curve_monitor(curves, expiry=None, forward=None):
    """Plot one vol curve in detail and compare curves across expiries."""

    if expiry is None:
        expiry = str(curves["expiry"].iloc[0])
    selected = curves[curves["expiry"] == expiry].sort_values("strike")
    if selected.empty:
        raise ValueError("expiry was not found in curves.")
    if forward is None:
        forward = float(selected["strike"].median())

    strikes = selected["strike"].to_numpy(dtype=float)
    iv = selected["implied_volatility"].to_numpy(dtype=float)
    spline = CubicSpline(strikes, iv, bc_type="natural")
    fine_strikes = np.linspace(strikes.min(), strikes.max(), 200)
    fine_iv = spline(fine_strikes)
    curvature = spline(fine_strikes, 2)

    fig, (ax_curve, ax_compare) = plt.subplots(
        2,
        1,
        figsize=(12, 8),
        gridspec_kw={"height_ratios": [3, 1.5]},
        constrained_layout=True,
    )

    ax_curve.plot(fine_strikes, fine_iv * 100, color="#8d99ae", linewidth=2, label="Smoothed IV")
    ax_curve.scatter(strikes, iv * 100, color="#5c677d", zorder=3, label="Market IV nodes")
    ax_curve.axvline(forward, color="#7f3b2e", linestyle="--", linewidth=1.5, label="Forward")
    ax_curve.set_title(f"Spline Curvature - {expiry}")
    ax_curve.set_xlabel("Strike")
    ax_curve.set_ylabel("Implied volatility (%)")
    ax_curve.grid(True, alpha=0.3)

    ax_curvature = ax_curve.twinx()
    ax_curvature.plot(fine_strikes, curvature, color="#2a9d8f", alpha=0.45, linewidth=1.5, label="Curvature")
    ax_curvature.set_ylabel("Curvature")
    curve_handles, curve_labels = ax_curve.get_legend_handles_labels()
    curvature_handles, curvature_labels = ax_curvature.get_legend_handles_labels()
    ax_curve.legend(curve_handles + curvature_handles, curve_labels + curvature_labels, loc="best")
    ax_curve.text(
        0.01,
        0.02,
        "Smoothed IV: fitted curve through observed nodes. Curvature: local smile bend; spikes often mean noisy or sparse strikes.",
        transform=ax_curve.transAxes,
        fontsize=8,
        color="#3d405b",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "alpha": 0.78, "edgecolor": "#d6d6d6"},
    )

    for name, group in curves.groupby("expiry"):
        group = group.sort_values("strike")
        ax_compare.plot(
            group["strike"],
            group["implied_volatility"] * 100,
            marker="o",
            linewidth=1.8,
            label=str(name),
        )
    ax_compare.axvline(forward, color="#7f3b2e", linestyle="--", linewidth=1)
    ax_compare.set_title("Curve Comparison")
    ax_compare.set_xlabel("Strike")
    ax_compare.set_ylabel("IV (%)")
    ax_compare.grid(True, alpha=0.3)
    ax_compare.legend(ncol=2, fontsize=8)

    return fig
