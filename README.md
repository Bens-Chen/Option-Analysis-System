# Option Pricing

This repository is an educational option-pricing project. It introduces core pricing methods, calibration tools, exotic option examples, Greek-letter estimation, hedging ideas, and selected trading strategies with Python implementations.

The goal is to keep the root README as a map of the project. Detailed notes are placed inside the folder that owns the topic.

## Features

- Closed-form Black-Scholes pricing for European vanilla options
- CRR binomial tree pricing for European and American options
- Monte Carlo pricing and simulation-based Greek estimation
- Finite difference methods for option-pricing PDEs
- Exotic option examples: Asian, Lookback, and Rainbow options
- Implied volatility calibration notes and code
- Greek letters, CRR Greeks, Monte Carlo Greeks, and dynamic delta hedging
- Selected option trading strategy notes

## Installation

```bash
git clone git@github.com:Bens-Chen/Option-Pricing.git
cd Option-Pricing
pip install -r requirements.txt
```

## Quick Start

Run the pricing examples:

```bash
python examples/black_scholes_example.py
python examples/crr_example.py
python examples/monte_carlo_example.py
```

Run tests:

```bash
pytest
```

## Project Structure

```text
Calibration/
  README.md                  # implied volatility and calibration notes
  implied_volatility.py

Exotic_Options/
  README.md                  # Asian, Lookback, and Rainbow option notes
  asian_option.py
  lookback_option.py
  rainbow_option.py

Greak Letters/
  README.md                  # Greeks, hedging, and strategy notes
  CRR                        # CRR Greek calculations
  Monte-Carlo                # pathwise and likelihood Monte Carlo Greeks
  Dynamic delta hedge

Methods/
  README.md                  # core pricing method notes
  black_scholes.py
  crr.py
  finite_difference.py
  monte_carlo.py

examples/
  black_scholes_example.py
  crr_example.py
  monte_carlo_example.py

tests/
  test_black_scholes.py
  test_crr.py
```

## Reading Order

1. Start with `Methods/README.md` to understand the pricing engines.
2. Read `Calibration/README.md` for implied volatility.
3. Read `Exotic_Options/README.md` for path-dependent examples.
4. Read `Greak Letters/README.md` for Greeks, hedging, and trading strategies.
5. Check `examples/` and `tests/` to see how the code is used.

## Disclaimer

This project is for educational purposes only. It is not financial advice and should not be used as a production trading system.
