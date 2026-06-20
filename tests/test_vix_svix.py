import importlib.util
import math
from importlib.machinery import SourceFileLoader
from pathlib import Path


def load_vix_svix_module():
    module_path = Path(__file__).resolve().parents[1] / "Implied_Volatility" / "vix_svix"
    loader = SourceFileLoader("test_vix_svix_module", str(module_path))
    spec = importlib.util.spec_from_loader("test_vix_svix_module", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_estimate_forward_price_from_put_call_parity_uses_closest_pair():
    module = load_vix_svix_module()

    result = module.estimate_forward_price_from_put_call_parity(
        r=0.04,
        T=30 / 365,
        K_list=[95, 100, 105],
        call_price_list=[8.0, 5.2, 3.0],
        put_price_list=[2.0, 4.9, 7.5],
    )

    expected_forward = 100 + math.exp(0.04 * 30 / 365) * (5.2 - 4.9)
    assert result["reference_strike"] == 100
    assert result["F"] == expected_forward


def test_vix_svix_uses_put_call_parity_forward_when_f_is_missing():
    module = load_vix_svix_module()

    result = module.VIX_SVIX(
        St=100,
        r=0.04,
        T=30 / 365,
        K_list=[95, 100, 105],
        call_price_list=[8.0, 5.2, 3.0],
        put_price_list=[2.0, 4.9, 7.5],
    )

    expected_forward = 100 + math.exp(0.04 * 30 / 365) * (5.2 - 4.9)
    assert result["forward"]["F"] == expected_forward
    assert result["VIX"]["F"] == expected_forward
    assert result["SVIX"]["F"] == expected_forward
