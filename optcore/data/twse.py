"""Warrant terms from TWSE open data (上市權證基本資料彙總表, free, no account).

The table is a daily snapshot with one row per listed warrant: latest strike,
exercise ratio, expiry, plus a free-text 備註 column listing every adjustment
(dividend adjustments, strike resets) with its date.

`parse_twse_terms()` turns it into the same *event* layout as the TEJ terms
table (one row per warrant event), so `terms_as_of()` and
`merge_daily_with_terms()` from `optcore.data.tej` work unchanged and the
strike used on a given day is the one valid on that day (no look-ahead).

Expired warrants drop out of the TWSE table after a while, so keep the dated
snapshots written by `download()`; `load_terms()` merges them.

Known limits:
* The ratio before the first adjustment is not published; the latest ratio is
  used for the initial row (dividend adjustments rarely change it at 4 decimals).
* Listed (TWSE) warrants only. TPEx warrants are not in this table.
* No issue volatility / issue price (TEJ has those).

CLI:  python -m optcore.data.twse --out ../data/twse
"""

import argparse
import json
import re
import urllib.request
from pathlib import Path

import pandas as pd

from optcore.data.tej import parse_issuer

URL = "https://openapi.twse.com.tw/v1/opendata/t187ap37_L"

_DIVIDEND_RE = re.compile(r"(\d{4}/\d{2}/\d{2})標的證券[^，]*，調整後履約價格([\d,.]+)元，調整後行使比例([\d.]+)")
_RESET_RE = re.compile(r"生效日期(\d{4}/\d{2}/\d{2})，重設後履約價\(元\)/點數：([\d,.]+)")


def roc_date(text):
    """'1151016' (ROC year 115) -> Timestamp('2026-10-16'). Blank/invalid -> NaT."""
    text = str(text).strip()
    if not re.fullmatch(r"\d{7}", text):
        return pd.NaT
    return pd.Timestamp(year=int(text[:3]) + 1911, month=int(text[3:5]), day=int(text[5:]))


def _num(text):
    value = pd.to_numeric(str(text).replace(",", "").strip(), errors="coerce")
    return float(value) if pd.notna(value) else float("nan")


def parse_remark_events(remark):
    """Strike/ratio changes found in the 備註 text, oldest first.

    Returns a list of (date, event, strike, ratio); ratio is None for resets.
    """
    text = str(remark or "")
    events = [(pd.Timestamp(d), "除權息調整", _num(k), float(r)) for d, k, r in _DIVIDEND_RE.findall(text)]
    events += [(pd.Timestamp(d), "履約價重設", _num(k), None) for d, k in _RESET_RE.findall(text)]
    # A reset takes effect on the listing day, before any same-day adjustment.
    return sorted(events, key=lambda e: (e[0], e[1] != "履約價重設"))


def parse_twse_terms(records, underlying_name=None):
    """Raw TWSE rows (list of dicts or DataFrame) -> event-style terms DataFrame."""
    raw = pd.DataFrame(records)
    raw = raw.apply(lambda col: col.str.strip() if col.dtype == object or str(col.dtype) == "str" else col)
    if underlying_name is not None:
        raw = raw[raw["標的證券/指數"] == underlying_name]

    rows = []
    for r in raw.to_dict("records"):
        start, end = roc_date(r["履約開始日"]), roc_date(r["履約截止日"])
        ratio = _num(r["最新標的履約配發數量(每仟單位權證)"]) / 1000.0
        upper, lower = _num(r["最新上限價格(元)/上限指數"]), _num(r["最新下限價格(元)/下限指數"])
        base = {
            "warrant_id": r["權證代號"], "name": r["權證簡稱"],
            "kind": "put" if r["權證類型"] == "認售" else "call",
            "style": "european" if start == end else "american",
            "category": r["類別"], "issuer": parse_issuer(r["權證簡稱"]),
            "underlying_name": r["標的證券/指數"],
            "exercise_start": start, "expiry_date": end, "last_trade_date": roc_date(r["最後交易日"]),
            "issue_units_k": _num(r["發行單位數量(仟單位)"]),
            "barrier": upper or lower or float("nan"),
            "snapshot_date": roc_date(r["出表日期"]),
        }
        events = [(pd.NaT, "發行", _num(r["原始履約價格(元)/履約指數"]), None)] + parse_remark_events(r.get("備註"))
        for seq, (date, event, strike, event_ratio) in enumerate(events):
            ratio_now = event_ratio if event_ratio is not None else ratio
            rows.append({**base, "event_date": date, "event_seq": seq, "event": event,
                         "strike": strike, "ratio": ratio_now})
        # The last event must reproduce TWSE's "latest" strike; if the remark text
        # was not fully understood, add a catch-all row so current terms are right.
        latest = _num(r["最新履約價格(元)/履約指數"])
        if abs(rows[-1]["strike"] - latest) > 0.005 or abs(rows[-1]["ratio"] - ratio) > 1e-9:
            rows.append({**base, "event_date": base["snapshot_date"], "event_seq": len(events),
                         "event": "未解析調整", "strike": latest, "ratio": ratio})
    out = pd.DataFrame(rows)
    return out.sort_values(["warrant_id", "event_seq"]).reset_index(drop=True)


def download(out_dir, url=URL, timeout=120):
    """Fetch today's table and store it as raw_<snapshot date>.parquet. Returns the path."""
    request = urllib.request.Request(url, headers={"User-Agent": "optcore", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = pd.DataFrame(json.load(response))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = roc_date(raw["出表日期"].iloc[0]).strftime("%Y%m%d")
    path = out_dir / f"raw_{stamp}.parquet"
    raw.to_parquet(path, index=False)
    return path


def load_terms(out_dir, underlying_name=None):
    """Parsed terms from every stored snapshot; each warrant uses its newest snapshot."""
    paths = sorted(Path(out_dir).glob("raw_*.parquet"))
    if not paths:
        raise FileNotFoundError(f"no raw_*.parquet snapshots in {out_dir}")
    terms = pd.concat([parse_twse_terms(pd.read_parquet(p), underlying_name) for p in paths], ignore_index=True)
    newest = terms.groupby("warrant_id")["snapshot_date"].transform("max")
    return terms[terms["snapshot_date"] == newest].reset_index(drop=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download the TWSE warrant terms snapshot")
    parser.add_argument("--out", required=True, help="folder for raw_<date>.parquet snapshots")
    args = parser.parse_args(argv)
    path = download(args.out)
    print(f"saved {path} ({len(pd.read_parquet(path))} warrants)")


if __name__ == "__main__":
    main()
