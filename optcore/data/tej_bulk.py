"""Bulk TEJ warrant exports -> Parquet.

TEJ's large exports differ from the small Excel samples handled by `optcore.data.tej`:

* UTF-16, tab separated (.txt / .csv), or .xlsx for the smaller terms files;
* 證券代碼 holds code and short name together ("030001T 大同凱基51購02");
* missing values are written as "." (numbers) or "-" (dates); dates are YYYYMMDD.

`convert_daily()` streams a multi-GB daily file in chunks and writes one Parquet file.
`convert_terms()` reads one or more terms (行使比例) files and writes one event table.
Column names follow `optcore.data.tej`, so `merge_daily_with_terms()` works on the output.

CLI:
    python -m optcore.data.tej_bulk daily  OUT.parquet IN1 [IN2 ...]
    python -m optcore.data.tej_bulk terms  OUT.parquet IN1 [IN2 ...]
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from optcore.data.tej import DAILY_COLUMNS, TERMS_COLUMNS, parse_issuer, parse_underlying, parse_warrant_type

DAILY_TEXT = {"warrant_id", "name", "moneyness_label", "underlying_raw", "settlement"}
DAILY_EXTRA = {"證券代碼": "code_name", "年月日": "date", "履約方式": "settlement", "價內外": "moneyness_label",
               "內含價值": "intrinsic_value", "時間價值": "time_value"}

TERMS_EXTRA = {"證券代碼": "code_name", "年月日": "event_date", "序號": "event_seq", "履約方式.1": "settlement",
               "權證衍生種類": "warrant_subtype", "存續期間(年)": "tenor_years"}
TERMS_DATES = ["event_date", "issue_date", "listing_date", "expiry_date", "last_trade_date",
               "scheduled_last_trade_date", "exercise_start", "exercise_end", "reset_start", "reset_end", "reset_date"]
TERMS_TEXT = {"warrant_id", "name", "underlying_raw", "event", "full_name", "settlement", "warrant_type",
              "warrant_subtype", "exchange", "foreign_investable"}
TERMS_DROP_PREFIX = ("重設說明", "履約價幣別", "發行履約價幣別", "發行時標的市價幣別", "目前履約價幣別", "發行匯率", "結算匯率")


def _is_text_file(path):
    return Path(path).suffix.lower() in {".txt", ".csv"}


def _split_code_name(series):
    parts = series.astype(str).str.strip().str.split(r"\s+", n=1, expand=True)
    return parts[0], parts[1] if parts.shape[1] > 1 else pd.Series(None, index=series.index)


def _numeric(series):
    s = series.astype(str).str.strip().str.replace(",", "", regex=False)
    return pd.to_numeric(s.where(~s.isin({".", "-", "", "nan", "None"})), errors="coerce")


def _yyyymmdd(series):
    s = series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    return pd.to_datetime(s.where(s.str.fullmatch(r"\d{8}")), format="%Y%m%d", errors="coerce")


def clean_daily(chunk):
    """One raw chunk (all str) -> typed DataFrame."""
    df = chunk.rename(columns={**DAILY_COLUMNS, **DAILY_EXTRA})
    df["warrant_id"], df["name"] = _split_code_name(df.pop("code_name"))
    df["date"] = _yyyymmdd(df["date"])
    if "settlement" not in df.columns:
        df["settlement"] = None
    for col in df.columns:
        if col not in DAILY_TEXT and col != "date":
            df[col] = _numeric(df[col]).astype("float64")
    for col in DAILY_TEXT:
        df[col] = df[col].astype("str").str.strip().replace({".": None, "": None})
    parsed = df["underlying_raw"].map(parse_underlying)
    df["underlying_id"] = parsed.map(lambda x: x[0]).astype("str")
    df["underlying_name"] = parsed.map(lambda x: x[1]).astype("str")
    df["T"] = df["days_to_expiry"] / 365.0
    df["traded"] = df["volume"].fillna(0) > 0
    return df


def _daily_chunks(path, chunksize):
    if _is_text_file(path):
        yield from pd.read_csv(path, sep="\t", encoding="utf-16", dtype=str, chunksize=chunksize,
                               keep_default_na=False)
    else:
        yield pd.read_excel(path, dtype=str)


def convert_daily(paths, out, chunksize=500_000, log=print):
    """Stream one or more daily exports into a single Parquet file. Returns row count."""
    writer, schema, rows = None, None, 0
    columns = None
    try:
        for path in paths:
            for chunk in _daily_chunks(path, chunksize):
                df = clean_daily(chunk)
                if columns is None:
                    columns = list(df.columns)
                df = df.reindex(columns=columns)
                table = pa.Table.from_pandas(df, preserve_index=False)
                if writer is None:
                    schema = table.schema
                    writer = pq.ParquetWriter(out, schema, compression="zstd")
                writer.write_table(table.cast(schema))
                rows += len(df)
                log(f"  {Path(path).name}: {rows:,} rows")
    finally:
        if writer is not None:
            writer.close()
    return rows


def _read_terms_raw(path):
    if _is_text_file(path):
        return pd.read_csv(path, sep="\t", encoding="utf-16", dtype=str, keep_default_na=False)
    return pd.read_excel(path, dtype=str)


def clean_terms(raw):
    df = raw.drop(columns=[c for c in raw.columns if str(c).startswith(TERMS_DROP_PREFIX)])
    df = df.drop(columns=["履約方式"], errors="ignore")  # first 履約方式 column is always "."
    df = df.rename(columns={**TERMS_COLUMNS, **TERMS_EXTRA, "外資可否投資": "foreign_investable"})
    df["warrant_id"], df["name"] = _split_code_name(df.pop("code_name"))
    for col in TERMS_DATES:
        if col in df.columns:
            df[col] = _yyyymmdd(df[col])
    for col in df.columns:
        if col not in TERMS_TEXT and col not in TERMS_DATES:
            df[col] = _numeric(df[col]).astype("float64")
    for col in TERMS_TEXT & set(df.columns):
        df[col] = df[col].astype("str").str.strip().replace({".": None, "-": None, "": None})

    parsed = df["underlying_raw"].map(parse_underlying)
    df["underlying_id"] = parsed.map(lambda x: x[0]).astype("str")
    df["underlying_name"] = parsed.map(lambda x: x[1]).astype("str")
    types = df["warrant_type"].map(parse_warrant_type)
    df["kind"] = types.map(lambda x: x[0]).astype("str")
    df["style"] = types.map(lambda x: x[1]).astype("str")
    df["issuer"] = df["name"].map(parse_issuer).astype("str")
    df["issue_vol"] = df["issue_vol_pct"] / 100.0
    df["event_seq"] = df["event_seq"].astype("Int64")
    return df


def convert_terms(paths, out, log=print):
    frames = []
    for path in paths:
        df = clean_terms(_read_terms_raw(path))
        log(f"  {Path(path).name}: {len(df):,} events")
        frames.append(df)
    terms = pd.concat(frames, ignore_index=True)
    terms = terms.drop_duplicates(["warrant_id", "event_date", "event_seq"], keep="last")
    terms = terms.sort_values(["warrant_id", "event_date", "event_seq"]).reset_index(drop=True)
    terms.to_parquet(out, index=False, compression="zstd")
    return len(terms)


def main(argv=None):
    p = argparse.ArgumentParser(description="Convert TEJ bulk exports to Parquet")
    p.add_argument("kind", choices=["daily", "terms"])
    p.add_argument("out")
    p.add_argument("inputs", nargs="+")
    a = p.parse_args(argv)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    n = convert_daily(a.inputs, a.out) if a.kind == "daily" else convert_terms(a.inputs, a.out)
    print(f"saved {a.out}: {n:,} rows")


if __name__ == "__main__":
    main()
