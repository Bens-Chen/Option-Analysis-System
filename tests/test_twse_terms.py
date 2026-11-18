"""TWSE warrant terms parser (no network)."""

import pandas as pd
import pytest

from optcore.data.tej import terms_as_of
from optcore.data.twse import load_terms, parse_remark_events, parse_twse_terms, roc_date


def _row(**kw):
    row = {
        "出表日期": "1151112", "權證代號": "03011T", "權證簡稱": "台積電凱基67售14", "權證類型": "認售", "類別": "一般型",
        "流動量提供者報價方式": "主動報價", "履約開始日": "1160719", "最後交易日": "1160715", "履約截止日": "1160719",
        "發行單位數量(仟單位)": "5000", "結算方式(詳附註編號說明)": "2", "標的證券/指數": "台積電",
        "最新標的履約配發數量(每仟單位權證)": "10.00", "原始履約價格(元)/履約指數": "1750.0000",
        "原始上限價格(元)/上限指數": "0.0000", "原始下限價格(元)/下限指數": "0.0000",
        "最新履約價格(元)/履約指數": "1740.2200", "最新上限價格(元)/上限指數": "0.0000",
        "最新下限價格(元)/下限指數": "0.0000",
        "備註": "◎2026/05/21申請自行註銷權證2,400仟單位，剩餘權證2,600仟單位。\r\n"
                "◎2026/06/11標的證券除息，調整後履約價格1,745.34元，調整後行使比例0.0100。\r\n"
                "◎2026/09/16標的證券除息，調整後履約價格1,740.22元，調整後行使比例0.0100。",
    }
    row.update(kw)
    return row


def test_roc_date():
    assert roc_date("1151016") == pd.Timestamp("2026-10-16")
    assert pd.isna(roc_date(""))


def test_remark_events_reset_and_dividend():
    text = "◎ 生效日期2026/05/21，重設後履約價(元)/點數：2,195.00\r\n◎2026/06/11標的證券除息，調整後履約價格2,189.16元，調整後行使比例0.0030。"
    events = parse_remark_events(text)
    assert [(e[1], e[2]) for e in events] == [("履約價重設", 2195.0), ("除權息調整", 2189.16)]


def test_terms_are_point_in_time():
    terms = parse_twse_terms([_row()])
    assert set(terms["kind"]) == {"put"} and set(terms["style"]) == {"european"}
    assert set(terms["issuer"]) == {"凱基"} and set(terms["ratio"]) == {0.01}
    assert terms["expiry_date"].iloc[0] == pd.Timestamp("2027-07-19")
    strike_on = lambda day: terms_as_of(terms, day)["strike"].iloc[0]
    assert strike_on("2026-06-10") == 1750.0
    assert strike_on("2026-06-11") == 1745.34
    assert strike_on("2026-11-12") == 1740.22


def test_american_style_and_unparsed_adjustment_fallback():
    row = _row(**{"權證代號": "030573", "權證簡稱": "台積電元大57購01", "權證類型": "認購", "履約開始日": "1140805",
                  "備註": "不明格式", "最新履約價格(元)/履約指數": "1700.0000"})
    terms = parse_twse_terms([row])
    assert terms["style"].iloc[0] == "american" and terms["kind"].iloc[0] == "call"
    assert terms["event"].iloc[-1] == "未解析調整"
    assert terms_as_of(terms, "2026-11-12")["strike"].iloc[0] == 1700.0


def test_filter_by_underlying_and_load_snapshots(tmp_path):
    other = _row(**{"權證代號": "039999", "標的證券/指數": "鴻海", "權證簡稱": "鴻海元大5A購01", "備註": "",
                    "最新履約價格(元)/履約指數": "1750.0000"})
    assert set(parse_twse_terms([_row(), other], "台積電")["warrant_id"]) == {"03011T"}

    pd.DataFrame([_row(**{"出表日期": "1151001"}), other | {"出表日期": "1151001"}]).to_parquet(tmp_path / "raw_20261001.parquet")
    pd.DataFrame([_row()]).to_parquet(tmp_path / "raw_20261112.parquet")  # 鴻海 warrant has dropped out
    terms = load_terms(tmp_path)
    assert set(terms["warrant_id"]) == {"03011T", "039999"}
    assert terms.loc[terms["warrant_id"] == "03011T", "snapshot_date"].nunique() == 1
    with pytest.raises(FileNotFoundError):
        load_terms(tmp_path / "empty")
