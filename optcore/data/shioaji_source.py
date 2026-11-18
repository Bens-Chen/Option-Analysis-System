"""Download Taiwan warrant data from SinoPac Shioaji and cache it as parquet.

What Shioaji provides (checked against a live account):
    * warrant contracts (code, name, reference / limit prices) - no strike / ratio / expiry,
      so warrant terms still come from TEJ
    * 1-minute K bars for warrants and underlyings (cheap: ~0.03 MB per warrant-month)
    * historical ticks with the best bid / ask at each trade (expensive: ~0.6 MB per
      warrant-day), which is where the issuer's market-making quotes are visible

The daily data quota (500 MB) is the binding constraint, so the downloader:
    * fetches K bars for every warrant on the underlying,
    * ranks warrants by traded volume and fetches ticks only for the most active ones,
    * stops when this run's usage reaches `max_mb`, and
    * skips anything already on disk, so re-running continues where it stopped.

Credentials are read from the environment (SJ_API_KEY, SJ_SEC_KEY) or from a
.env file passed with --env-file. They are never written anywhere.

Usage:
    python -m optcore.data.shioaji_source --underlying 2330 --env-file /path/to/.env
"""

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from optcore.data.tej import _ISSUER_RE, parse_issuer, parse_warrant_type

TICK_COLUMNS = ["ts", "close", "volume", "bid_price", "bid_volume", "ask_price", "ask_volume", "tick_type"]
KBAR_COLUMNS = ["ts", "Open", "High", "Low", "Close", "Volume", "Amount"]


# ---------------------------------------------------------------- helpers
def load_env_file(path):
    """Read KEY=VALUE lines into os.environ (existing variables win)."""
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def to_frame(result, columns):
    """Shioaji Ticks / Kbars objects -> DataFrame with a datetime column.

    Shioaji timestamps are Taipei wall-clock time stored as epoch nanoseconds,
    so converting without a timezone gives the local trading time.
    """
    data = {c: list(getattr(result, c, [])) for c in columns}
    df = pd.DataFrame(data, columns=columns)
    df["datetime"] = pd.to_datetime(df["ts"], unit="ns")
    return df.drop(columns="ts")


def is_warrant_of(contract, underlying_name):
    """Warrant short names are <underlying><issuer><code><購/售/牛/熊><serial>."""
    name = contract.name
    if len(contract.code) != 6 or not name.startswith(underlying_name):
        return False
    match = _ISSUER_RE.match(name, len(underlying_name))
    return match is not None


class _CoveredDays(set):
    """Traded days within [start, end]; days outside the range count as 'maybe traded'."""

    def __init__(self, days, start, end):
        super().__init__(days)
        self.start, self.end = start, end

    def __contains__(self, day):
        if day < self.start or day > self.end:
            return True
        return super().__contains__(day)


@dataclass
class Budget:
    """Tracks this run's data usage against a cap."""

    api: object
    max_mb: float
    reserve_mb: float = 20.0
    start_bytes: int = field(init=False)

    def __post_init__(self):
        self.start_bytes = self._usage().bytes

    def _usage(self, tries=4):
        # The usage endpoint occasionally times out; retry instead of aborting the run.
        for attempt in range(tries):
            try:
                return self.api.usage()
            except Exception:
                if attempt == tries - 1:
                    raise
                time.sleep(2 * (attempt + 1))

    def used_mb(self):
        return (self._usage().bytes - self.start_bytes) / 1e6

    def exhausted(self):
        usage = self._usage()
        return (usage.bytes - self.start_bytes) / 1e6 >= self.max_mb or usage.remaining_bytes / 1e6 <= self.reserve_mb


