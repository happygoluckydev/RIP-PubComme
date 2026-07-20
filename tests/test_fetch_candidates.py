"""fetch_candidates.py のテスト。外部RSSへの通信は行わない。"""

from fetch_candidates import parse_rss


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns="http://purl.org/rss/1.0/"
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <item rdf:about="https://example.test/detail/1">
    <title>架空の案件</title>
    <link>https://example.test/detail/1</link>
    <description>案の公示日：2026/07/20&lt;br/&gt;受付締切日時：2026/08/20 23:59&lt;br/&gt;カテゴリー：陸運&lt;br/&gt;問合せ先（所管省庁・部局名等）：架空省</description>
    <dc:date>2026-07-20T00:00:00Z</dc:date>
  </item>
</rdf:RDF>"""


def test_rss解析_必要な項目を抽出する():
    result = parse_rss(RSS, "2026-07-20T09:00:00+09:00")

    assert result["metadata"]["fetched_at"] == "2026-07-20T09:00:00+09:00"
    assert result["items"] == [{
        "source_url": "https://example.test/detail/1",
        "title": "架空の案件",
        "detail_url": "https://example.test/detail/1",
        "published_at": "2026-07-20T00:00:00Z",
        "announced_on": "2026/07/20",
        "deadline": "2026/08/20 23:59",
        "category": "陸運",
        "contact": "架空省",
    }]


def test_rss解析_説明項目が欠けても空の案件を返す():
    rss = RSS.replace("受付締切日時：2026/08/20 23:59&lt;br/&gt;", "")

    result = parse_rss(rss, "2026-07-20T09:00:00+09:00")

    assert result["items"][0]["deadline"] is None


def test_rss解析_案件がない場合は空リストを返す():
    rss = """<?xml version="1.0"?><rdf:RDF xmlns="http://purl.org/rss/1.0/"/>"""

    result = parse_rss(rss, "2026-07-20T09:00:00+09:00")

    assert result["items"] == []
