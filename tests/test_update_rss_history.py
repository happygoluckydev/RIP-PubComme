"""update_rss_history.py のテスト。"""

from update_rss_history import build_diff, history_filename


def _snapshot(fetched_at, items):
    return {"metadata": {"fetched_at": fetched_at}, "items": items}


def _item(url, deadline="2026/08/01 23:59"):
    return {
        "detail_url": url,
        "title": "架空の案件",
        "announced_on": "2026/07/20",
        "deadline": deadline,
        "category": "陸運",
        "contact": "架空省",
        "published_at": "2026-07-20T00:00:00Z",
    }


def test_rss差分_初回は全件を新着として返す():
    current = _snapshot("2026-07-20T09:00:00+09:00", [_item("https://example.test/1")])

    diff = build_diff(None, current)

    assert len(diff["new_items"]) == 1
    assert diff["no_longer_listed"] == []


def test_rss差分_新規とRSS上の非掲載化を区別する():
    previous = _snapshot("2026-07-20T09:00:00+09:00", [_item("https://example.test/1")])
    current = _snapshot("2026-07-21T09:00:00+09:00", [_item("https://example.test/2")])

    diff = build_diff(previous, current)

    assert diff["new_items"][0]["detail_url"] == "https://example.test/2"
    assert diff["no_longer_listed"][0]["detail_url"] == "https://example.test/1"


def test_rss差分_締切変更を検出する():
    previous = _snapshot("2026-07-20T09:00:00+09:00", [_item("https://example.test/1")])
    current = _snapshot("2026-07-21T09:00:00+09:00", [_item("https://example.test/1", "2026/08/02 23:59")])

    diff = build_diff(previous, current)

    assert diff["changed_items"][0]["changed_fields"] == ["deadline"]


def test_履歴ファイル名_取得日時を安全なファイル名にする():
    snapshot = _snapshot("2026-07-20T09:00:00+09:00", [])

    assert history_filename(snapshot) == "egov_rss_20260720T0900000900.json"
