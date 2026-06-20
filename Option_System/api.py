from pathlib import Path
import sys

from fastapi import FastAPI
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Option_System.analytics import black_scholes_greeks, option_price_from_bs


app = FastAPI(title="Option System API")


class PriceRequest(BaseModel):
    S: float = Field(gt=0)
    K: float = Field(gt=0)
    r: float
    q: float = 0.0
    sigma: float = Field(gt=0)
    T: float = Field(gt=0)
    option_kind: str = Field(pattern="^(call|put)$")


class PriceResponse(BaseModel):
    model_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/price", response_model=PriceResponse)
def price(request: PriceRequest):
    model_price = option_price_from_bs(
        request.S,
        request.K,
        request.r,
        request.q,
        request.sigma,
        request.T,
        request.option_kind,
    )
    greeks = black_scholes_greeks(
        request.S,
        request.K,
        request.r,
        request.q,
        request.sigma,
        request.T,
        request.option_kind,
    )
    return PriceResponse(
        model_price=model_price,
        delta=greeks["delta"],
        gamma=greeks["gamma"],
        theta=greeks["theta_per_day"],
        vega=greeks["vega"],
        rho=greeks["rho"],
    )
