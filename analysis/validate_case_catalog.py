"""案件台帳の必須項目を検証する。

このモジュールは、公開前の事実確認に必要な項目の有無だけを検証する。案件の重要性、
意見内容、行政の対応の評価や採点は行わない。
"""

import argparse
import json
from pathlib import Path


VALID_STATUSES = {"掲載中", "次回候補", "保留", "対象外", "取り下げ"}
BASE_FIELDS = {"case_id", "status", "official_title", "official_detail_url", "verified_at", "status_reason"}
ACTIVE_FIELDS = {"deadline", "summary", "explanation", "documents"}
EXPLANATION_FIELDS = {"what_changes", "life_connection", "how_to_submit"}
SUBMISSION_FIELDS = {"official_submission_url", "status", "notice"}
SUBMISSION_STATUSES = {"案内中", "公式確認が必要"}


def validate_catalog(catalog):
    """台帳の構造を検証し、不備を文字列のリストで返す。"""
    errors = []
    cases = catalog.get("cases")
    if not isinstance(cases, list):
        return ["cases must be a list"]

    active_count = 0
    for index, case in enumerate(cases):
        prefix = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = BASE_FIELDS - case.keys()
        if missing:
            errors.append(f"{prefix} missing base fields: {', '.join(sorted(missing))}")
            continue
        if case["status"] not in VALID_STATUSES:
            errors.append(f"{prefix} has invalid status: {case['status']}")
            continue
        if case["status"] != "掲載中":
            continue

        active_count += 1
        missing = ACTIVE_FIELDS - case.keys()
        if missing:
            errors.append(f"{prefix} missing active fields: {', '.join(sorted(missing))}")
            continue
        explanation = case["explanation"]
        if not isinstance(explanation, dict) or EXPLANATION_FIELDS - explanation.keys():
            errors.append(f"{prefix} has incomplete explanation")
        if not isinstance(case["documents"], list) or not case["documents"]:
            errors.append(f"{prefix} must include at least one official document")
        submission = case.get("submission")
        if not isinstance(submission, dict) or SUBMISSION_FIELDS - submission.keys():
            errors.append(f"{prefix} has incomplete submission guidance")
        elif submission["status"] not in SUBMISSION_STATUSES:
            errors.append(f"{prefix} has invalid submission status: {submission['status']}")

    if active_count > 1:
        errors.append("at most one case may have status 掲載中")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="案件台帳JSONのパス")
    args = parser.parse_args()

    catalog = json.loads(args.input.read_text(encoding="utf-8"))
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("\n".join(errors))
    print(f"case catalog: PASS ({len(catalog['cases'])} cases)")


if __name__ == "__main__":
    main()
