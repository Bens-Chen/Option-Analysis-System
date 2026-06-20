from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from Methods.crr import CRR_O_n


def main():
    call_price, put_price = CRR_O_n(
        S=100,
        K=100,
        r=0.05,
        q=0.0,
        sigma=0.2,
        T=1,
        num_time_steps=200,
        option_type="European",
    )

    print(f"CRR European call price: {call_price:.4f}")
    print(f"CRR European put price: {put_price:.4f}")


if __name__ == "__main__":
    main()
