"""Shioaji ticks for 2330 stock and CDF / TXF near-month futures, plus CDF / TXF minute bars.

Fetches every day that already has warrant ticks (data/shioaji/ticks/<day>) and skips days
already on disk, so it can run daily after optcore.data.shioaji_source.

Usage: python scripts/fetch_underlying_ticks.py --data ../data --env-file "<path to .env>"
"""

import argparse
import os
import time
from pathlib import Path

from optcore.data.shioaji_source import TICK_COLUMNS, load_env_file, to_frame

KBAR_COLUMNS = ["ts", "Open", "High", "Low", "Close", "Volume", "Amount"]


def retry(fn, tries=4):
    for i in range(tries):
        try:
            return fn()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="../data")
    p.add_argument("--env-file")
    a = p.parse_args(argv)
    out = Path(a.data) / "shioaji"
    days = sorted(d.name for d in (out / "ticks").iterdir() if d.is_dir())
    if a.env_file:
        load_env_file(a.env_file)

    import shioaji as sj

    api = sj.Shioaji(simulation=False)
    api.login(api_key=os.environ["SJ_API_KEY"], secret_key=os.environ["SJ_SEC_KEY"],
              fetch_contract=True, contracts_timeout=60000)
    try:
        start_mb = retry(lambda: api.usage().bytes) / 1e6
        fut = api.Contracts.Futures
        targets = {"2330": ("stock", api.Contracts.Stocks["2330"]),
                   "CDF": ("futures", fut.CDF.CDFR1), "TXF": ("futures", fut.TXF.TXFR1)}
        n_files = n_rows = 0
        for name, (sub, contract) in targets.items():
            for day in days:
                path = out / "underlying_ticks" / sub / name / f"{day}.parquet"
                if path.exists():
                    continue
                ticks = to_frame(retry(lambda: api.ticks(contract, date=day)), TICK_COLUMNS)
                path.parent.mkdir(parents=True, exist_ok=True)
                ticks.to_parquet(path, index=False)
                n_files += 1
                n_rows += len(ticks)
                time.sleep(0.12)
            if sub == "futures":
                k = to_frame(retry(lambda: api.kbars(contract, start=days[0], end=days[-1])), KBAR_COLUMNS)
                kpath = out / "underlying_kbars" / "futures" / f"{name}.parquet"
                kpath.parent.mkdir(parents=True, exist_ok=True)
                k.to_parquet(kpath, index=False)
        used = retry(lambda: api.usage().bytes) / 1e6 - start_mb
        print(f"完成：days {len(days)} ({days[0]}~{days[-1]}), new files {n_files}, rows {n_rows:,}, used {used:.1f} MB")
    finally:
        try:
            api.logout()
        except Exception:
            pass


if __name__ == "__main__":
    main()
