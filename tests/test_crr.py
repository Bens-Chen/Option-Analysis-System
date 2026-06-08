from Methods.black_scholes import BS
from Methods.crr import CRR_O_n


def test_crr_converges_near_black_scholes_for_european_option():
    bs_call, bs_put = BS(100, 100, 0.05, 0.0, 0.2, 1)
    crr_call, crr_put = CRR_O_n(100, 100, 0.05, 0.0, 0.2, 1, 500)

    assert abs(crr_call - bs_call) < 0.05
    assert abs(crr_put - bs_put) < 0.05
