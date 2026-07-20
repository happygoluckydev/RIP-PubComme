"""e-Gov RSSスナップショットを保存し、前回との差分を作成する。

差分はRSS上の掲載有無・項目値の変化という事実だけを示す。RSSから消えた案件を
「募集終了」とは判定しない。案件の評価や掲載可否の判定は行わない。
"""

import argparse
import json
import re
from pathlib import Path


COMPARISON_FIELDS = ("title", "announced_on", "deadline", "category", "contact", "published_at")


def _item_map(items):
    return {item["detail_url"]: item for item in items if item.get("detail_url")}


def build_diff(previous, current):
    """2つのRSSスナップショットを比較し、掲載上の変化だけを返す。"""
    previous_items = _item_map(previous["items"]) if previous else {}
    current_items = _item_map(current["items"])
    new_urls = current_items.keys() - previous_items.keys()
    missing_urls = previous_items.keys() - current_items.keys()
    changed_items = []

    for url in current_items.keys() & previous_items.keys():
        before = previous_items[url]
        after = current_items[url]
        changed_fields = [field for field in COMPARISON_FIELDS if before.get(field) != after.get(field)]
        if changed_fields:
            changed_items.append({
                "detail_url": url,
                "changed_fields": changed_fields,
                "previous": before,
                "current": after,
            })

    return {
        "metadata": {
            "current_fetched_at": current["metadata"]["fetched_at"],
            "previous_fetched_at": previous["metadata"]["fetched_at"] if previous else None,
            "note": "RSS掲載上の差分。no_longer_listed は募集終了を意味しない。",
        },
        "new_items": [current_items[url] for url in sorted(new_urls)],
        "no_longer_listed": [previous_items[url] for url in sorted(missing_urls)],
        "changed_items": sorted(changed_items, key=lambda item: item["detail_url"]),
    }


def history_filename(snapshot):
    fetched_at = snapshot["metadata"]["fetched_at"]
    safe_timestamp = re.sub(r"[^0-9A-Za-z]+", "", fetched_at)
    return f"egov_rss_{safe_timestamp}.json"


def load_latest_snapshot(history_dir):
    snapshots = []
    for path in history_dir.glob("*.json"):
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        snapshots.append((snapshot["metadata"]["fetched_at"], snapshot))
    return max(snapshots, default=(None, None), key=lambda item: item[0])[1]


def save_history(snapshot, history_dir, diff_output):
    """スナップショットを追記保存し、直前スナップショットとの差分を保存する。"""
    history_dir.mkdir(parents=True, exist_ok=True)
    previous = load_latest_snapshot(history_dir)
    target = history_dir / history_filename(snapshot)
    if target.exists():
        raise FileExistsError(f"history snapshot already exists: {target}")

    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    diff = build_diff(previous, snapshot)
    diff_output.parent.mkdir(parents=True, exist_ok=True)
    diff_output.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, diff


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("snapshot", type=Path, help="fetch_candidates.py が出力したRSSスナップショット")
    parser.add_argument("--history-dir", type=Path, default=Path("data/processed/rss_history"))
    parser.add_argument("--diff-output", type=Path, default=Path("data/processed/rss_diff.json"))
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    target, diff = save_history(snapshot, args.history_dir, args.diff_output)
    print(
        f"history: {target}, new: {len(diff['new_items'])}, "
        f"no longer listed: {len(diff['no_longer_listed'])}, changed: {len(diff['changed_items'])}"
    )


if __name__ == "__main__":
    main()
