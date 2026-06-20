"""Historical and EWMA VaR/Expected Shortfall estimators."""

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


def parametric_var(annualized_volatility, confidence_level=0.95, portfolio_value=1.0, horizon_days=1):
    """Normal-distribution VaR using annualized volatility and a day horizon."""

    from scipy.stats import norm

    if annualized_volatility <= 0:
        raise ValueError("annualized_volatility must be positive.")
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive.")
    _validate_confidence_level(confidence_level)

    horizon_volatility = annualized_volatility * np.sqrt(horizon_days / 252)
    z_score = norm.ppf(confidence_level)
    return float(z_score * horizon_volatility * portfolio_value)


def _clean_returns(returns):
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("returns must contain at least one finite value.")
    return values


def _validate_confidence_level(confidence_level):
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1.")