# ---------------------------------------------------------------- downloader
class ShioajiDownloader:
    def __init__(self, api, out_dir, throttle=0.12, log=print):
        self.api = api
        self.out = Path(out_dir)
        self.throttle = throttle  # stays under Shioaji's ~50 queries / 5 s limit
        self.log = log
        self.out.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.out / "manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text()) if self.manifest_path.exists() else {"kbars": {}}

    def _save_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest, indent=1, ensure_ascii=False))

    def _pause(self):
        if self.throttle:
            time.sleep(self.throttle)

    # ---- contracts
    def stock(self, code):
        return self.api.Contracts.Stocks[code]

    def warrants(self, underlying_id):
        underlying_name = self.stock(underlying_id).name
        found = []
        for exchange in ("TSE", "OTC"):
            for c in getattr(self.api.Contracts.Stocks, exchange):
                if is_warrant_of(c, underlying_name):
                    found.append(c)
        return found

    def save_contracts(self, underlying_id, contracts):
        rows = []
        for c in contracts:
            kind, _ = parse_warrant_type(c.name)
            rows.append({
                "warrant_id": c.code, "name": c.name, "underlying_id": underlying_id,
                "exchange": str(getattr(c.exchange, "value", c.exchange)), "kind": kind, "issuer": parse_issuer(c.name),
                "reference": c.reference, "limit_up": c.limit_up, "limit_down": c.limit_down,
                "update_date": c.update_date,
            })
        df = pd.DataFrame(rows)
        path = self.out / "contracts" / f"{underlying_id}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        return df

    # ---- K bars (one file per code, extended incrementally)
    def kbars(self, contract, start, end):
        """Fetch [start, end] minus the range already downloaded. Returns rows added."""
        code = contract.code
        start, end = pd.Timestamp(start).date(), pd.Timestamp(end).date()
        have = self.manifest["kbars"].get(code)
        segments = [(start, end)]
        if have:
            h0, h1 = date.fromisoformat(have[0]), date.fromisoformat(have[1])
            segments = []
            if start < h0:
                segments.append((start, min(end, h0 - timedelta(days=1))))
            if end > h1:
                segments.append((max(start, h1 + timedelta(days=1)), end))
        path = self.out / "kbars" / f"{code}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        frames = [pd.read_parquet(path)] if path.exists() else []
        added = 0
        for s, e in segments:
            if s > e:
                continue
            result = self.api.kbars(contract, start=s.isoformat(), end=e.isoformat())
            self._pause()
            df = to_frame(result, KBAR_COLUMNS)
            added += len(df)
            frames.append(df)
        if segments:
            merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=KBAR_COLUMNS[1:] + ["datetime"])
            merged = merged.drop_duplicates("datetime").sort_values("datetime")
            merged.to_parquet(path, index=False)
            lo = min([start] + ([date.fromisoformat(have[0])] if have else []))
            hi = max([end] + ([date.fromisoformat(have[1])] if have else []))
            self.manifest["kbars"][code] = [lo.isoformat(), hi.isoformat()]
            self._save_manifest()
        return added

    def read_kbars(self, code):
        path = self.out / "kbars" / f"{code}.parquet"
        return pd.read_parquet(path) if path.exists() else pd.DataFrame()

    def traded_days(self, code):
        """Days on which the K bars show volume, or None if K bars weren't downloaded.

        Only days inside the downloaded K-bar range are known; callers should treat
        days outside it as unknown (and fetch them), so this returns the covered range too.
        """
        have = self.manifest["kbars"].get(code)
        if not have:
            return None
        k = self.read_kbars(code)
        days = set() if k.empty else set(pd.to_datetime(k.loc[k["Volume"] > 0, "datetime"]).dt.date)
        return _CoveredDays(days, date.fromisoformat(have[0]), date.fromisoformat(have[1]))

    # ---- ticks (one file per code per day; an empty file marks "no trades")
    def tick_path(self, code, day):
        return self.out / "ticks" / str(day) / f"{code}.parquet"

    def ticks(self, contract, day):
        path = self.tick_path(contract.code, day)
        if path.exists():
            return None  # already downloaded
        result = self.api.ticks(contract, date=str(day))
        self._pause()
        df = to_frame(result, TICK_COLUMNS)
        df.insert(0, "warrant_id", contract.code)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        return len(df)


def rank_by_volume(downloader, contracts, since):
    """Warrants sorted by K-bar volume since `since` (most active first)."""
    rows = []
    for c in contracts:
        k = downloader.read_kbars(c.code)
        vol = 0 if k.empty else float(k.loc[k["datetime"] >= pd.Timestamp(since), "Volume"].sum())
        rows.append((c, vol))
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows


