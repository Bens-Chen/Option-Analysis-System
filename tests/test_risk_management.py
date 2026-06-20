import matplotlib
import pytest

matplotlib.use("Agg")

from Risk_Management.risk_visuals import (
    build_demo_risk_matrix,
    build_demo_vol_curves,
    build_demo_vol_tracker,
    historical_expected_shortfall,
    historical_var,
    historical_var_es_summary,
    iv_smoothed_return_distribution,
    iv_smoothed_var_es_summary,
    ewma_var_es_summary,
    parametric_var,
    plot_risk_matrix,
    plot_vol_curve_monitor,
    plot_vol_tracker,
    vol_curve_diagnostics,
)


def test_demo_risk_matrix_has_expected_columns():
    matrix = build_demo_risk_matrix()

    assert {"shock", "pnl", "delta", "gamma", "theta", "vega", "rho"}.issubset(matrix.columns)
    assert len(matrix) == 9
    assert matrix.loc[matrix["shock"].eq(0), "pnl"].iloc[0] == 0


def test_risk_matrix_plot_builds_figure():
    fig = plot_risk_matrix(build_demo_risk_matrix())

    assert len(fig.axes) == 2


def test_vol_curve_monitor_plot_builds_figure():
    fig = plot_vol_curve_monitor(build_demo_vol_curves(), expiry="2026-07-17", forward=100)

    assert len(fig.axes) == 3


def test_vol_curve_diagnostics_returns_curvature_table():
    table, summary = vol_curve_diagnostics(build_demo_vol_curves(), expiry="2026-07-17", forward=100)

    assert {"moneyness", "iv_pct", "slope_per_strike", "curvature", "abs_curvature", "curve_zone"} <= set(table.columns)
    assert summary["iv_range_pct"] > 0
    assert summary["max_abs_curvature"] >= 0


def test_vol_tracker_plot_builds_figure():
    fig = plot_vol_tracker(build_demo_vol_tracker(periods=20))

    assert len(fig.axes) == 2


def test_historical_var_and_expected_shortfall_are_positive_losses():
    returns = [-0.05, -0.03, -0.01, 0.0, 0.02]

    var = historical_var(returns, confidence_level=0.8, portfolio_value=100000)
    es = historical_expected_shortfall(returns, confidence_level=0.8, portfolio_value=100000)

    assert var == pytest.approx(3400)
    assert es == pytest.approx(5000)


def test_historical_var_es_summary_includes_tail_count():
    summary = historical_var_es_summary(
        [-0.05, -0.03, -0.01, 0.0, 0.02],
        confidence_level=0.8,
        portfolio_value=100000,
    )

    assert summary["var"] == pytest.approx(3400)
    assert summary["expected_shortfall"] == pytest.approx(5000)
    assert summary["tail_observations"] == 1


def test_parametric_var_uses_iv_smoothed_historical_returns():
    returns = [-0.04, -0.02, -0.01, 0.0, 0.01, 0.03]

    low_iv_var = parametric_var(returns, annualized_volatility=0.1, confidence_level=0.8, portfolio_value=100000)
    high_iv_var = parametric_var(returns, annualized_volatility=0.2, confidence_level=0.8, portfolio_value=100000)

    assert low_iv_var > 0
    assert high_iv_var == pytest.approx(low_iv_var * 2)


def test_iv_smoothed_return_distribution_matches_target_volatility():
    returns = [-0.04, -0.02, -0.01, 0.0, 0.01, 0.03]

    distribution = iv_smoothed_return_distribution(returns, annualized_volatility=0.2)

    assert distribution.std(ddof=1) == pytest.approx(0.2 / (252**0.5))


def test_iv_smoothed_var_es_summary_returns_scaled_tail_metrics():
    returns = [-0.04, -0.02, -0.01, 0.0, 0.01, 0.03]

    summary = iv_smoothed_var_es_summary(returns, annualized_volatility=0.2, confidence_level=0.8, portfolio_value=100000)

    assert summary["var"] > 0
    assert summary["expected_shortfall"] >= summary["var"]
    assert summary["annualized_volatility"] == pytest.approx(0.2)


def test_ewma_var_es_summary_returns_tail_metrics():
    summary = ewma_var_es_summary(
        [-0.05, -0.03, -0.01, 0.0, 0.02, -0.02, 0.01],
        confidence_level=0.8,
        portfolio_value=100000,
    )

    assert summary["var"] > 0
    assert summary["expected_shortfall"] > 0
    assert summary["tail_observations"] >= 1
