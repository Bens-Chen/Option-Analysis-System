"""Shioaji downloader tests against a fake API (no network, no credentials)."""

from types import SimpleNamespace

import pandas as pd
import pytest

from optcore.data.shioaji_source import ShioajiDownloader, is_warrant_of, run, to_frame


def _contract(code, name, **kw):
    return SimpleNamespace(code=code, name=name, exchange="TSE", reference=1.0, limit_up=1.1, limit_down=0.9,
                           update_date="2026/11/12", **kw)


def _ns(ts):
    return int(pd.Timestamp(ts).value)


class FakeAPI:
    """Mimics the parts of shioaji.Shioaji the downloader uses; charges bytes per call."""

    def __init__(self, tick_cost=600_000, kbar_cost=30_000, limit=500_000_000):
        tsmc = _contract("2330", "台積電")
        self.warrants = [
            _contract("03011T", "台積電凱基67售14"),
            _contract("030156", "台積電永豐64購15"),
            _contract("030157", "台積電永豐64購16"),
        ]
        others = [_contract("2317", "鴻海"), _contract("03999A", "鴻海元大5A購01"), _contract("2330X", "台積電ADR")]
        self.Contracts = SimpleNamespace(Stocks=_Stocks({c.code: c for c in [tsmc, *self.warrants, *others]}))
        self.bytes, self.limit = 0, limit
        self.tick_cost, self.kbar_cost = tick_cost, kbar_cost
        self.calls = []
        self.days = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12"]
        self.volume = {"03011T": 5, "030156": 50, "030157": 0}

    def usage(self):
        return SimpleNamespace(bytes=self.bytes, remaining_bytes=self.limit - self.bytes)

    def kbars(self, contract, start, end):
        self.calls.append(("kbars", contract.code, start, end))
        self.bytes += self.kbar_cost
        days = [d for d in self.days if start <= d <= end]
        def vol(d):
            if contract.code == "2330":
                return 1000
            v = self.volume.get(contract.code, 0)
            return v.get(d, 0) if isinstance(v, dict) else v

        return SimpleNamespace(
            ts=[_ns(f"{d} 09:01") for d in days], Open=[1.0] * len(days), High=[1.0] * len(days),
            Low=[1.0] * len(days), Close=[1.0] * len(days), Volume=[vol(d) for d in days], Amount=[1.0] * len(days),
        )

    def ticks(self, contract, date):
        self.calls.append(("ticks", contract.code, date))
        self.bytes += self.tick_cost
        return SimpleNamespace(ts=[_ns(f"{date} 10:00:01")], close=[0.97], volume=[2], bid_price=[0.87],
                               bid_volume=[499], ask_price=[0.97], ask_volume=[8], tick_type=[1])


class _Stocks(dict):
    @property
    def TSE(self):
        return list(self.values())

    @property
    def OTC(self):
        return []


def test_is_warrant_of_requires_issuer_after_underlying():
    assert is_warrant_of(_contract("03011T", "台積電凱基67售14"), "台積電")
    assert not is_warrant_of(_contract("2330X", "台積電ADR"), "台積電")
    assert not is_warrant_of(_contract("03999A", "鴻海元大5A購01"), "台積電")


def test_to_frame_converts_shioaji_timestamps_to_local_time():
    res = SimpleNamespace(ts=[_ns("2026-11-11 09:48:00")], Open=[1], High=[1], Low=[1], Close=[1], Volume=[1], Amount=[1])
    df = to_frame(res, ["ts", "Open", "High", "Low", "Close", "Volume", "Amount"])
    assert df["datetime"].iloc[0] == pd.Timestamp("2026-11-11 09:48:00")


def test_kbars_only_fetches_missing_range(tmp_path):
    api = FakeAPI()
    dl = ShioajiDownloader(api, tmp_path, throttle=0)
    stock = api.Contracts.Stocks["2330"]
    assert dl.kbars(stock, "2026-11-10", "2026-11-11") == 2
    assert dl.kbars(stock, "2026-11-10", "2026-11-11") == 0  # cached
    dl.kbars(stock, "2026-11-09", "2026-11-12")
    assert api.calls[-2:] == [("kbars", "2330", "2026-11-09", "2026-11-09"), ("kbars", "2330", "2026-11-12", "2026-11-12")]
    assert len(dl.read_kbars("2330")) == 4


