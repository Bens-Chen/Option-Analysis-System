# Risk Management

This folder contains notes and chart utilities for option-trading risk management.

## VaR & Expected Shortfall

VaR estimates the loss threshold at a chosen confidence level. For example,
95% one-day VaR asks: "what loss should only be exceeded about 5% of the time?"

Expected Shortfall, also called CVaR, focuses on the average loss after VaR is
breached. It is usually more informative for option portfolios because short
options and volatility positions can have fat-tail losses.

`var_es.py` provides:

- `historical_var`: historical simulation VaR from returns
- `historical_expected_shortfall`: average loss after the VaR cutoff
- `historical_var_es_summary`: VaR, ES, cutoff return, and tail count together
- `iv_smoothed_return_distribution`: historical daily simple returns converted to log returns, scaled to current annualized IV, then converted back to simple returns
- `iv_smoothed_var_es_summary`: VaR and ES from the IV-smoothed return distribution
- `parametric_var`: VaR from the IV-smoothed historical-return distribution

The functions return positive loss numbers. If `portfolio_value=100000` and
`var=3000`, the interpretation is that the historical loss threshold is about
3,000 currency units at the chosen confidence level.

The IV-smoothed method keeps the empirical shape of historical daily returns,
including skew and fat tails, but rescales the log-return distribution so its
volatility matches the current implied-volatility input. It converts the scaled
log returns back to simple returns before calculating loss amounts, so the final
VaR and ES remain direct portfolio-value losses.

## Movement Risk - Risk Matrix

Movement risk measures how the portfolio changes when the underlying price
moves. A risk matrix keeps volatility, interest rate, dividend yield, and time
to maturity fixed, then shocks the underlying price across a scenario grid.

`risk_matrix.py` provides:

- `OptionLeg`: describes one option position
- `build_risk_matrix`: calculates P&L and aggregate Greeks across shocks
- `plot_risk_matrix`: draws the P&L curve and Greeks table

Interpretation:

- P&L shows how much the portfolio gains or loses under each price shock.
- Delta shows first-order exposure to the underlying price.
- Gamma shows how quickly delta changes when the underlying moves.
- Theta shows daily time decay.
- Vega shows sensitivity to a 1 volatility-point change.
- Rho shows sensitivity to a 1 basis-point rate change.

The demo position is a long straddle, so the P&L curve tends to improve when
the underlying moves far away from the strike and lose value near the current
spot after paying option premium.

## Skew Risk & Term Structure - Curve Monitor

Skew risk appears when implied volatility is not flat across strikes. Term
structure risk appears when implied volatility differs across expiries.

`vol_curve_monitor.py` provides:

- `build_demo_vol_curves`: creates sample volatility curves
- `plot_vol_curve_monitor`: draws one selected curve, its spline curvature, and
  a comparison across expiries

The top chart is useful for one expiry. The curvature line highlights where the
smile bends more sharply. The bottom chart compares expiries so you can see
whether front-month or back-month volatility is richer at the same strike.


## Node Risk

Node risk is the risk that a specific strike or maturity point moves differently
from the rest of the volatility surface. For example, the 90% moneyness put may
become expensive because crash protection demand rises, while ATM volatility
barely moves.

In practice, node risk is monitored by comparing:

- IV change at each strike
- IV change at each expiry
- node ratio versus ATM volatility
- curve slope and curvature around important strikes

## Volatility Curve- Volatility Tracker

The volatility tracker records how volatility and underlying price change
through time. It is useful when several underlyings or expiries need to be
monitored together.

`vol_tracker.py` provides:

- `build_demo_vol_tracker`: creates sample intraday vol and price observations
- `plot_vol_tracker`: plots ATM volatility or underlying price through time

Use `value="atm_vol"` to monitor volatility and `value="underlying_price"` to
monitor the futures or stock price. Use `change_on_day=True` to display the
change since the first observation instead of the absolute level.
