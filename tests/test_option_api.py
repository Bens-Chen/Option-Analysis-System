from fastapi.testclient import TestClient

from Methods.black_scholes import BS
from Option_System.api import app


client = TestClient(app)


def test_health_endpoint_returns_ok():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_price_endpoint_returns_price_and_greeks():
    payload = {
        "S": 100,
        "K": 100,
        "r": 0.04,
        "q": 0,
        "sigma": 0.2,
        "T": 1,
        "option_kind": "call",
    }

    response = client.post("/api/price", json=payload)
    result = response.json()
    expected_call, _ = BS(100, 100, 0.04, 0, 0.2, 1)

    assert response.status_code == 200
    assert result["model_price"] == expected_call
    assert {"delta", "gamma", "theta", "vega", "rho"} <= set(result)


def test_price_endpoint_rejects_invalid_sigma():
    response = client.post(
        "/api/price",
        json={
            "S": 100,
            "K": 100,
            "r": 0.04,
            "q": 0,
            "sigma": 0,
            "T": 1,
            "option_kind": "call",
        },
    )

    assert response.status_code == 422


def test_price_endpoint_rejects_invalid_option_kind():
    response = client.post(
        "/api/price",
        json={
            "S": 100,
            "K": 100,
            "r": 0.04,
            "q": 0,
            "sigma": 0.2,
            "T": 1,
            "option_kind": "straddle",
        },
    )

    assert response.status_code == 422
