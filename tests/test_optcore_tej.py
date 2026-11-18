"""TEJ reader tests using synthetic files that copy TEJ's real headers."""

import pandas as pd
import pytest

from optcore.data import merge_daily_with_terms, read_tej_daily, read_tej_terms, terms_as_of
from optcore.data.tej import parse_issuer, parse_underlying, parse_warrant_type


def _terms_frame():
    base = {
        "名稱": "啟碁台新5A售02", "權證碼": "03001T", "標的證券碼": "6285.TW 啟碁",
        "履約價幣別": "NTD", "權證全稱": "啟碁台新5A售02", "履約方式": "現金",
        "發行日": "2026/04/15", "上市日": "2026/04/17", "到期日": "2026/10/16",
        "存續期間(年)": 0.5, "權證類型": "單一個股之歐式認售權證", "權證衍生種類": "一般型",
        "發行單位": 5000, "發行價格(台幣元)": 2.25, "發行履約價(元)": 210,
        "目前上(下)限價(台幣元)": None, "掛牌交易所": "台灣交易所",
        "最後交易日": "2026/10/14", "發行日波動率": 87.86, "重設期間起日": "-",
        "重設說明1": None,
    }
    issue = {**base, "事件日": "2026/04/15", "序號": 1, "事件說明": "發行",
             "行使比例": 0.05, "履約價(元)": 210.0, "目前履約價(元)": 210.0, "目前行使比例": 0.05}
    reset = {**base, "事件日": "2026/07/01", "序號": 1, "事件說明": "重設",
             "行使比例": 0.051, "履約價(元)": 206.52, "目前履約價(元)": 206.52, "目前行使比例": 0.051}
    return pd.DataFrame([reset, issue])  # deliberately unsorted


def _daily_frame():
    rows = []
    for date, strike in (("2026/06/30", 210.0), ("2026/07/01", 206.52), ("2026/10/14", 206.52)):
        rows.append({
            "名稱": "啟碁台新5A售02", "權證碼": "03001T", "日期": date,
            "權證收盤價(元)": 0.1, "當日成交量": 0 if date == "2026/10/14" else 12,
            "隱含波動": 1.1875, "歷史波動性": 0.6597, "履約價(元)": strike,
            "剩餘期間(日)": 7, "DELTA": -0.005, "標的證券價格(元)": 253, "標的證券": "6285   啟碁",
        })
    return pd.DataFrame(rows)


@pytest.fixture
def tej_files(tmp_path):
    terms_path = tmp_path / "tej_terms.xlsx"
    daily_path = tmp_path / "tej_daily.csv"
    _terms_frame().to_excel(terms_path, index=False)
    _daily_frame().to_csv(daily_path, index=False)
    return terms_path, daily_path


def test_parsers():
    assert parse_underlying("6285.TW 啟碁") == ("6285", "啟碁")
    assert parse_underlying("6285   啟碁") == ("6285", "啟碁")
    assert parse_warrant_type("單一個股之歐式認售權證") == ("put", "european")
    assert parse_warrant_type("單一個股之美式認購權證") == ("call", "american")
    assert parse_issuer("啟碁台新5A售02") == "台新"
    assert parse_issuer("台積電凱基67售14") == "凱基"
    assert parse_issuer("台新金元大5A購01") == "元大"  # underlying name contains an issuer
    assert parse_issuer("沒有發行商") is None


def test_read_terms(tej_files):
    terms = read_tej_terms(tej_files[0])
    assert list(terms["event"]) == ["發行", "重設"]  # sorted by event date
    row = terms.iloc[-1]
    assert row["warrant_id"] == "03001T"
    assert row["underlying_id"] == "6285"
    assert (row["kind"], row["style"], row["issuer"]) == ("put", "european", "台新")
    assert row["issue_vol"] == pytest.approx(0.8786)
    assert pd.isna(row["reset_start"])  # "-" becomes NaT
    assert not any(c.startswith("重設說明") for c in terms.columns)


def test_terms_as_of_has_no_look_ahead(tej_files):
    terms = read_tej_terms(tej_files[0])
    assert terms_as_of(terms, "2026/06/30").iloc[0]["strike"] == 210.0
    assert terms_as_of(terms, "2026/07/01").iloc[0]["strike"] == 206.52


def test_read_daily_and_merge(tej_files):
    terms = read_tej_terms(tej_files[0])
    daily = read_tej_daily(tej_files[1])
    assert daily["underlying_id"].iloc[0] == "6285"
    assert daily["T"].iloc[0] == pytest.approx(7 / 365)
    assert list(daily["traded"]) == [True, True, False]

    merged = merge_daily_with_terms(daily, terms)
    assert list(merged["ratio"]) == [0.05, 0.051, 0.051]
    assert merged["kind"].eq("put").all()
    assert not merged["strike_mismatch"].any()
