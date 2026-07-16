"""パブコメ結果PDF（意見・考え方の対応表）から意見・回答ペアを抽出する。

対象: S-001 資料６「交通政策基本計画（素案）に対する主な御意見（パブリックコメント）
及びそれに対する考え方」（docs/SOURCES.md 参照）。

元資料の構造（2026-07-16 実物確認）:
- ページ1見出しに意見提出総数（33者62件）と意見募集期間の記載がある
- 表は2グループ:「Ⅰ．当該意見を踏まえて内容を修正するもの」「Ⅱ．その他の主な意見」。
  グループごとに番号が1から振り直されるため、レコードキーはグループ＋番号で一意化する
- 「該当箇所」「意見に対する考え方」セルは縦結合されることがある（複数の意見が
  同一の回答を共有する）。結合は response_cell_merged_with_previous として明示する

中立性に関する方針（CLAUDE.md §3・§6）:
- 本スクリプトが中立的事実として扱うのは「PDFに記載された文言そのもの」のみ。
  加工はセル内の改行除去（行の連結）に限る。要約・言い換え・評価は行わない。
- 縦結合セルの回答は「共有された同一回答」であり、行政による回答文の使い回し
  （コピペ）とは区別する。使い回し検出（M2）はこのフラグを除外条件に使うこと。
- 抽出できなかった行は捨てずに errors として出力し、欠損を明示する（歪曲の回避）。

注意: 掲載されている意見は国交省による「主な御意見」の抜粋・概要であり全意見ではない
（掲載38件 < 提出総数62件）。この事実は出力JSONの metadata に必ず含める。
"""

import argparse
import json
import re
from pathlib import Path

import pdfplumber

SOURCE_ID = "S-001"
# 元資料の表ヘッダー（この4列構造でないページが現れた場合はエラーとして報告する）
EXPECTED_HEADER = ["該当箇所", "番号", "素案に対する意見（概要）", "意見に対する考え方"]
# グループ見出し（例:「Ⅰ．当該意見を踏まえて内容を修正するもの」）
GROUP_HEADING_RE = re.compile(r"([ⅠⅡⅢⅣⅤ])．(\S+)")
# ページ1見出しの提出総数・募集期間（例:「※パブリックコメント意見提出総数 33者62件
# （意見募集期間：令和７年10月31日～11月21日）」）
TOTALS_RE = re.compile(r"意見提出総数\s*(\d+)者(\d+)件")
PERIOD_RE = re.compile(r"意見募集期間：(\S+?)～(\S+?)[）)]")


def join_cell_lines(cell):
    """セル内の改行を除去して1つの文字列にする。

    日本語文が印刷幅で折り返されているだけなので、行は区切り文字なしで連結する。
    行内の空白や文字はそのまま保持する（原文の改変を最小化するため）。
    """
    if cell is None:
        return ""
    return "".join(line.strip() for line in cell.split("\n"))


def is_header_row(row):
    return [join_cell_lines(c) for c in row] == EXPECTED_HEADER


def parse_page_headings(page, table_bboxes):
    """表領域の外にあるテキスト（グループ見出し・資料見出し）を取り出す。"""

    def outside(word):
        for x0, top, x1, bottom in table_bboxes:
            if word["top"] >= top and word["bottom"] <= bottom:
                return False
        return True

    return " ".join(w["text"] for w in page.extract_words() if outside(w))


