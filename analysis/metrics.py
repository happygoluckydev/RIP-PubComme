"""意見・回答ペアに対する構造的指標の算出（CLAUDE.md §3.1 の範囲のみ）。

本モジュールが中立的事実として扱うもの・評価しないもの（CLAUDE.md §6）:
- 扱う事実: 回答文の文字数、定義済みリストとの文字列一致（定型句）、
  複数回答間の文字列の一致・類似（使い回し）、特定パターンの出現（具体的参照）
- 評価しないもの: 回答内容の妥当性・具体性・誠実さ。文字数が多い/少ない、
  定型句がある/ない等が「良い/悪い」かの判断は本モジュールでは一切行わない。
  指標をどう解釈するかは閲覧者に委ねる（§3 中立性ガードレール）。
"""

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

# 定型句リスト
# 採録基準: 「意見の内容に依存せず、複数の回答・案件で繰り返し使用されうる締め文句・
# 常套句」であること。回答固有の名詞を含む文言は採録しない。
# このリスト自体が運営の判断を含む（何を定型句と見なすか）ため、変更は必ず
# プルリクエスト経由とし、変更時は既存データでの検出結果差分を提示する（CLAUDE.md §8）。
TEIKEIKU_PHRASES = [
    # 本案件（S-001）の回答文中に実際に出現する定型句
    "適切に対処して参ります",
    "適切に対処してまいります",
    "適切に対処をしてまいります",
    "記述しているところであり",
    "素案のとおり",
    "素案のまま",
    "引き続き検討を進めてまいります",
    # 他案件で頻出が知られる定型句（パブコメ回答の常套句）
    "ご意見として承ります",
    "御意見として承ります",
    "ご意見として承りました",
    "御意見として承りました",
    "今後の参考にさせていただきます",
    "参考にさせていただきます",
]

# 具体的参照の検出パターン
# 「具体的な参照が存在するか」という機械的事実のみを検出する。
# 参照の内容が適切か・十分かは判定しない。
CONCRETE_REFERENCE_PATTERNS = {
    # 計画本文のページ参照（例:【14ページ】）
    "page_reference": re.compile(r"【\d+ページ】"),
    # 法令の条文参照（例: 第12条）
    "article_reference": re.compile(r"第\d+条"),
    # 年月・年度の言及（例: 令和６年４月、2027年度、2021年11月）
    "date_reference": re.compile(r"(?:令和|平成)[0-9０-９元]+年|[0-9]{4}年"),
    # 数量の言及（例: 1万台、20-30%、２種）※数値＋単位のみを機械的に検出
    "quantity_reference": re.compile(r"[0-9０-９][0-9０-９,，.]*\s*(?:％|%|件|台|人|万|割|時間)"),
}

# 使い回し（類似回答）判定のしきい値
# SequenceMatcher.ratio() がこの値以上の回答ペアを「類似」として列挙する。
# しきい値の選定も運営判断を含むため、値はここで公開し、変更時は差分を提示する。
SIMILARITY_THRESHOLD = 0.9

# 回答構文パターン分類（docs/CLASSIFICATION_PROPOSALS.md 案B、2026-07-16 統括者承認）
# - 分類は「キーワードが回答文に含まれるか」という機械的事実のみに基づく。
#   回答の妥当性・誠実さの評価ではない（カテゴリ名も事実記述に徹し、評価語を使わない）
# - 複数パターンに該当する回答は複数カテゴリを付与する（マルチラベル）。
#   単一カテゴリへの圧縮は「どのパターンが主か」という判断を要するため行わない
# - キーワードは S-001（計画策定パブコメ）の回答文の観察から採録した。
#   案件を追加した際は網羅性を再検証し、変更は差分提示の上でPR経由とする（CLAUDE.md §8）
RESPONSE_CATEGORIES = {
    "shusei_tsuika": {
        "label": "「記述を追加・修正した」旨を含む回答",
        "keywords": ["記述を追加しました", "修正しました", "追記しました"],
    },
    "kisai_zumi": {
        "label": "「既に記述している」旨を含む回答",
        "keywords": ["記述しているところ", "記載しているところ", "おおむね記述"],
    },
    "soan_no_toori": {
        "label": "「素案のとおりとする」旨を含む回答",
        "keywords": ["素案のとおり", "素案のまま"],
    },
    "kento_keizoku": {
        "label": "「検討を継続する」旨を含む回答",
        "keywords": ["引き続き検討", "検討を進めてまいります"],
    },
    "kizon_torikumi": {
        "label": "「既存の取組を説明する」回答",
        "keywords": ["取り組んでおります", "行っており", "策定しているところ"],
    },
}
# 上記いずれにも該当しない回答に付与するカテゴリ
CATEGORY_OTHER = "sonota"


def response_char_count(text):
    """回答の文字数（空白除去後）。文字数の多寡の評価はしない。"""
    return len(re.sub(r"\s+", "", text))


