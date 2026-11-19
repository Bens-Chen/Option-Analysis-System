"""TEJ bulk export conversion (UTF-16, tab separated, code+name in one cell)."""

import pandas as pd

from optcore.data.tej import merge_daily_with_terms
from optcore.data.tej_bulk import convert_daily, convert_terms

DAILY_HEADER = ["證券代碼", "年月日", "權證開盤價(元)", "權證最高價(元)", "權證最低價(元)", "權證收盤價(元)", "權證ROI(%)",
                "當日成交量", "當日成交金額", "累積履約數", "未履約數", "權證理論價格(元)", "權證高估(元)", "權證高估%",
                "歷史波動性", "隱含波動", "履約價(元)", "剩餘期間(日)", "溢價比率%", "成本槓桿", "有效槓桿", "DELTA",
                "GAMMA", "VEGA", "THETA", "RHO", "內含價值", "時間價值", "價內外", "標的證券價格(元)", "標的證券ROI%", "標的證券"]


def _write_utf16(path, header, rows):
    text = "\r\n".join("\t".join(map(str, r)) for r in [header, *rows]) + "\r\n"
    path.write_bytes(text.encode("utf-16"))


def test_daily_conversion_streams_chunks_and_parses_types(tmp_path):
    rows = [
        ["030001T 大同凱基51購02", "20260102", 0.21, 0.21, 0.21, 0.21, ".", 0, 0, 9500, 500, 0.21, 0, 0, 0.3849,
         0.5983, 37.0, 33, 22.04, 65.79, 11.247, 0.077, 0.021, 1.054, -0.014, 0.19, 0.0, 0.21, "價外", 30.7, -2.69, "2371   大同"],
        ["030001T 大同凱基51購02", "20260105", 0.25, 0.25, 0.25, 0.25, 19.0, 12, 3, 9500, 512, ".", ".", ".", 0.38,
         0.61, 37.0, 32, 21.0, 60.0, 11.0, 0.08, 0.02, 1.0, -0.01, 0.2, 0.0, 0.25, "價外", 31.0, 0.98, "2371   大同"],
        ["03002TZ 技嘉凱基33售13", "20260102", 1.46, 1.46, 1.46, 1.46, ".", 0, 0, 4500, 500, 1.43, 0.03, 2.03, 0.52,
         0.51, 280.0, 86, 6.55, 6.11, -3.66, -0.021, 0.0, 1.66, -1.8, -1.6, 0.88, 0.56, "價內", 255.0, -4.1, "2376   技嘉"],
    ]
    src = tmp_path / "daily.txt"
    _write_utf16(src, DAILY_HEADER, rows)
    out = tmp_path / "daily.parquet"
    assert convert_daily([src], out, chunksize=2, log=lambda *_: None) == 3
    df = pd.read_parquet(out)
    first = df.iloc[0]
    assert (first["warrant_id"], first["name"]) == ("030001T", "大同凱基51購02")
    assert first["date"] == pd.Timestamp("2026-01-02")
    assert (first["underlying_id"], first["underlying_name"]) == ("2371", "大同")
    assert pd.isna(first["return_pct"])  # "." -> NaN
    assert df["unexercised"].tolist() == [500, 512, 500]
    assert df["traded"].tolist() == [False, True, False]
    assert df.loc[1, "T"] == 32 / 365


def test_terms_conversion_and_merge(tmp_path):
    header = ["證券代碼", "年月日", "序號", "履約方式", "標的證券碼", "行使比例", "履約價(元)", "履約價幣別", "事件說明",
              "權證全稱", "履約方式", "發行日", "到期日", "權證類型", "權證衍生種類", "目前履約價(元)", "目前行使比例",
              "最後交易日", "發行日波動率", "重設說明", "重設說明1"]
    rows = [
        ["030001T 大同凱基51購02", "20251201", "1 ", ".", "2371.TW 大同", "0.16", "37.5", "NTD", "上市櫃", "大同凱基51購02",
         "現金", "20251128", "20260204", "單一個股之美式認購權證", "一般型", "37.5", "0.16", "20260202", "70.0", "-", "."],
        ["030001T 大同凱基51購02", "20260103", "1 ", ".", "2371.TW 大同", "0.161", "37.0", "NTD", "除權息", "大同凱基51購02",
         "現金", "20251128", "20260204", "單一個股之美式認購權證", "一般型", "37.0", "0.161", "20260202", "70.0", "-", "."],
    ]
    src = tmp_path / "terms.csv"
    _write_utf16(src, header, rows)
    out = tmp_path / "terms.parquet"
    assert convert_terms([src, src], out, log=lambda *_: None) == 2  # duplicates across files dropped
    terms = pd.read_parquet(out)
    assert set(terms["kind"]) == {"call"} and set(terms["style"]) == {"american"}
    assert set(terms["issuer"]) == {"凱基"} and set(terms["settlement"]) == {"現金"}
    assert terms["issue_vol"].iloc[0] == 0.70
    assert not any(c.startswith("重設說明") for c in terms.columns)

    daily = pd.DataFrame({"warrant_id": ["030001T"] * 2, "date": pd.to_datetime(["2026-01-02", "2026-01-05"]),
                          "strike": [37.5, 37.0]})
    merged = merge_daily_with_terms(daily, terms)
    assert merged["ratio"].tolist() == [0.16, 0.161]  # point in time: adjustment applies from 01-03