def extract_records(pdf_path):
    """PDFの全ページから意見・回答ペアを抽出する。

    Returns:
        (metadata, records, errors)
        metadata: 資料見出しから機械抽出した事実（提出総数・募集期間・見出し原文）
        records: 意見・回答ペアのリスト（グループ＋番号で一意）
        errors: 構造が想定と異なり取り込めなかった行（欠損の明示用）
    """
    records = []
    errors = []
    heading_texts = []
    current_group = None  # (グループ記号, 見出し文言)
    last_section = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_no = page.page_number
            tables = page.find_tables()
            heading = parse_page_headings(page, [t.bbox for t in tables])
            if heading:
                heading_texts.append({"page": page_no, "text": heading})
            m = GROUP_HEADING_RE.search(heading)
            if m:
                current_group = (m.group(1), f"{m.group(1)}．{m.group(2)}")

            if not tables:
                errors.append({"page": page_no, "reason": "テーブルが検出できないページ"})
                continue

            for table in tables:
                raw_rows = table.extract()
                for row_idx, row in enumerate(raw_rows):
                    if is_header_row(row):
                        continue
                    if len(row) != len(EXPECTED_HEADER):
                        errors.append({
                            "page": page_no,
                            "reason": f"想定外の列数({len(row)})",
                            "row": [join_cell_lines(c) for c in row],
                        })
                        continue

                    raw_section, raw_number, raw_opinion, raw_response = row
                    number = join_cell_lines(raw_number)
                    opinion = join_cell_lines(raw_opinion)
                    response = join_cell_lines(raw_response)
                    # 縦結合セルは extract() で None になる（空文字列とは区別できる）
                    section_merged = raw_section is None
                    response_merged = raw_response is None

                    if number == "":
                        # 番号なし行 = 直前レコードのページまたぎ分割行として連結
                        if not records:
                            errors.append({"page": page_no, "reason": "先頭に番号なし行",
                                           "row": [join_cell_lines(c) for c in row]})
                            continue
                        prev = records[-1]
                        prev["opinion_summary"] += opinion
                        prev["response"] += response
                        if page_no not in prev["pages"]:
                            prev["pages"].append(page_no)
                        continue

                    if not number.isdigit():
                        errors.append({"page": page_no, "reason": f"番号が数値でない({number})",
                                       "row": [join_cell_lines(c) for c in row]})
                        continue

                    if current_group is None:
                        errors.append({"page": page_no, "reason": "グループ見出し未検出のままの行",
                                       "row": [join_cell_lines(c) for c in row]})
                        continue

                    section = join_cell_lines(raw_section)
                    if section:
                        last_section = section
                    if response_merged and records:
                        # 直前の意見と同一の回答セルを共有している（行政の記載事実）
                        response = records[-1]["response"]

                    records.append({
                        "key": f"{current_group[0]}-{number}",
                        "group": current_group[0],
                        "group_label": current_group[1],
                        "no": int(number),
                        "section": section if not section_merged else last_section,
                        "opinion_summary": opinion,
                        "response": response,
                        "response_cell_merged_with_previous": response_merged,
                        "pages": [page_no],
                    })

    all_heading = " ".join(h["text"] for h in heading_texts)
    totals = TOTALS_RE.search(all_heading)
    period = PERIOD_RE.search(all_heading)
    metadata = {
        "source_id": SOURCE_ID,
        "source_file": Path(pdf_path).name,
        "headings_verbatim": heading_texts,
        "total_submitters": int(totals.group(1)) if totals else None,
        "total_opinions": int(totals.group(2)) if totals else None,
        "comment_period_verbatim": (
            f"{period.group(1)}～{period.group(2)}" if period else None
        ),
        "note": (
            "掲載意見は国土交通省による「主な御意見」の抜粋・概要であり、"
            "提出された全意見の一覧ではない（掲載件数 < 意見提出総数）。"
            "意見・回答の文言はPDF記載のまま（セル内改行の除去のみ）。"
        ),
        "record_count": len(records),
        "error_count": len(errors),
    }
    return metadata, records, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path, help="入力PDF（data/raw/ 配下の原文）")
    parser.add_argument("-o", "--output", type=Path, required=True, help="出力JSONパス")
    args = parser.parse_args()

    metadata, records, errors = extract_records(args.pdf)
    output = {"metadata": metadata, "records": records, "errors": errors}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"records: {len(records)}, errors: {len(errors)} -> {args.output}")


if __name__ == "__main__":
    main()