def detect_teikeiku(text):
    """回答に含まれる定型句を列挙する（TEIKEIKU_PHRASES との文字列一致のみ）。"""
    return [p for p in TEIKEIKU_PHRASES if p in text]


def detect_concrete_references(text):
    """回答に含まれる具体的参照を種類別に列挙する（正規表現一致のみ）。"""
    return {name: pattern.findall(text) for name, pattern in CONCRETE_REFERENCE_PATTERNS.items()}


def classify_response(text):
    """回答文を構文パターンで分類する（マルチラベル、キーワード一致のみ）。

    どのカテゴリのキーワードにも該当しない場合は [CATEGORY_OTHER] を返す。
    「その他」の件数・割合は必ず公開し、分類の限界として明示する
    （docs/CLASSIFICATION_PROPOSALS.md）。
    """
    found = [cat for cat, spec in RESPONSE_CATEGORIES.items()
             if any(kw in text for kw in spec["keywords"])]
    return found if found else [CATEGORY_OTHER]


def find_duplicate_responses(records):
    """完全に同一の回答文を持つレコード群を列挙する。

    response_cell_merged_with_previous のレコードは除外する。
    （縦結合セルは「1つの回答セルを複数の意見が共有」という元資料のレイアウト上の
    事実であり、別々の回答として同文を繰り返し記載する「使い回し」とは区別する）
    """
    by_text = {}
    for r in records:
        if r.get("response_cell_merged_with_previous"):
            continue
        by_text.setdefault(r["response"], []).append(r["key"])
    return [{"keys": keys, "response": text}
            for text, keys in by_text.items() if len(keys) >= 2]


def find_similar_responses(records, threshold=SIMILARITY_THRESHOLD):
    """しきい値以上に類似する回答ペアを列挙する（完全一致ペアは除く）。

    完全一致は find_duplicate_responses が扱うため、ここでは ratio < 1.0 のみ返す。
    結合セルの除外基準は find_duplicate_responses と同じ。
    """
    targets = [r for r in records if not r.get("response_cell_merged_with_previous")]
    pairs = []
    for i, a in enumerate(targets):
        for b in targets[i + 1:]:
            if a["response"] == b["response"]:
                continue
            ratio = SequenceMatcher(None, a["response"], b["response"]).ratio()
            if ratio >= threshold:
                pairs.append({"keys": [a["key"], b["key"]], "ratio": round(ratio, 3)})
    return pairs


def compute_metrics(records):
    """全レコードの指標と、コーパス全体の使い回し検出結果を返す。"""
    per_record = []
    for r in records:
        per_record.append({
            "key": r["key"],
            "response_char_count": response_char_count(r["response"]),
            "teikeiku_found": detect_teikeiku(r["response"]),
            "concrete_references": detect_concrete_references(r["response"]),
            "categories": classify_response(r["response"]),
            "response_cell_merged_with_previous": r.get("response_cell_merged_with_previous", False),
        })
    n = len(records)
    with_teikeiku = sum(1 for m in per_record if m["teikeiku_found"])
    category_counts = {cat: 0 for cat in list(RESPONSE_CATEGORIES) + [CATEGORY_OTHER]}
    for m in per_record:
        for cat in m["categories"]:
            category_counts[cat] += 1
    corpus = {
        "record_count": n,
        "teikeiku_hit_count": with_teikeiku,
        "duplicate_response_groups": find_duplicate_responses(records),
        "similar_response_pairs": find_similar_responses(records),
        "category_counts": category_counts,
        # 「その他」率は分類の網羅率の指標として必ず公開する（KPIレベル2）
        "category_other_rate": round(category_counts[CATEGORY_OTHER] / n, 3) if n else None,
        "settings": {
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "teikeiku_phrases": TEIKEIKU_PHRASES,
            "response_categories": {
                cat: spec for cat, spec in RESPONSE_CATEGORIES.items()
            },
        },
    }
    return {"per_record": per_record, "corpus": corpus}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="抽出済みJSON（extract_opinions.py の出力）")
    parser.add_argument("-o", "--output", type=Path, required=True, help="指標JSONの出力先")
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    metrics = compute_metrics(data["records"])
    metrics["metadata"] = {
        "source_id": data["metadata"]["source_id"],
        "note": "構造的指標のみを算出。回答内容の質的評価は行わない（CLAUDE.md §3）。",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    dup = len(metrics["corpus"]["duplicate_response_groups"])
    sim = len(metrics["corpus"]["similar_response_pairs"])
    print(f"records: {len(metrics['per_record'])}, "
          f"teikeiku hits: {metrics['corpus']['teikeiku_hit_count']}, "
          f"duplicate groups: {dup}, similar pairs: {sim} -> {args.output}")


if __name__ == "__main__":
    main()
