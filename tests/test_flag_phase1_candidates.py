"""flag_phase1_candidates.py のテスト。"""

from flag_phase1_candidates import find_phase1_signals


def test_phase1候補目印_タイトルのキーワード一致を返す():
    items = [{"title": "道路運送法施行規則の改正案", "category": "陸運", "contact": "国土交通省"}]

    result = find_phase1_signals(items)

    assert result[0]["matched_keywords"] == ["道路運送"]
    assert result[0]["matched_fields"] == ["title"]


def test_phase1候補目印_所管のキーワード一致を返す():
    items = [{"title": "架空の案件", "category": "その他", "contact": "物流・自動車局"}]

    result = find_phase1_signals(items)

    assert result[0]["matched_keywords"] == ["物流"]
    assert result[0]["matched_fields"] == ["contact"]


def test_phase1候補目印_不一致は空リストを返す():
    items = [{"title": "架空の案件", "category": "その他", "contact": "架空省"}]

    assert find_phase1_signals(items) == []
