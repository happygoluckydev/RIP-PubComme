"""RSSスナップショットからPhase 1に関係する可能性がある案件を文字列一致で抽出する。

扱う事実は、公開されたRSSのタイトル・カテゴリ・所管に定義済みキーワードが現れることだけである。
一致は掲載可否・重要性・内容の評価を意味しない。不一致も対象外を意味しない。
"""

import argparse
import json
from pathlib import Path


PHASE1_KEYWORDS = (
    "ライドシェア",
    "道路運送",
    "旅客自動車運送",
    "貨物自動車運送",
    "自家用有償旅客運送",
    "物流",
    "トラック",
    "タクシー",
)
MATCH_FIELDS = ("title", "category", "contact")


def find_phase1_signals(items):
    """キーワードが含まれるRSS項目と一致箇所を返す。"""
    matches = []
    for item in items:
        matched_keywords = []
        matched_fields = []
        for field in MATCH_FIELDS:
            text = item.get(field) or ""
            found = [keyword for keyword in PHASE1_KEYWORDS if keyword in text]
            if found:
                matched_fields.append(field)
                matched_keywords.extend(found)
        if matched_keywords:
            matches.append({
                "item": item,
                "matched_keywords": list(dict.fromkeys(matched_keywords)),
                "matched_fields": matched_fields,
            })
    return matches


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("snapshot", type=Path, help="RSSスナップショットJSONのパス")
    parser.add_argument("-o", "--output", type=Path, required=True, help="候補目印JSONの出力先")
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    signals = find_phase1_signals(snapshot["items"])
    output = {
        "metadata": {
            "source_url": snapshot["metadata"]["source_url"],
            "source_fetched_at": snapshot["metadata"]["fetched_at"],
            "keywords": list(PHASE1_KEYWORDS),
            "note": "文字列一致による候補目印。不一致は対象外、一覧は掲載候補を意味しない。",
        },
        "signals": signals,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"phase 1 signals: {len(signals)} -> {args.output}")


if __name__ == "__main__":
    main()
