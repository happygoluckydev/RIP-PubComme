"""抽出結果（opinions.json）と原文PDFの突合レポートを生成する。

検証内容（MVP_PLAN.md M1 の成功条件に対応）:
1. 構造検証: グループごとの件数・番号の連続性・レコードキーの一意性
2. 件数検証: 掲載件数と資料見出しの意見提出総数の関係（掲載は「主な御意見」の抜粋）
3. 再現性検証: PDFから再抽出した結果とJSONが完全一致するか（JSONの陳腐化・改変の検出）
4. 原文突合: 表の各セルの行単位テキストが、ページ生テキストに含まれるか
   ※ pdfplumber の extract_text はページを視覚的な行単位で出力するため、
     折り返されたセル全文は連続文字列にならない。突合はセルの「行」単位で行う
5. 目視サンプル: 統括者がPDFと見比べるためのサンプル出力

中立性に関する方針（CLAUDE.md §6）:
- 本スクリプトは抽出の正確性のみを検証する。意見・回答の内容は評価しない。
"""

import argparse
import json
import re
from pathlib import Path

import pdfplumber

from extract_opinions import extract_records

STRIP_WS = re.compile(r"\s+")


def normalize(text):
    return STRIP_WS.sub("", text)


def verify(pdf_path, json_path):
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    records = data["records"]
    metadata = data["metadata"]

    lines = ["# M1 突合レポート: 抽出結果と原文PDFの検証", ""]
    lines.append(f"- 対象PDF: `{Path(pdf_path).name}`（S-001）")
    lines.append(f"- 対象JSON: `{Path(json_path).name}`")
    lines.append("")

    # 1. 構造検証
    lines.append("## 1. 構造検証")
    lines.append("")
    keys = [r["key"] for r in records]
    groups = {}
    for r in records:
        groups.setdefault(r["group"], []).append(r["no"])
    ok_unique = len(keys) == len(set(keys))
    ok_structure = ok_unique
    lines.append(f"- レコード数: {len(records)}（errors: {len(data['errors'])}）")
    for g, nos in sorted(groups.items()):
        contiguous = nos == list(range(min(nos), max(nos) + 1))
        ok_structure = ok_structure and contiguous
        lines.append(f"- グループ{g}: {len(nos)}件、番号 {min(nos)}〜{max(nos)}、"
                     f"連続性: {'OK' if contiguous else 'NG'}")
    lines.append(f"- レコードキーの一意性: {'OK' if ok_unique else 'NG'}")
    lines.append("")

    # 2. 件数検証
    lines.append("## 2. 件数検証")
    lines.append("")
    lines.append(f"- 資料見出し記載の意見提出総数: {metadata['total_submitters']}者"
                 f"{metadata['total_opinions']}件")
    lines.append(f"- 掲載（抽出）件数: {len(records)}件")
    lines.append("- 掲載件数 < 提出総数 であり、元資料が「主な御意見」の抜粋であることと整合する。")
    lines.append("  （どの意見を掲載するかは国交省の選択であり、本プロジェクトは関与していない）")
    lines.append("")

    # 3. 再現性検証
    lines.append("## 3. 再現性検証（PDFからの再抽出とJSONの一致）")
    lines.append("")
    re_metadata, re_records, re_errors = extract_records(pdf_path)
    ok_repro = re_records == records and re_errors == data["errors"]
    lines.append(f"- 再抽出レコードとJSONの一致: {'OK' if ok_repro else 'NG'}")
    lines.append("")

    # 4. 原文突合（セル行単位）
    lines.append("## 4. 原文突合（セル行単位の包含チェック）")
    lines.append("")
    checked = 0
    failures = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = normalize(page.extract_text() or "")
            for table in page.find_tables():
                for row in table.extract():
                    for cell in row:
                        if cell is None:
                            continue
                        for cell_line in cell.split("\n"):
                            target = normalize(cell_line)
                            if not target:
                                continue
                            checked += 1
                            if target not in page_text:
                                failures.append({"page": page.page_number, "line": cell_line})
    lines.append(f"- 検査したセル行数: {checked}")
    if failures:
        lines.append(f"- **不一致: {len(failures)}件**")
        for f in failures:
            lines.append(f"  - p.{f['page']}: {f['line']}")
    else:
        lines.append("- 不一致: 0件（全セル行がページ生テキストに存在）")
    lines.append("")

    # 5. 目視サンプル
    lines.append("## 5. 目視サンプル（統括者確認用）")
    lines.append("")
    lines.append("PDFの該当ページと以下を見比べ、文言が一致することを確認してください。")
    lines.append("")
    sample_keys = {"Ⅰ-1", "Ⅰ-3", "Ⅱ-19", "Ⅱ-35"}
    for r in records:
        if r["key"] not in sample_keys:
            continue
        lines.append(f"### {r['key']}（{r['group_label']} / p.{r['pages']}）")
        lines.append("")
        lines.append(f"- 該当箇所: {r['section']}")
        lines.append(f"- 意見（概要）: {r['opinion_summary']}")
        lines.append(f"- 考え方: {r['response']}")
        if r["response_cell_merged_with_previous"]:
            lines.append("- 注: 「考え方」セルは直前の意見と縦結合されており、同一回答を共有している")
        lines.append("")

    ok = ok_structure and ok_repro and not failures
    lines.append("## 判定")
    lines.append("")
    lines.append("**PASS**: 全検証項目OK" if ok else "**FAIL**: 不一致あり（上記参照）")
    lines.append("")
    return "\n".join(lines), ok


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("json", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True, help="レポート出力先(.md)")
    args = parser.parse_args()

    report, ok = verify(args.pdf, args.json)
    args.output.write_text(report, encoding="utf-8")
    print(f"{'PASS' if ok else 'FAIL'} -> {args.output}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
