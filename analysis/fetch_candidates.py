"""e-Gov RSSから意見募集案件の候補検知用スナップショットを作成する。

このモジュールが扱うのは、RSSに記載された案件名・URL・公示日・締切・カテゴリ・所管だけである。
案件の重要性、意見内容、行政の対応の評価は行わない。RSSは候補検知の入口であり、掲載可否は
案件詳細、意見募集要領、案文を確認して別途判断する（docs/CASE_SELECTION_POLICY.md）。
"""

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree


RSS_URL = "https://public-comment.e-gov.go.jp/rss/pcm_list.xml"
RDF_NAMESPACE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
DC_NAMESPACE = "http://purl.org/dc/elements/1.1/"


def _text(element, name):
    value = element.findtext(f"{{http://purl.org/rss/1.0/}}{name}")
    return value.strip() if value else None


def _dc_text(element, name):
    value = element.findtext(f"{{{DC_NAMESPACE}}}{name}")
    return value.strip() if value else None


def _description_fields(description):
    plain = re.sub(r"<br\s*/?>", "\n", html.unescape(description or ""), flags=re.IGNORECASE)
    plain = re.sub(r"<[^>]+>", "", plain)
    fields = {}
    for line in plain.splitlines():
        if "：" not in line:
            continue
        key, value = line.split("：", 1)
        fields[key.strip()] = value.strip()
    return fields


def parse_rss(content, fetched_at):
    """RSS XMLを、候補検知に必要な事実だけを持つ辞書へ変換する。"""
    root = ElementTree.fromstring(content)
    items = []
    for item in root.findall("{http://purl.org/rss/1.0/}item"):
        fields = _description_fields(_text(item, "description"))
        items.append({
            "source_url": item.attrib.get(f"{{{RDF_NAMESPACE}}}about"),
            "title": _text(item, "title"),
            "detail_url": _text(item, "link"),
            "published_at": _dc_text(item, "date"),
            "announced_on": fields.get("案の公示日"),
            "deadline": fields.get("受付締切日時"),
            "category": fields.get("カテゴリー"),
            "contact": fields.get("問合せ先（所管省庁・部局名等）"),
        })
    return {
        "metadata": {
            "source_url": RSS_URL,
            "fetched_at": fetched_at,
            "note": "RSS掲載項目の候補検知用スナップショット。掲載可否の判定や内容評価は含まない。",
        },
        "items": items,
    }


def fetch_rss(url):
    """e-Gov RSSを取得する。ネットワーク失敗時は例外を呼び出し元へ伝播する。"""
    request = Request(url, headers={"User-Agent": "RIP-PubComme candidate monitor/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", type=Path, required=True, help="スナップショットJSONの出力先")
    parser.add_argument("--rss-url", default=RSS_URL, help="取得するRSS URL（テスト時に差し替え可能）")
    args = parser.parse_args()

    content = fetch_rss(args.rss_url)
    fetched_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    snapshot = parse_rss(content, fetched_at)
    snapshot["metadata"]["source_url"] = args.rss_url
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"items: {len(snapshot['items'])} -> {args.output}")


if __name__ == "__main__":
    main()
