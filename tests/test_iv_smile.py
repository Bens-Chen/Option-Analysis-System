import numpy as np

from Implied_Volatility.iv_smile import fit_svi_smile, svi_total_variance


def test_fit_svi_smile_returns_smooth_curve_and_quality_metrics():
    forward = 100.0
    T = 30 / 365
    strikes = np.array([80, 90, 95, 100, 105, 110, 120], dtype=float)
    log_moneyness = np.log(strikes / forward)
    true_params = [0.004, 0.08, -0.25, 0.0, 0.18]
    implied_volatilities = np.sqrt(svi_total_variance(log_moneyness, *true_params) / T)

    result = fit_svi_smile(strikes, implied_volatilities, forward, T)

    assert set(result["params"]) == {"a", "b", "rho", "m", "sigma"}
    assert len(result["smooth_strikes"]) == 100
    assert len(result["smooth_iv"]) == 100
    assert result["rmse"] < 0.05
    assert result["n_obs"] == len(strikes)
    assert isinstance(result["density_check"], bool)


def test_fit_svi_smile_rejects_too_few_points():
    strikes = [95, 100, 105, 110]
    implied_volatilities = [0.25, 0.22, 0.23, 0.27]

    try:
        fit_svi_smile(strikes, implied_volatilities, forward=100, T=30 / 365)
    except ValueError as exc:
        assert "At least five valid IV points" in str(exc)
    else:
        raise AssertionError("fit_svi_smile should reject fewer than five valid points.")
