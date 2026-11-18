"""HTTP routes. Run with:  python -m webapp   (then open http://127.0.0.1:8000)"""

from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from webapp import services, us_services

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Option Lab")
store = services.WarrantStore()


class CalcRequest(BaseModel):
    S: float = Field(gt=0)
    K: float = Field(gt=0)
    r: float = 0.015
    q: float = 0.0
    sigma: float = Field(gt=0, le=5)
    T: float = Field(ge=0, le=30)
    kind: Literal["call", "put"] = "call"
    model: Literal["bs", "crr"] = "bs"
    style: Literal["european", "american"] = "european"
    steps: int = Field(default=200, ge=10, le=2000)
    ratio: float = Field(default=1.0, gt=0)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/calc")
def calc(req: CalcRequest):
    return services.calculate(**req.model_dump())


# ---------------------------------------------------------------- US options
def _market_data():
    from Market_Data.yfinance_data import download_price_history, fetch_option_chain

    return us_services.MarketData(fetch_option_chain, download_price_history)


market = _market_data()


def _us_call(fn, *args):
    try:
        return fn(*args)
    except (ValueError, ImportError, KeyError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class UsBase(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    expiration: Optional[str] = None
    r: float = 0.04
    q: float = 0.0
    kind: Literal["call", "put"] = "call"
    strike: float = Field(gt=0)


class Leg(BaseModel):
    option_kind: Literal["call", "put"]
    side: Literal["long", "short"]
    strike: float = Field(gt=0)
    premium: float = 0.0
    quantity: int = Field(default=1, ge=1, le=1000)


class StrategyRequest(UsBase):
    strategy: str = "Single Option"
    width: Optional[float] = Field(default=None, gt=0)
    ratio_quantity: int = Field(default=2, ge=2, le=20)
    custom_legs: Optional[list[Leg]] = None
    holding_days: int = Field(default=20, ge=1, le=252)
    initial_capital: float = Field(default=100000, gt=0)
    multiplier: int = Field(default=100, ge=1)
    commission: float = Field(default=0.65, ge=0)
    slippage: float = Field(default=0.01, ge=0)
    non_overlapping: bool = True


class RiskRequest(UsBase):
    legs: Optional[list[Leg]] = None
    holding_days: int = Field(default=20, ge=1, le=252)
    multiplier: int = Field(default=100, ge=1)


@app.get("/api/us/chain")
def us_chain(
    ticker: str = Query(min_length=1, max_length=12),
    expiration: Optional[str] = None,
    r: float = 0.04,
    q: float = 0.0,
):
    return _us_call(us_services.chain_view, market, ticker.strip().upper(), expiration, r, q)


@app.get("/api/us/surface")
def us_surface(ticker: str = Query(min_length=1, max_length=12), r: float = 0.04, q: float = 0.0,
               max_expirations: int = Query(default=8, ge=2, le=15)):
    return _us_call(us_services.iv_surface, market, ticker.strip().upper(), r, q, max_expirations)


@app.post("/api/us/strategy")
def us_strategy(req: StrategyRequest):
    if req.strategy not in us_services.STRATEGIES:
        raise HTTPException(status_code=400, detail=f"未知的策略：{req.strategy}")
    body = req.model_dump()
    body["ticker"] = req.ticker.strip().upper()
    return _us_call(us_services.strategy_backtest, market, body)


@app.post("/api/us/risk")
def us_risk(req: RiskRequest):
    body = req.model_dump()
    body["ticker"] = req.ticker.strip().upper()
    return _us_call(us_services.risk_report, market, body)


@app.post("/api/warrants/upload")
async def warrants_upload(daily: UploadFile = File(...), terms: Optional[UploadFile] = File(None)):
    allowed = {".xlsx", ".xls", ".csv"}
    for f in (daily, terms):
        if f is not None and f.filename and Path(f.filename).suffix.lower() not in allowed:
            raise HTTPException(status_code=400, detail=f"不支援的檔案格式：{f.filename}（請用 xlsx 或 csv）")
    try:
        terms_bytes = await terms.read() if terms is not None and terms.filename else None
        _, summary = store.load(
            await daily.read(), daily.filename, terms_bytes, terms.filename if terms_bytes else None
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"讀取 TEJ 檔案失敗：{exc}") from exc
    return summary


def _dataset(dataset_id):
    try:
        return store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="找不到資料集，請重新上傳") from exc


@app.get("/api/warrants/{dataset_id}/snapshot")
def warrants_snapshot(dataset_id: str, date: Optional[str] = None, r: float = 0.015):
    return services.warrant_snapshot(_dataset(dataset_id), date, r)


@app.get("/api/warrants/{dataset_id}/series")
def warrants_series(dataset_id: str, warrant_id: str, r: float = 0.015):
    try:
        return services.warrant_series(_dataset(dataset_id), warrant_id, r)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="找不到這檔權證") from exc


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