def run(api, out_dir, underlying_id, underlying_start, warrant_kbar_days, tick_days, tick_top, max_mb,
        today=None, throttle=0.12, log=print):
    today = pd.Timestamp(today or date.today()).date()
    dl = ShioajiDownloader(api, out_dir, throttle=throttle, log=log)
    budget = Budget(api, max_mb)
    summary = {"underlying_kbars": 0, "warrant_kbars": 0, "tick_files": 0, "ticks": 0, "stopped_by_budget": False}

    # 1. Underlying minute bars -> also tells us which days traded.
    summary["underlying_kbars"] = dl.kbars(dl.stock(underlying_id), underlying_start, today)
    ukb = dl.read_kbars(underlying_id)
    trading_days = sorted({d.date() for d in pd.to_datetime(ukb["datetime"])}) if not ukb.empty else []
    log(f"標的 {underlying_id}：{len(ukb)} 根分 K，{len(trading_days)} 個交易日")

    # 2. Contracts.
    contracts = dl.warrants(underlying_id)
    dl.save_contracts(underlying_id, contracts)
    log(f"權證合約：{len(contracts)} 檔")

    # 3. Warrant minute bars for every warrant.
    kbar_start = today - timedelta(days=warrant_kbar_days)
    for i, c in enumerate(contracts, 1):
        if budget.exhausted():
            summary["stopped_by_budget"] = True
            break
        summary["warrant_kbars"] += dl.kbars(c, kbar_start, today)
        if i % 100 == 0:
            log(f"  分 K {i}/{len(contracts)}，本次已用 {budget.used_mb():.1f} MB")

    # 4. Ticks for the most active warrants over the last `tick_days` trading days.
    recent = trading_days[-tick_days:] if tick_days else []
    if recent and not summary["stopped_by_budget"]:
        ranked = rank_by_volume(dl, contracts, recent[0])
        top = [c for c, vol in ranked[:tick_top] if vol > 0]
        log(f"逐筆：前 {len(top)} 檔最活躍權證 × {len(recent)} 天（{recent[0]} ~ {recent[-1]}）")
        traded = {c.code: dl.traded_days(c.code) for c in top}
        summary["skipped_no_trade"] = 0
        for day in reversed(recent):  # newest first: most useful if the budget runs out
            for c in top:
                if budget.exhausted():
                    summary["stopped_by_budget"] = True
                    break
                days = traded[c.code]
                if days is not None and day not in days:
                    summary["skipped_no_trade"] += 1  # K bars show no trades: ticks would be empty
                    continue
                n = dl.ticks(c, day)
                if n is not None:
                    summary["tick_files"] += 1
                    summary["ticks"] += n
            if summary["stopped_by_budget"]:
                break
        pd.DataFrame([{"warrant_id": c.code, "name": c.name, "volume": v} for c, v in ranked]).to_parquet(
            Path(out_dir) / "contracts" / f"{underlying_id}_activity.parquet", index=False)

    summary["used_mb"] = round(budget.used_mb(), 1)
    summary["remaining_mb"] = round(budget._usage().remaining_bytes / 1e6, 1)
    log(f"完成：{summary}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Download warrant data from SinoPac Shioaji")
    parser.add_argument("--underlying", default="2330")
    parser.add_argument("--out", default="data/shioaji")
    parser.add_argument("--env-file", default=os.environ.get("SHIOAJI_ENV_FILE"))
    parser.add_argument("--underlying-start", default=str(date.today() - timedelta(days=365)))
    parser.add_argument("--warrant-kbar-days", type=int, default=30)
    parser.add_argument("--tick-days", type=int, default=5)
    parser.add_argument("--tick-top", type=int, default=40)
    parser.add_argument("--max-mb", type=float, default=250)
    args = parser.parse_args()

    if args.env_file:
        load_env_file(args.env_file)
    if not os.environ.get("SJ_API_KEY") or not os.environ.get("SJ_SEC_KEY"):
        raise SystemExit("請設定 SJ_API_KEY / SJ_SEC_KEY，或用 --env-file 指定 .env 檔")

    import shioaji as sj

    api = sj.Shioaji(simulation=False)
    api.login(api_key=os.environ["SJ_API_KEY"], secret_key=os.environ["SJ_SEC_KEY"],
              fetch_contract=True, contracts_timeout=60000)
    try:
        run(api, args.out, args.underlying, args.underlying_start, args.warrant_kbar_days,
            args.tick_days, args.tick_top, args.max_mb)
    finally:
        try:
            api.logout()
        except Exception as exc:  # data is already saved; a slow logout is harmless
            print(f"登出逾時，可忽略：{type(exc).__name__}")


if __name__ == "__main__":
    main()
