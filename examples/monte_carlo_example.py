"""Example script for running the Monte Carlo pricing function."""

from pathlib import Path
import sys

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from Methods.monte_carlo import Monte_Carlo


def main():
    np.random.seed(7)

    call_price, put_price, call_se, put_se = Monte_Carlo(
        S=100,
        r=0.05,
        q=0.0,
        sigma=0.2,
        T=1,
        K=100,
        num_simulations=10_000,
        num_repetitions=20,
    )

    print(f"Monte Carlo call price: {call_price:.4f} (SE {call_se:.4f})")
    print(f"Monte Carlo put price: {put_price:.4f} (SE {put_se:.4f})")


if __name__ == "__main__":
    main()
