"""Shioaji near-month (R1) and next-month (R2) minute bars for TXF / MXF / TMF.

Writes <root>/shioaji_raw/{TXF,MXF,TMF}{R1,R2}.parquet for START..END; these feed
scripts/extend_futures_continuous.py.

Usage: python scripts/fetch_futures_r1r2.py --root ../data/futures_continuous --env-file "<.env>" [--end YYYY-MM-DD]
"""

import argparse
import os
import time
from datetime import date
from pathlib import Path

from optcore.data.shioaji_source import load_env_file, to_frame

START = "2026-06-17"  # overlaps the base continuous files, which end 2026-08-07


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="../data/futures_continuous")
    p.add_argument("--env-file")
    p.add_argument("--end", default=date.today().isoformat())
    a = p.parse_args(argv)
    out = Path(a.root) / "shioaji_raw"
    out.mkdir(parents=True, exist_ok=True)
    if a.env_file:
        load_env_file(a.env_file)

    import shioaji as sj

    api = sj.Shioaji(simulation=False)
    api.login(api_key=os.environ["SJ_API_KEY"], secret_key=os.environ["SJ_SEC_KEY"],
              fetch_contract=True, contracts_timeout=60000)
    try:
        fut = api.Contracts.Futures
        for prod in ["TXF", "MXF", "TMF"]:
            for r in ["R1", "R2"]:
                contract = getattr(getattr(fut, prod), prod + r)
                for i in range(4):
                    try:
                        k = to_frame(api.kbars(contract, start=START, end=a.end),
                                     ["ts", "Open", "High", "Low", "Close", "Volume"])
                        break
                    except Exception:
                        if i == 3:
                            raise
                        time.sleep(3 * (i + 1))
                k[["datetime", "Open", "High", "Low", "Close", "Volume"]].to_parquet(out / f"{prod}{r}.parquet", index=False)
                print(prod, r, len(k), k["datetime"].min(), k["datetime"].max())
    finally:
        try:
            api.logout()
        except Exception:
            pass


if __name__ == "__main__":
    main()
