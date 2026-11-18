"""Cross-validate optcore against the learning implementations."""

import math

import numpy as np
import pytest

from Implied_Volatility.constant_IV import implied_volatility_bisection
from Methods.black_scholes import BS
from Methods.crr import CRR_O_n
from Option_System.analytics import black_scholes_greeks
from optcore import bs_greeks, bs_price, crr_price, implied_vol, warrant_greeks, warrant_iv, warrant_price

CASES = [
    # S, K, r, q, sigma, T
    (100, 100, 0.02, 0.00, 0.30, 0.5),
    (253, 206.52, 0.015, 0.02, 0.60, 0.25),
    (50, 70, 0.01, 0.00, 0.80, 1.0),
    (1000, 900, 0.03, 0.01, 0.25, 30 / 365),
]


@pytest.mark.parametrize("S,K,r,q,sigma,T", CASES)
def test_bs_matches_learning_version(S, K, r, q, sigma, T):
    call, put = BS(S, K, r, q, sigma, T)
    assert bs_price(S, K, r, q, sigma, T, "call") == pytest.approx(call, abs=1e-12)
    assert bs_price(S, K, r, q, sigma, T, "put") == pytest.approx(put, abs=1e-12)


def test_bs_vectorised_chain_matches_scalar_loop():
    strikes = np.linspace(60, 140, 41)
    prices = bs_price(100, strikes, 0.02, 0.01, 0.3, 0.5, "put")
    expected = [BS(100, k, 0.02, 0.01, 0.3, 0.5)[1] for k in strikes]
    assert prices.shape == strikes.shape
    np.testing.assert_allclose(prices, expected, atol=1e-12)


def test_bs_mixed_call_put_array():
    kinds = np.array(["call", "put"])
    prices = bs_price(100, 100, 0.02, 0.0, 0.3, 0.5, kinds)
    call, put = BS(100, 100, 0.02, 0.0, 0.3, 0.5)
    np.testing.assert_allclose(prices, [call, put], atol=1e-12)


def test_bs_expired_returns_intrinsic_instead_of_crashing():
    with pytest.raises(ZeroDivisionError):
        BS(100, 90, 0.02, 0.0, 0.3, 0.0)  # learning version: documents the edge case
    assert bs_price(100, 90, 0.02, 0.0, 0.3, 0.0, "call") == pytest.approx(10.0)
    assert bs_price(100, 90, 0.02, 0.0, 0.3, 0.0, "put") == 0.0
    assert bs_price(100, 90, 0.02, 0.0, 0.3, -0.01, "put") == 0.0


def test_bs_zero_vol_is_discounted_forward_intrinsic():
    expected = 100 - 90 * math.exp(-0.02 * 1.0)
    assert bs_price(100, 90, 0.02, 0.0, 0.0, 1.0, "call") == pytest.approx(expected)


@pytest.mark.parametrize("style", ["European", "American"])
@pytest.mark.parametrize("S,K,r,q,sigma,T", CASES)
def test_crr_matches_learning_version(S, K, r, q, sigma, T, style):
    call, put = CRR_O_n(S, K, r, q, sigma, T, 200, option_type=style)
    assert crr_price(S, K, r, q, sigma, T, "call", style, 200) == pytest.approx(call, abs=1e-10)
    assert crr_price(S, K, r, q, sigma, T, "put", style, 200) == pytest.approx(put, abs=1e-10)


def test_crr_european_converges_to_bs():
    bs = bs_price(100, 105, 0.02, 0.0, 0.3, 0.5, "call")
    assert crr_price(100, 105, 0.02, 0.0, 0.3, 0.5, "call", "european", 2000) == pytest.approx(bs, abs=5e-3)


def test_american_put_worth_at_least_european():
    eu = crr_price(100, 110, 0.05, 0.0, 0.3, 1.0, "put", "european")
    am = crr_price(100, 110, 0.05, 0.0, 0.3, 1.0, "put", "american")
    assert am > eu


@pytest.mark.parametrize("kind", ["call", "put"])
@pytest.mark.parametrize("S,K,r,q,sigma,T", CASES)
def test_greeks_match_learning_version(S, K, r, q, sigma, T, kind):
    expected = black_scholes_greeks(S, K, r, q, sigma, T, kind)
    got = bs_greeks(S, K, r, q, sigma, T, kind)
    for key, value in expected.items():
        assert got[key] == pytest.approx(value, rel=1e-10, abs=1e-12), key


def test_greeks_vectorised_shape():
    g = bs_greeks(100, np.array([90, 100, 110]), 0.02, 0.0, 0.3, 0.5, "call")
    assert g["delta"].shape == (3,)
    assert np.all(np.diff(g["delta"]) < 0)  # call delta falls as strike rises


@pytest.mark.parametrize("kind", ["call", "put"])
@pytest.mark.parametrize("S,K,r,q,sigma,T", CASES)
def test_iv_matches_learning_version_and_round_trips(S, K, r, q, sigma, T, kind):
    price = bs_price(S, K, r, q, sigma, T, kind)
    learning = implied_volatility_bisection(S, K, r, q, T, price, option_kind=kind)
    got = implied_vol(price, S, K, r, q, T, kind)
    assert got == pytest.approx(sigma, abs=1e-6)
    assert got == pytest.approx(learning, abs=1e-6)


def test_iv_vectorised_and_nan_for_impossible_prices():
    strikes = np.array([80.0, 100.0, 120.0, 100.0])
    sigmas = np.array([0.2, 0.3, 0.4, 0.3])
    prices = bs_price(100, strikes, 0.01, 0.0, sigmas, 0.5, "call")
    prices[3] = 0.0001  # ATM price this small would need sigma below the search range
    ivs = implied_vol(prices, 100, strikes, 0.01, 0.0, 0.5, "call")
    np.testing.assert_allclose(ivs[:3], sigmas[:3], atol=1e-6)
    assert np.isnan(ivs[3])
    assert math.isnan(implied_vol(5.0, 100, 90, 0.0, 0.0, 0.5, "call"))  # below intrinsic
    assert math.isnan(implied_vol(5.0, 100, 90, 0.0, 0.0, 0.0, "call"))  # expired


def test_crr_iv_round_trip():
    price = crr_price(100, 110, 0.03, 0.0, 0.35, 0.75, "put", "american", 150)
    iv = implied_vol(price, 100, 110, 0.03, 0.0, 0.75, "put", model="crr", style="american", steps=150)
    assert iv == pytest.approx(0.35, abs=1e-6)


def test_warrant_helpers_scale_by_ratio():
    ratio = 0.051
    option = bs_price(253, 206.52, 0.015, 0.0, 0.6, 0.25, "put")
    w = warrant_price(253, 206.52, 0.015, 0.0, 0.6, 0.25, ratio, "put")
    assert w == pytest.approx(ratio * option)
    assert warrant_iv(w, 253, 206.52, 0.015, 0.0, 0.25, ratio, "put") == pytest.approx(0.6, abs=1e-6)
    g = warrant_greeks(253, 206.52, 0.015, 0.0, 0.6, 0.25, ratio, "put")
    assert g["delta"] == pytest.approx(ratio * bs_greeks(253, 206.52, 0.015, 0.0, 0.6, 0.25, "put")["delta"])
