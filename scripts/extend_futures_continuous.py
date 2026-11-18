"""Extend the TX / MTX / TMF 1-minute continuous series (post roll rule) with Shioaji data.

Base: <root>/source/{TX,MTX,TMF}_continuous_1m_post.parquet (layout described in its README).
New:  <root>/shioaji_raw/{TXF,MXF,TMF}{R1,R2}.parquet from Shioaji near / next-month continuous kbars.

Conventions copied from the base files:
* ts = bar START (Shioaji labels bars by their end, so ts = datetime - 1 min).
* session: position 08:45-13:44, after_market 15:00-04:59.
* trade_date: night bars belong to the next trading day.
* post rule: on expiry day the old contract is kept through the 13:29 bar; the new contract's
  13:30-13:44 bars on that day are dropped and the new segment starts with the 15:00 night session.
* Roll gap for rolls after the base ends = next-month close minus front close at the front's last
  bar (13:29 on expiry day), both taken from Shioaji R2 / R1 at the same minute.
* Backward adjustment: the newest segment is unadjusted; every older row gets the new gaps added
  (diff) / multiplied (ratio) on top of its existing adjustment.

Usage: python scripts/extend_futures_continuous.py --root ../data/futures_continuous --end 2026-11-18
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

PRODUCTS = {"TX": "TXF", "MTX": "MXF", "TMF": "TMF"}
PRICE = ["open", "high", "low", "close"]


def third_wednesdays(start, end):
    """TAIFEX monthly expiry = third Wednesday. Holiday shifts are checked against the data."""
    out = []
    for month in pd.period_range(start, end, freq="M"):
        first = month.to_timestamp()
        weds = pd.date_range(first, first + pd.offsets.MonthEnd(0), freq="W-WED")
        out.append(weds[2].normalize())
    return out


def load_shioaji(path):
    k = pd.read_parquet(path)
    k["ts"] = k["datetime"] - pd.Timedelta(minutes=1)
    return k.drop(columns="datetime").rename(columns=str.lower).set_index("ts").sort_index()


def session_of(ts):
    minutes = ts.dt.hour * 60 + ts.dt.minute
    day = (minutes >= 8 * 60 + 45) & (minutes <= 13 * 60 + 44)
    night = (minutes >= 15 * 60) | (minutes <= 4 * 60 + 59)
    return np.where(day, "position", np.where(night, "after_market", None))


def trade_dates(ts, session, trading_days):
    """Day bars -> own date; night bars -> next trading day (00:00-04:59 -> that date if trading)."""
    days = np.array(sorted(trading_days), dtype="datetime64[ns]")
    cal = ts.dt.normalize().to_numpy()
    after_15 = (ts.dt.hour >= 15).to_numpy()
    # first trading day strictly after the calendar date (evening) / on or after it (early morning)
    idx = np.where(after_15, np.searchsorted(days, cal, side="right"), np.searchsorted(days, cal, side="left"))
    night = np.where(idx < len(days), days[np.minimum(idx, len(days) - 1)], np.datetime64("NaT"))
    return pd.to_datetime(np.where(session == "position", cal, night)).date


def build_new_rows(r1, r2, start_after, end_ts, expiries):
    k = r1[(r1.index > start_after) & (r1.index <= end_ts)].copy()
    k = k.reset_index()
    k["session"] = session_of(k["ts"])
    k = k[k["session"].notna()]

    # contract month per bar under the post rule
    exp_ts = sorted(e + pd.Timedelta(hours=13, minutes=29) for e in expiries)
    pos = np.searchsorted(np.array(exp_ts, dtype="datetime64[ns]"), k["ts"].to_numpy(), side="left")
    k["contract"] = [exp_ts[i].strftime("%Y%m") for i in pos]

    # drop new-contract bars between 13:30 and 13:44 on expiry days
    exp_days = {e.date() for e in expiries}
    on_exp = k["ts"].dt.date.isin(exp_days)
    late = (k["ts"].dt.hour == 13) & (k["ts"].dt.minute >= 30)
    k = k[~(on_exp & late)]

    trading_days = set(k.loc[k["session"] == "position", "ts"].dt.normalize())
    k["trade_date"] = trade_dates(k["ts"], k["session"].to_numpy(), trading_days)
    k = k.rename(columns={c: f"{c}_none" for c in PRICE})
    k["source"] = "shioaji"
    return k


def roll_gaps(new, r1, r2):
    """One row per contract change inside `new`: front close vs next close at the front's last bar."""
    change = new["contract"].ne(new["contract"].shift(-1)) & new["contract"].shift(-1).notna()
    rows = []
    for i in new.index[change]:
        t = new.at[i, "ts"]
        front = r1["close"].loc[:t].iloc[-1]
        nxt_series = r2["close"].loc[:t]
        nxt, nxt_t = nxt_series.iloc[-1], nxt_series.index[-1]
        rows.append({"roll_ts": t, "from_contract": new.at[i, "contract"],
                     "to_contract": new.at[new.index[new.index.get_loc(i) + 1], "contract"],
                     "px_front": front, "px_next": nxt, "same_minute": nxt_t == t,
                     "gap_points": nxt - front, "gap_ratio": nxt / front})
    return pd.DataFrame(rows)


