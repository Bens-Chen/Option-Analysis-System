"""Backward-compatible entrypoint for risk-management chart utilities."""

import matplotlib.pyplot as plt

from .risk_matrix import OptionLeg, build_demo_risk_matrix, build_risk_matrix, plot_risk_matrix
from .var_es import (
    ewma_var_es_summary,
    historical_expected_shortfall,
    historical_var,
    historical_var_es_summary,
    iv_smoothed_return_distribution,
    iv_smoothed_var_es_summary,
    parametric_var,
)
from .vol_curve_monitor import build_demo_vol_curves, plot_vol_curve_monitor, vol_curve_diagnostics
from .vol_tracker import build_demo_vol_tracker, plot_vol_tracker

__all__ = [
    "OptionLeg",
    "build_demo_risk_matrix",
    "build_demo_vol_curves",
    "build_demo_vol_tracker",
    "build_risk_matrix",
    "ewma_var_es_summary",
    "historical_expected_shortfall",
    "historical_var",
    "historical_var_es_summary",
    "iv_smoothed_return_distribution",
    "iv_smoothed_var_es_summary",
    "parametric_var",
    "plot_risk_matrix",
    "plot_vol_curve_monitor",
    "plot_vol_tracker",
    "show_demo_charts",
    "vol_curve_diagnostics",
]


def show_demo_charts():
    """Open all demo charts with matplotlib."""

    plot_risk_matrix(build_demo_risk_matrix())
    plot_vol_curve_monitor(build_demo_vol_curves(), expiry="2026-07-17", forward=100)
    plot_vol_tracker(build_demo_vol_tracker(), value="atm_vol", change_on_day=True)
    plt.show()


if __name__ == "__main__":
    show_demo_charts()