def test_run_downloads_contracts_kbars_and_top_ticks(tmp_path):
    api = FakeAPI()
    summary = run(api, tmp_path, "2330", "2026-11-09", warrant_kbar_days=5, tick_days=2, tick_top=2, max_mb=100,
                  today="2026-11-12", throttle=0, log=lambda *_: None)
    contracts = pd.read_parquet(tmp_path / "contracts" / "2330.parquet")
    assert set(contracts["warrant_id"]) == {"030156", "030157", "03011T"}
    assert set(contracts["kind"]) == {"call", "put"}
    # Top 2 by volume with volume > 0: 030156 then 03011T; 030157 never traded so no ticks.
    tick_calls = [c for c in api.calls if c[0] == "ticks"]
    assert {c[1] for c in tick_calls} == {"030156", "03011T"}
    assert {c[2] for c in tick_calls} == {"2026-11-11", "2026-11-12"}
    assert summary["tick_files"] == 4 and not summary["stopped_by_budget"]
    ticks = pd.read_parquet(tmp_path / "ticks" / "2026-11-12" / "030156.parquet")
    assert list(ticks[["bid_price", "ask_price"]].iloc[0]) == [0.87, 0.97]

    # Second run downloads no ticks again.
    api.calls.clear()
    again = run(api, tmp_path, "2330", "2026-11-09", 5, 2, 2, 100, today="2026-11-12", throttle=0, log=lambda *_: None)
    assert again["tick_files"] == 0
    assert not [c for c in api.calls if c[0] == "ticks"]


def test_run_stops_at_budget_and_resumes(tmp_path):
    api = FakeAPI(tick_cost=10_000_000)  # 10 MB per tick call
    first = run(api, tmp_path, "2330", "2026-11-09", 5, 2, 2, max_mb=15, today="2026-11-12", throttle=0, log=lambda *_: None)
    assert first["stopped_by_budget"] and first["tick_files"] == 2  # 0.1 MB of kbars, then 2 x 10 MB
    second = run(api, tmp_path, "2330", "2026-11-09", 5, 2, 2, max_mb=100, today="2026-11-12", throttle=0, log=lambda *_: None)
    assert second["tick_files"] == 2 and not second["stopped_by_budget"]  # only the missing ones


def test_ticks_skip_days_without_trades(tmp_path):
    api = FakeAPI()
    api.volume = {"03011T": {"2026-11-10": 3, "2026-11-12": 7}, "030156": 50, "030157": 0}
    summary = run(api, tmp_path, "2330", "2026-11-09", warrant_kbar_days=5, tick_days=4, tick_top=10, max_mb=100,
                  today="2026-11-12", throttle=0, log=lambda *_: None)
    days_03011T = sorted(c[2] for c in api.calls if c[0] == "ticks" and c[1] == "03011T")
    assert days_03011T == ["2026-11-10", "2026-11-12"]  # 11-09 and 11-11 had no K-bar volume
    assert summary["skipped_no_trade"] == 2
    assert len([c for c in api.calls if c[0] == "ticks" and c[1] == "030156"]) == 4


def test_ticks_fetched_when_kbars_do_not_cover_the_day(tmp_path):
    api = FakeAPI()
    # K bars only for the last 1 day, ticks requested for 3 days: older days are unknown -> fetched.
    run(api, tmp_path, "2330", "2026-11-09", warrant_kbar_days=1, tick_days=3, tick_top=10, max_mb=100,
        today="2026-11-12", throttle=0, log=lambda *_: None)
    days = sorted(c[2] for c in api.calls if c[0] == "ticks" and c[1] == "030156")
    assert days == ["2026-11-10", "2026-11-11", "2026-11-12"]
