"""optcore: production-grade pricing core.

The folders Methods/, Implied_Volatility/, Greak_Letters/ keep the original
step-by-step learning implementations. optcore re-implements the same maths
in vectorised NumPy form for real systems (option chains, thousands of
warrants), and tests/test_optcore_*.py check that both give the same answers.
"""

from optcore.pricing import bs_price, crr_price
from optcore.greeks import bs_greeks
from optcore.iv import implied_vol
from optcore.warrant import warrant_price, warrant_iv, warrant_greeks

__all__ = [
    "bs_price",
    "crr_price",
    "bs_greeks",
    "implied_vol",
    "warrant_price",
    "warrant_iv",
    "warrant_greeks",
]
