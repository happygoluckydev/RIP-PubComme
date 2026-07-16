"""extract_opinions.py の純粋関数・正規表現のテスト。

PDF実ファイルへの依存は最小化し、文字列処理のみを検証する
（外部データに依存する検証は analysis/verify_extraction.py が担う）。
"""

from extract_opinions import (
    GROUP_HEADING_RE,
    PERIOD_RE,
    TOTALS_RE,
    is_header_row,
    join_cell_lines,
)


# --- join_cell_lines ---

def test_セル行連結_改行は区切りなしで連結():
    assert join_cell_lines("日本語の文が\n折り返されている") == "日本語の文が折り返されている"


def test_セル行連結_Noneは空文字列():
    assert join_cell_lines(None) == ""


def test_セル行連結_行内の空白は保持():
    # 行内に元からある空白は原文の一部として保持する（改変の最小化）
    assert join_cell_lines("A B\nCD") == "A BCD"


def test_セル行連結_空文字列は空文字列():
    assert join_cell_lines("") == ""


# --- is_header_row ---

def test_ヘッダー行判定_一致():
    row = ["該当箇所", "番号", "素案に対する意見（概要）", "意見に対する考え方"]
    assert is_header_row(row)


def test_ヘッダー行判定_改行入りでも一致():
    row = ["該当箇所", "番号", "素案に対する意見\n（概要）", "意見に対する考え方"]
    assert is_header_row(row)


def test_ヘッダー行判定_データ行は不一致():
    row = ["第２章", "1", "意見本文", "回答本文"]
    assert not is_header_row(row)


# --- 見出しの正規表現 ---

def test_総数抽出_者数と件数を取得():
    m = TOTALS_RE.search("※パブリックコメント意見提出総数 33者62件")
    assert m and m.group(1) == "33" and m.group(2) == "62"


def test_総数抽出_該当なしはNone():
    assert TOTALS_RE.search("意見募集の結果について") is None


def test_募集期間抽出_開始と終了を取得():
    m = PERIOD_RE.search("（意見募集期間：令和７年10月31日～11月21日）")
    assert m and m.group(1) == "令和７年10月31日" and m.group(2) == "11月21日"


def test_グループ見出し抽出_ローマ数字と文言():
    m = GROUP_HEADING_RE.search("Ⅰ．当該意見を踏まえて内容を修正するもの")
    assert m and m.group(1) == "Ⅰ"
    m2 = GROUP_HEADING_RE.search("Ⅱ．その他の主な意見")
    assert m2 and m2.group(1) == "Ⅱ"