def extend(base, new, gaps):
    base = base.copy()
    last = base.iloc[-1]
    # roll between base's last contract and the first new contract (if the base ends on a roll)
    new = new.copy()
    seg = int(last["seg"]) + np.cumsum(new["contract"].ne(new["contract"].shift(1).fillna(last["contract"]))).to_numpy()
    new["seg"] = seg
    new["is_roll"] = new["contract"].ne(new["contract"].shift(-1)) & new["contract"].shift(-1).notna()

    total_pts = gaps["gap_points"].sum() if len(gaps) else 0.0
    total_fac = gaps["gap_ratio"].prod() if len(gaps) else 1.0

    # adjustments for new rows: sum/product of gaps of rolls that happen after the row's segment
    seg_ids = sorted(new["seg"].unique())
    pts_after, fac_after = {}, {}
    for j, s in enumerate(seg_ids):
        later = gaps.iloc[j:] if len(gaps) else gaps
        pts_after[s] = later["gap_points"].sum() if len(later) else 0.0
        fac_after[s] = later["gap_ratio"].prod() if len(later) else 1.0
    new["adj_points"] = new["seg"].map(pts_after)
    new["adj_factor"] = new["seg"].map(fac_after)

    base["adj_points"] = base["adj_points"] + total_pts
    base["adj_factor"] = base["adj_factor"] * total_fac
    out = pd.concat([base, new], ignore_index=True)
    for c in PRICE:
        out[f"{c}_diff"] = out[f"{c}_none"] + out["adj_points"]
        out[f"{c}_ratio"] = out[f"{c}_none"] * out["adj_factor"]
    out["volume"] = out["volume"].astype("int64")
    return out[base.columns]


def check_overlap(base, r1, expiries, trading_from="2026-06-18"):
    """Rebuild the base's own recent period from Shioaji and report how well it matches."""
    lo, hi = pd.Timestamp(trading_from), base["ts"].max()
    mine = build_new_rows(r1, None, lo - pd.Timedelta(minutes=1), hi, expiries)
    theirs = base[base["ts"] >= lo]
    m = theirs.merge(mine, on="ts", suffixes=("", "_sj"))
    return {
        "bars_base": len(theirs), "bars_matched": len(m),
        "close_equal": round(float((m["close_none"] == m["close_none_sj"]).mean()), 4),
        "session_equal": round(float((m["session"] == m["session_sj"]).mean()), 4),
        "trade_date_equal": round(float((pd.to_datetime(m["trade_date"]) == pd.to_datetime(m["trade_date_sj"])).mean()), 4),
        "contract_equal": round(float((m["contract"] == m["contract_sj"]).mean()), 4),
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--end", required=True, help="last trading date to include (day session through 13:44)")
    args = p.parse_args(argv)
    root = Path(args.root)
    end_ts = pd.Timestamp(args.end) + pd.Timedelta(hours=13, minutes=44)
    expiries = third_wednesdays("2026-06", pd.Timestamp(args.end) + pd.offsets.MonthEnd(2))

    for her, sj in PRODUCTS.items():
        base = pd.read_parquet(root / "source" / f"{her}_continuous_1m_post.parquet")
        r1, r2 = load_shioaji(root / "shioaji_raw" / f"{sj}R1.parquet"), load_shioaji(root / "shioaji_raw" / f"{sj}R2.parquet")
        print(her, "overlap check:", check_overlap(base, r1, expiries))

        new = build_new_rows(r1, r2, base["ts"].max(), end_ts, expiries)
        gaps = roll_gaps(pd.concat([base.tail(1)[["ts", "contract"]], new[["ts", "contract"]]], ignore_index=True), r1, r2)
        out = extend(base, new, gaps)

        tag = pd.Timestamp(args.end).strftime("%Y%m%d")
        out.to_parquet(root / f"{her}_continuous_1m_post_to_{tag}.parquet", index=False)
        gaps.to_csv(root / f"{her}_new_rolls_to_{tag}.csv", index=False)
        print(f"  rows {len(base):,} + {len(new):,} = {len(out):,}; {out['ts'].min()} ~ {out['ts'].max()}")
        print("  new rolls:", gaps[["roll_ts", "from_contract", "to_contract", "gap_points", "same_minute"]].to_dict("records"))


if __name__ == "__main__":
    main()
