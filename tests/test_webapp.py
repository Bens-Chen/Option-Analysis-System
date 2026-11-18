import io
from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from optcore import bs_price
from webapp import services, us_services
from webapp.server import app

client = TestClient(app)


def test_index_and_static_served():
    assert client.get("/").status_code == 200
    assert "Option Lab" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200


def test_calc_matches_optcore_and_scales_by_ratio():
    payload = {"S": 100, "K": 95, "r": 0.01, "q": 0, "sigma": 0.3, "T": 0.5, "kind": "put", "ratio": 0.1}
    body = client.post("/api/calc", json=payload).json()
    expected = bs_price(100, 95, 0.01, 0, 0.3, 0.5, "put")
    assert body["option_price"] == pytest.approx(expected)
    assert body["price"] == pytest.approx(0.1 * expected)
    assert len(body["curves"]["spot"]) == len(body["curves"]["now"])


def test_calc_accepts_expired_contract():
    body = client.post("/api/calc", json={"S": 110, "K": 100, "sigma": 0.3, "T": 0, "kind": "call"}).json()
    assert body["price"] == pytest.approx(10.0)


def test_calc_rejects_bad_input():
    assert client.post("/api/calc", json={"S": -1, "K": 100, "sigma": 0.3, "T": 1}).status_code == 422


# ---------------------------------------------------------------- US chain with fake yfinance
def _fake_chain_factory(spot=100.0, sigma=0.25, r=0.04, T_days=30):
    T = T_days / 365
    strikes = np.arange(80, 121, 5.0)

    def side(kind):
        mid = bs_price(spot, strikes, r, 0.0, sigma, T, kind)
        return pd.DataFrame({
            "contractSymbol": [f"X{kind[0].upper()}{k:.0f}" for k in strikes],
            "strike": strikes, "bid": mid - 0.05, "ask": mid + 0.05, "lastPrice": mid,
            "volume": 10, "openInterest": 100, "impliedVolatility": sigma,
        })

    exps = ["2026-01-02", "2026-01-31"]  # with today=2026-01-01: 1 day and 30 days out

    def fetch_chain(ticker, expiration=None):
        exp = expiration or exps[0]
        return {"ticker": ticker, "expiration": exp, "expirations": exps, "calls": side("call"), "puts": side("put")}

    def fetch_history(ticker, period="10y"):
        rng = np.random.default_rng(1)
        close = spot * np.exp(np.cumsum(rng.normal(0, 0.015, 400)))
        close = close * spot / close[-1]
        return pd.DataFrame({"Close": close}, index=pd.bdate_range("2024-06-03", periods=400))

    return fetch_chain, fetch_history


@pytest.fixture
def fake_market():
    fetch_chain, fetch_history = _fake_chain_factory()
    return us_services.MarketData(fetch_chain, fetch_history, today=date(2026, 1, 1))


def test_us_chain_recovers_iv_and_skips_one_day_expiry(fake_market):
    data = us_services.chain_view(fake_market, "XYZ", None, 0.04, 0.0)
    assert data["expiration"] == "2026-01-31"  # first expiry >= 7 days
    assert data["spot"] == pytest.approx(100.0)
    ivs = [row["iv"] for row in data["calls"]]
    assert ivs == pytest.approx([0.25] * len(ivs), abs=1e-6)
    assert data["forward"] == pytest.approx(100 * np.exp(0.04 * 30 / 365), rel=1e-3)
    assert data["smile"]["svi"] is not None  # flat smile fits easily
    assert "Long Straddle" in data["strategies"]


@pytest.mark.parametrize("strategy,n_legs", [
    ("Single Option", 1), ("Long Straddle", 2), ("Long Call Butterfly", 3), ("Short Iron Condor", 4),
])
def test_strategy_backtest(fake_market, strategy, n_legs):
    req = dict(ticker="XYZ", expiration=None, r=0.04, q=0.0, kind="call", strike=100.0, strategy=strategy,
               width=None, ratio_quantity=2, custom_legs=None, holding_days=10, initial_capital=100000,
               multiplier=100, commission=0.65, slippage=0.01, non_overlapping=True)
    out = us_services.strategy_backtest(fake_market, req)
    assert len(out["legs"]) == n_legs
    assert len(out["backtest"]) > 10
    assert out["sigma"] == pytest.approx(0.25, abs=1e-6)  # contract's own IV
    assert set(out["metrics"]) >= {"total_pnl", "sharpe_ratio", "mdd"}
    if strategy == "Long Straddle":
        assert abs(out["greeks"]["delta"]) < 0.2 and out["greeks"]["gamma"] > 0


