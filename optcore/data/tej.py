"""Readers for TEJ data-explorer exports (Excel or CSV).

Two tables are supported:

* Warrant terms / events (權證條款): one row per warrant *event* (issue,
  strike reset, dividend adjustment...). Strike and ratio can change over
  time, so use `terms_as_of()` to get the terms valid on a given date and
  avoid look-ahead bias.
* Warrant daily trading (權證日交易): price, volume, underlying price and
  TEJ's own theoretical price / IV / Greeks (handy for cross-checking).

Column names are mapped from TEJ's Chinese headers to English snake_case.
Unknown columns are kept with their original names.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

TERMS_COLUMNS = {
    "名稱": "name",
    "權證碼": "warrant_id",
    "事件日": "event_date",
    "序號": "event_seq",
    "標的證券碼": "underlying_raw",
    "行使比例": "ratio_event",
    "履約價(元)": "strike_event",
    "事件說明": "event",
    "權證全稱": "full_name",
    "履約方式": "settlement",
    "發行日": "issue_date",
    "上市日": "listing_date",
    "到期日": "expiry_date",
    "存續期間(年)": "tenor_years",
    "權證類型": "warrant_type",
    "權證衍生種類": "warrant_subtype",
    "發行單位": "issue_units",
    "發行總額(千台幣)": "issue_amount_k",
    "發行價格(台幣元)": "issue_price",
    "發行溢價%": "issue_premium_pct",
    "價內外發行%": "issue_moneyness_pct",
    "發行履約價(元)": "issue_strike",
    "發行時標的市價(元)": "issue_underlying_price",
    "發行上(下)限價格(台幣元)": "issue_barrier",
    "目前履約價(元)": "strike",
    "目前上(下)限價(台幣元)": "barrier",
    "目前行使比例": "ratio",
    "掛牌交易所": "exchange",
    "最後交易日": "last_trade_date",
    "預定最後交易日": "scheduled_last_trade_date",
    "履約開始日": "exercise_start",
    "履約結束日": "exercise_end",
    "發行日波動率": "issue_vol_pct",
    "重設期間起日": "reset_start",
    "重設期間迄日": "reset_end",
    "重設百分比上限": "reset_cap_pct",
    "重設百分比下限": "reset_floor_pct",
    "實際重設日": "reset_date",
}

DAILY_COLUMNS = {
    "名稱": "name",
    "權證碼": "warrant_id",
    "日期": "date",
    "權證開盤價(元)": "open",
    "權證最高價(元)": "high",
    "權證最低價(元)": "low",
    "權證收盤價(元)": "close",
    "權證ROI(%)": "return_pct",
    "當日成交量": "volume",
    "當日成交金額": "turnover",
    "累積履約數": "exercised_cum",
    "未履約數": "unexercised",
    "權證理論價格(元)": "tej_theo_price",
    "權證高估(元)": "tej_overvalue",
    "權證高估%": "tej_overvalue_pct",
    "歷史波動性": "tej_hist_vol",
    "隱含波動": "tej_iv",
    "履約價(元)": "strike",
    "剩餘期間(日)": "days_to_expiry",
    "溢價比率%": "premium_pct",
    "成本槓桿": "cost_leverage",
    "有效槓桿": "effective_leverage",
    "DELTA": "tej_delta",
    "GAMMA": "tej_gamma",
    "VEGA": "tej_vega",
    "THETA": "tej_theta",
    "RHO": "tej_rho",
    "內含價值": "intrinsic",
    "時間價值": "time_value",
    "價內外": "moneyness_label",
    "標的證券價格(元)": "underlying_price",
    "標的證券ROI%": "underlying_return_pct",
    "標的證券": "underlying_raw",
}

TERMS_DATE_COLUMNS = [
    "event_date", "issue_date", "listing_date", "expiry_date", "last_trade_date",
    "scheduled_last_trade_date", "exercise_start", "exercise_end",
    "reset_start", "reset_end", "reset_date",
]

# Issuers that appear in Taiwan warrant short names (e.g. 啟碁台新5A售02).
ISSUERS = [
    "元大", "凱基", "群益", "富邦", "統一", "永豐", "國泰", "兆豐", "台新", "元富",
    "中信", "第一", "康和", "華南", "日盛", "亞東", "宏遠", "玉山", "國票", "麥證",
    "摩根", "麥格理", "法興", "德意志", "美林", "港商", "安泰", "大華", "福邦", "華信",
]
# Short name = underlying + issuer + 1-3 char year/month code + 購/售/牛/熊 + serial.
# Requiring the code right after the issuer avoids matching an underlying such
# as 台新金 in 台新金元大5A購01.
_ISSUER_RE = re.compile(
    "(" + "|".join(sorted(ISSUERS, key=len, reverse=True)) + r")[0-9A-Z]{1,3}[購售牛熊]"
)


def _read_any(path, sheet_name=0):
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet_name, dtype={"權證碼": str})
    return pd.read_csv(path, dtype={"權證碼": str})


def parse_underlying(raw):
    """'6285.TW 啟碁' -> ('6285', '啟碁');  '6285   啟碁' -> ('6285', '啟碁')."""
    if pd.isna(raw):
        return None, None
    text = str(raw).strip()
    match = re.match(r"^([0-9A-Za-z]+)(?:\.[A-Za-z]+)?\s*(.*)$", text)
    if not match:
        return None, text or None
    return match.group(1), (match.group(2).strip() or None)


def parse_warrant_type(text):
    """'單一個股之歐式認售權證' -> ('put', 'european')."""
    if pd.isna(text):
        return None, None
    text = str(text)
    if "售" in text or "熊" in text:
        kind = "put"
    elif "購" in text or "牛" in text:
        kind = "call"
    else:
        kind = None
    if "美式" in text:
        style = "american"
    elif "歐式" in text:
        style = "european"
    else:
        style = None
    return kind, style


def parse_issuer(name):
    """'啟碁台新5A售02' -> '台新'. Returns None if no known issuer is found."""
    if pd.isna(name):
        return None
    match = _ISSUER_RE.search(str(name))
    return match.group(1) if match else None


def _to_dates(df, columns):
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col].replace({"-": None, "": None}), errors="coerce")
    return df


def read_tej_terms(path, sheet_name=0):
    """Read a TEJ warrant terms/events export into a clean DataFrame."""
    df = _read_any(path, sheet_name).rename(columns=TERMS_COLUMNS)
    df = df.drop(columns=[c for c in df.columns if str(c).startswith("重設說明")], errors="ignore")
    df["warrant_id"] = df["warrant_id"].astype(str).str.strip()
    df = _to_dates(df, TERMS_DATE_COLUMNS)

    parsed = df["underlying_raw"].map(parse_underlying)
    df["underlying_id"] = parsed.map(lambda x: x[0])
    df["underlying_name"] = parsed.map(lambda x: x[1])

    types = df["warrant_type"].map(parse_warrant_type)
    df["kind"] = types.map(lambda x: x[0])
    df["style"] = types.map(lambda x: x[1])
    df["issuer"] = df["name"].map(parse_issuer)

    if "issue_vol_pct" in df.columns:
        df["issue_vol"] = pd.to_numeric(df["issue_vol_pct"], errors="coerce") / 100.0
    # Fall back to event-level strike/ratio when "current" columns are missing.
    for cur, evt in (("strike", "strike_event"), ("ratio", "ratio_event")):
        if cur not in df.columns and evt in df.columns:
            df[cur] = df[evt]
    sort_cols = [c for c in ("warrant_id", "event_date", "event_seq") if c in df.columns]
    return df.sort_values(sort_cols).reset_index(drop=True)


def read_tej_daily(path, sheet_name=0):
    """Read a TEJ warrant daily-trading export into a clean DataFrame."""
    df = _read_any(path, sheet_name).rename(columns=DAILY_COLUMNS)
    df["warrant_id"] = df["warrant_id"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # 標的證券 sometimes comes as '6285   啟碁' in one cell.
    parsed = df["underlying_raw"].map(parse_underlying)
    df["underlying_id"] = parsed.map(lambda x: x[0])
    df["underlying_name"] = parsed.map(lambda x: x[1])

    # TEJ hist vol / IV come as decimals (0.66 = 66%); keep them as decimals.
    df["T"] = pd.to_numeric(df["days_to_expiry"], errors="coerce") / 365.0
    df["traded"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0) > 0
    return df.sort_values(["warrant_id", "date"]).reset_index(drop=True)


def terms_as_of(terms, date):
    """Terms valid on `date`: the latest event on or before that date, per warrant."""
    date = pd.Timestamp(date)
    known = terms[terms["event_date"].isna() | (terms["event_date"] <= date)]
    return known.groupby("warrant_id", as_index=False).tail(1).reset_index(drop=True)


def merge_daily_with_terms(daily, terms):
    """Attach the terms valid on each trading day (point-in-time, no look-ahead).

    Uses merge_asof on event_date so a strike reset on day D only affects rows
    from day D onwards.
    """
    term_cols = [
        c for c in ("warrant_id", "event_date", "event_seq", "kind", "style", "issuer",
                    "ratio", "strike", "expiry_date", "last_trade_date", "issue_vol",
                    "underlying_id", "barrier")
        if c in terms.columns
    ]
    t = terms[term_cols].copy()
    t["event_date"] = t["event_date"].fillna(pd.Timestamp("1900-01-01"))
    sort_by = ["event_date"] + (["event_seq"] if "event_seq" in t.columns else [])
    t = t.sort_values(sort_by)
    d = daily.sort_values("date")

    merged = pd.merge_asof(
        d, t, left_on="date", right_on="event_date", by="warrant_id",
        direction="backward", suffixes=("", "_terms"),
    )
    # Daily table already has today's strike; keep the terms one only as a check.
    if "strike_terms" in merged.columns:
        merged["strike_mismatch"] = ~np.isclose(merged["strike"], merged["strike_terms"], equal_nan=True)
    if "underlying_id_terms" in merged.columns:
        merged = merged.drop(columns=["underlying_id_terms"])
    return merged.sort_values(["warrant_id", "date"]).reset_index(drop=True)
