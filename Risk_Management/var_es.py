import numpy as np


def historical_var(returns, confidence_level=0.95, portfolio_value=1.0):
    """Historical VaR from a return series.

    Returns a positive loss amount. For example, with portfolio_value=100000,
    a result of 2500 means a 2,500 currency-unit VaR.
    """

    returns = _clean_returns(returns)
    _validate_confidence_level(confidence_level)
    percentile = 1 - confidence_level
    tail_return = np.quantile(returns, percentile)
    return float(-tail_return * portfolio_value)


def historical_expected_shortfall(returns, confidence_level=0.95, portfolio_value=1.0):
    """Historical Expected Shortfall from a return series.

    Expected Shortfall is the average loss after the VaR threshold is breached.
    """

    returns = _clean_returns(returns)
    _validate_confidence_level(confidence_level)
    percentile = 1 - confidence_level
    tail_return = np.quantile(returns, percentile)
    tail_returns = returns[returns <= tail_return]
    return float(-np.mean(tail_returns) * portfolio_value)


def historical_var_es_summary(returns, confidence_level=0.95, portfolio_value=1.0):
    """Return VaR, Expected Shortfall, and the tail return cutoff together."""

    returns = _clean_returns(returns)
    _validate_confidence_level(confidence_level)
    percentile = 1 - confidence_level
    tail_return = np.quantile(returns, percentile)
    tail_returns = returns[returns <= tail_return]
    return {
        "confidence_level": float(confidence_level),
        "portfolio_value": float(portfolio_value),
        "tail_return": float(tail_return),
        "var": float(-tail_return * portfolio_value),
        "expected_shortfall": float(-np.mean(tail_returns) * portfolio_value),
        "tail_observations": int(len(tail_returns)),
    }


def ewma_var_es_summary(
    returns,
    confidence_level=0.95,
    portfolio_value=1.0,
    lambda_=0.94,
):
    """Filtered historical VaR/ES using EWMA volatility scaling."""

    returns = _clean_returns(returns)
    _validate_confidence_level(confidence_level)
    if not 0 < lambda_ < 1:
        raise ValueError("lambda_ must be between 0 and 1.")
    if returns.size < 3:
        raise ValueError("returns must contain at least three finite values.")

    variance = np.empty_like(returns)
    variance[0] = returns.var(ddof=1)
    for i in range(1, returns.size):
        variance[i] = lambda_ * variance[i - 1] + (1 - lambda_) * returns[i - 1] ** 2
    volatility = np.sqrt(np.maximum(variance, 1e-12))
    current_volatility = float(volatility[-1])
    filtered_returns = returns / volatility * current_volatility
    percentile = 1 - confidence_level
    tail_return = np.quantile(filtered_returns, percentile)
    tail_returns = filtered_returns[filtered_returns <= tail_return]
    return {
        "confidence_level": float(confidence_level),
        "portfolio_value": float(portfolio_value),
        "lambda": float(lambda_),
        "current_volatility": current_volatility,
        "tail_return": float(tail_return),
        "var": float(-tail_return * portfolio_value),
        "expected_shortfall": float(-np.mean(tail_returns) * portfolio_value),
        "tail_observations": int(len(tail_returns)),
    }


def parametric_var(
    returns,
    annualized_volatility,
    confidence_level=0.95,
    portfolio_value=1.0,
    horizon_days=1,
    trading_days=252,
):
    """VaR from historical daily returns scaled to the current implied volatility."""

    smoothed_returns = iv_smoothed_return_distribution(
        returns,
        annualized_volatility=annualized_volatility,
        horizon_days=horizon_days,
        trading_days=trading_days,
    )
    _validate_confidence_level(confidence_level)
    tail_return = np.quantile(smoothed_returns, 1 - confidence_level)
    return float(-tail_return * portfolio_value)


def iv_smoothed_var_es_summary(
    returns,
    annualized_volatility,
    confidence_level=0.95,
    portfolio_value=1.0,
    horizon_days=1,
    trading_days=252,
):
    """VaR/ES from historical returns scaled to the current implied volatility."""

    smoothed_returns = iv_smoothed_return_distribution(
        returns,
        annualized_volatility=annualized_volatility,
        horizon_days=horizon_days,
        trading_days=trading_days,
    )
    _validate_confidence_level(confidence_level)
    percentile = 1 - confidence_level
    tail_return = np.quantile(smoothed_returns, percentile)
    tail_returns = smoothed_returns[smoothed_returns <= tail_return]
    return {
        "confidence_level": float(confidence_level),
        "portfolio_value": float(portfolio_value),
        "annualized_volatility": float(annualized_volatility),
        "horizon_days": int(horizon_days),
        "tail_return": float(tail_return),
        "var": float(-tail_return * portfolio_value),
        "expected_shortfall": float(-np.mean(tail_returns) * portfolio_value),
        "tail_observations": int(len(tail_returns)),
    }


def iv_smoothed_return_distribution(
    returns,
    annualized_volatility,
    horizon_days=1,
    trading_days=252,
):
    """Scale the empirical daily-return distribution to a target annualized IV."""

    returns = _clean_returns(returns)
    if returns.size < 2:
        raise ValueError("returns must contain at least two finite values.")
    if annualized_volatility <= 0:
        raise ValueError("annualized_volatility must be positive.")
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive.")
    if trading_days <= 0:
        raise ValueError("trading_days must be positive.")

    centered_returns = returns - float(np.mean(returns))
    realized_daily_volatility = float(np.std(centered_returns, ddof=1))
    if realized_daily_volatility <= 0 or not np.isfinite(realized_daily_volatility):
        raise ValueError("returns must have positive realized volatility.")

    target_horizon_volatility = annualized_volatility * np.sqrt(horizon_days / trading_days)
    return centered_returns / realized_daily_volatility * target_horizon_volatility


def _clean_returns(returns):
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("returns must contain at least one finite value.")
    return values


def _validate_confidence_level(confidence_level):
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1.")