def test_custom_strategy_and_risk(fake_market):
    legs = [{"option_kind": "call", "side": "long", "strike": 100.0, "premium": 3.0, "quantity": 1},
            {"option_kind": "call", "side": "short", "strike": 110.0, "premium": 1.0, "quantity": 1}]
    req = dict(ticker="XYZ", expiration=None, r=0.04, q=0.0, kind="call", strike=100.0, strategy="Custom",
               width=None, ratio_quantity=2, custom_legs=legs, holding_days=10, initial_capital=100000,
               multiplier=100, commission=0.0, slippage=0.0, non_overlapping=True)
    assert us_services.strategy_backtest(fake_market, req)["net_premium"] == pytest.approx(2.0)

    risk = us_services.risk_report(fake_market, dict(ticker="XYZ", expiration=None, r=0.04, q=0.0, kind="call",
                                                     strike=100.0, legs=legs, holding_days=10, multiplier=100))
    zero = next(row for row in risk["matrix"] if row["shock"] == 0)
    assert zero["pnl"] == pytest.approx(0.0)
    up = max(risk["matrix"], key=lambda row: row["shock"])
    assert up["pnl"] > 0  # bull call spread gains when the stock rises
    assert risk["var"]["historical"]["var"] > 0
    assert risk["curve"]["summary"]["atm_iv_pct"] == pytest.approx(25.0, abs=0.01)


def test_iv_surface(fake_market):
    out = us_services.iv_surface(fake_market, "XYZ", 0.04, 0.0, max_expirations=2)
    # 2026-01-02 is 1 day out and is skipped; only the 30-day expiry remains.
    assert {n["expiration"] for n in out["nodes"]} == {"2026-01-31"}


def test_strategy_endpoint_rejects_unknown_strategy():
    body = {"ticker": "XYZ", "strike": 100, "strategy": "Moon Shot"}
    assert client.post("/api/us/strategy", json=body).status_code == 400


# ---------------------------------------------------------------- warrants upload flow
def _tej_daily_csv():
    rows = []
    for i, d in enumerate(pd.date_range("2026-09-01", periods=5, freq="B")):
        for wid, name, strike, kind in (("03001T", "啟碁台新5A售02", 206.52, "put"), ("030999", "啟碁元大5A購01", 260.0, "call")):
            S = 250 + i
            ratio = 0.05
            price = round(ratio * bs_price(S, strike, 0.015, 0, 0.6, (60 - i) / 365, kind), 2)
            rows.append({
                "名稱": name, "權證碼": wid, "日期": d.strftime("%Y/%m/%d"), "權證收盤價(元)": price,
                "當日成交量": 0 if i == 2 else 15, "隱含波動": 0.6, "歷史波動性": 0.5, "履約價(元)": strike,
                "剩餘期間(日)": 60 - i, "DELTA": 0.0, "標的證券價格(元)": S, "標的證券": "6285   啟碁",
            })
    return pd.DataFrame(rows).to_csv(index=False).encode()


def _tej_terms_csv():
    rows = []
    for wid, name, strike, wtype in (("03001T", "啟碁台新5A售02", 206.52, "單一個股之歐式認售權證"), ("030999", "啟碁元大5A購01", 260.0, "單一個股之美式認購權證")):
        rows.append({"名稱": name, "權證碼": wid, "事件日": "2026/04/15", "序號": 1, "標的證券碼": "6285.TW 啟碁",
                     "事件說明": "發行", "權證類型": wtype, "到期日": "2026/12/31", "目前履約價(元)": strike, "目前行使比例": 0.05,
                     "行使比例": 0.05, "履約價(元)": strike, "發行日波動率": 70.0})
    return pd.DataFrame(rows).to_csv(index=False).encode()


def test_warrant_upload_snapshot_and_series():
    files = {"daily": ("daily.csv", io.BytesIO(_tej_daily_csv())), "terms": ("terms.csv", io.BytesIO(_tej_terms_csv()))}
    summary = client.post("/api/warrants/upload", files=files).json()
    assert summary["warrants"] == 2 and summary["has_terms"] is True
    assert summary["issuers"] == ["元大", "台新"]
    ds = summary["dataset_id"]

    snap = client.get(f"/api/warrants/{ds}/snapshot").json()
    assert snap["as_of"] == "2026-09-07"
    ivs = {r["warrant_id"]: r["iv"] for r in snap["rows"]}
    # Prices were rounded to 0.01 so IV is only approximately 0.6.
    assert ivs["030999"] == pytest.approx(0.6, abs=0.02)
    assert ivs["03001T"] == pytest.approx(0.6, abs=0.1)

    series = client.get(f"/api/warrants/{ds}/series", params={"warrant_id": "030999"}).json()
    assert len(series["rows"]) == 5
    assert [r["traded"] for r in series["rows"]] == [True, True, False, True, True]


def test_warrant_upload_without_terms_still_works():
    files = {"daily": ("daily.csv", io.BytesIO(_tej_daily_csv()))}
    summary = client.post("/api/warrants/upload", files=files).json()
    assert summary["has_terms"] is False
    snap = client.get(f"/api/warrants/{summary['dataset_id']}/snapshot").json()
    assert all(r["iv"] is None for r in snap["rows"])  # no ratio -> no own IV
    assert {r["kind"] for r in snap["rows"]} == {"call", "put"}  # parsed from name


def test_warrant_errors():
    bad = {"daily": ("notes.txt", io.BytesIO(b"x"))}
    assert client.post("/api/warrants/upload", files=bad).status_code == 400
    assert client.get("/api/warrants/nope/snapshot").status_code == 404
