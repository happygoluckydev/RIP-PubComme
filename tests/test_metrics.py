"""metrics.py のテスト（正常系・異常系・境界値）。

テストデータはすべて架空の最小例。実データ（data/processed/）には依存しない。
"""

from metrics import (
    CATEGORY_OTHER,
    classify_response,
    compute_metrics,
    detect_concrete_references,
    detect_teikeiku,
    find_duplicate_responses,
    find_similar_responses,
    response_char_count,
)


def _record(key, response, merged=False):
    return {"key": key, "response": response, "response_cell_merged_with_previous": merged}


# --- response_char_count ---

def test_response_char_count_通常の文():
    assert response_char_count("あいうえお") == 5


def test_response_char_count_空文字列():
    assert response_char_count("") == 0


def test_response_char_count_空白は数えない():
    assert response_char_count("あい うえお\n") == 5


# --- detect_teikeiku ---

def test_定型句検出_該当ありは文言を返す():
    text = "ご意見も踏まえて適切に対処して参ります。"
    assert "適切に対処して参ります" in detect_teikeiku(text)


def test_定型句検出_該当なしは空リスト():
    assert detect_teikeiku("具体的な回答内容です。") == []


def test_定型句検出_複数該当は全件返す():
    text = "素案のとおりとし、適切に対処してまいります。"
    found = detect_teikeiku(text)
    assert "素案のとおり" in found
    assert "適切に対処してまいります" in found


def test_定型句検出_空文字列は空リスト():
    assert detect_teikeiku("") == []


# --- detect_concrete_references ---

def test_具体的参照_ページ参照を検出():
    refs = detect_concrete_references("【14ページ】に記述を追加しました。")
    assert refs["page_reference"] == ["【14ページ】"]


def test_具体的参照_条文参照を検出():
    refs = detect_concrete_references("道路運送法第78条に基づき実施します。")
    assert refs["article_reference"] == ["第78条"]


def test_具体的参照_年および数量を検出():
    refs = detect_concrete_references("令和６年４月に導入し、2030年度に1万台を目指します。")
    assert "令和６年" in refs["date_reference"]
    assert "2030年" in refs["date_reference"]
    assert any("万" in q for q in refs["quantity_reference"])


def test_具体的参照_参照なしは全種類空():
    refs = detect_concrete_references("適切に対処してまいります。")
    assert all(v == [] for v in refs.values())


# --- classify_response ---

def test_分類_記述追加を検出():
    assert classify_response("頂いたご意見を踏まえ、脚注に以下の記述を追加しました。") == ["shusei_tsuika"]


def test_分類_既記載を検出():
    text = "第３章に記述しているところであり、適切に対処して参ります。"
    assert classify_response(text) == ["kisai_zumi"]


def test_分類_素案のとおりを検出():
    assert classify_response("素案のとおりとして取組を進めてまいります。") == ["soan_no_toori"]


def test_分類_検討継続を検出():
    assert classify_response("引き続き検討を進めてまいります。") == ["kento_keizoku"]


def test_分類_既存取組を検出():
    assert classify_response("人材確保の取組に対する支援について、取り組んでおります。") == ["kizon_torikumi"]


def test_分類_複数パターンはマルチラベル():
    text = "第３章に記載しているところであり、素案のままとし、適切に対処して参ります。"
    found = classify_response(text)
    assert "kisai_zumi" in found
    assert "soan_no_toori" in found


def test_分類_該当なしはその他():
    assert classify_response("全国の移動の足の確保に向けた運用改善を重ねてきております。") == [CATEGORY_OTHER]


def test_分類_空文字列はその他():
    assert classify_response("") == [CATEGORY_OTHER]


# --- find_duplicate_responses ---

def test_使い回し検出_完全一致をグループ化():
    records = [
        _record("Ⅱ-1", "同一の回答文です。"),
        _record("Ⅱ-2", "同一の回答文です。"),
        _record("Ⅱ-3", "別の回答文です。"),
    ]
    groups = find_duplicate_responses(records)
    assert len(groups) == 1
    assert groups[0]["keys"] == ["Ⅱ-1", "Ⅱ-2"]


def test_使い回し検出_結合セルは除外():
    # 縦結合セル（同一回答の共有）は元資料のレイアウト上の事実であり、使い回しではない
    records = [
        _record("Ⅰ-2", "共有された回答です。"),
        _record("Ⅰ-3", "共有された回答です。", merged=True),
    ]
    assert find_duplicate_responses(records) == []


def test_使い回し検出_重複なしは空リスト():
    records = [_record("Ⅱ-1", "回答A"), _record("Ⅱ-2", "回答B")]
    assert find_duplicate_responses(records) == []


# --- find_similar_responses ---

def test_類似検出_高類似ペアを返す():
    base = "全国の移動の足の確保に向け、日本版ライドシェアの導入を行いました。"
    records = [
        _record("Ⅱ-4", base),
        _record("Ⅱ-5", base + "また、制度改善を進めます。"),
    ]
    pairs = find_similar_responses(records, threshold=0.7)
    assert len(pairs) == 1
    assert pairs[0]["keys"] == ["Ⅱ-4", "Ⅱ-5"]


def test_類似検出_完全一致ペアは対象外():
    records = [_record("Ⅱ-1", "同じ文です。"), _record("Ⅱ-2", "同じ文です。")]
    assert find_similar_responses(records, threshold=0.5) == []


def test_類似検出_低類似は返さない():
    records = [_record("Ⅱ-1", "回答Aの本文です。"), _record("Ⅱ-2", "全く異なる内容。")]
    assert find_similar_responses(records, threshold=0.9) == []


# --- compute_metrics ---

def test_全指標算出_レコードごとの指標とコーパス集計を返す():
    records = [
        _record("Ⅱ-1", "素案のとおりとし、適切に対処して参ります。"),
        _record("Ⅱ-2", "【63ページ】に記述を追加しました。"),
    ]
    m = compute_metrics(records)
    assert len(m["per_record"]) == 2
    assert m["corpus"]["record_count"] == 2
    assert m["corpus"]["teikeiku_hit_count"] == 1
    # 検出設定（定型句リスト・しきい値）が出力に含まれ、追跡可能であること
    assert m["corpus"]["settings"]["teikeiku_phrases"]


def test_全指標算出_空リストは空の結果():
    m = compute_metrics([])
    assert m["per_record"] == []
    assert m["corpus"]["record_count"] == 0
    assert m["corpus"]["duplicate_response_groups"] == []
