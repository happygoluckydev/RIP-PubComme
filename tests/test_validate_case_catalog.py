"""validate_case_catalog.py のテスト。"""

from validate_case_catalog import validate_catalog


def _active_case():
    return {
        "case_id": "C-001",
        "status": "掲載中",
        "official_title": "架空の案件",
        "official_detail_url": "https://example.test/detail",
        "verified_at": "2026-07-20T09:00:00+09:00",
        "status_reason": "公式資料を確認済み",
        "deadline": "2026-08-20 23:59",
        "summary": "架空の要約です。",
        "explanation": {
            "what_changes": "架空の変更です。",
            "life_connection": "架空の関係です。",
            "how_to_submit": "公式ページから提出します。",
        },
        "documents": [{"label": "案文", "url": "https://example.test/document"}],
        "submission": {
            "official_submission_url": "https://example.test/submit",
            "status": "案内中",
            "notice": "公式ページで募集要領を確認して提出します。",
        },
    }


def test_案件台帳検証_空台帳は有効():
    assert validate_catalog({"cases": []}) == []


def test_案件台帳検証_掲載中案件の必須項目が揃えば有効():
    assert validate_catalog({"cases": [_active_case()]}) == []


def test_案件台帳検証_無効なステータスを検出():
    case = _active_case()
    case["status"] = "未判定"

    errors = validate_catalog({"cases": [case]})

    assert errors == ["cases[0] has invalid status: 未判定"]


def test_案件台帳検証_掲載中案件の資料不足を検出():
    case = _active_case()
    case["documents"] = []

    errors = validate_catalog({"cases": [case]})

    assert errors == ["cases[0] must include at least one official document"]


def test_案件台帳検証_提出案内の状態が無効なら検出():
    case = _active_case()
    case["submission"]["status"] = "受付終了"

    errors = validate_catalog({"cases": [case]})

    assert errors == ["cases[0] has invalid submission status: 受付終了"]


def test_案件台帳検証_掲載中案件が二件なら検出():
    errors = validate_catalog({"cases": [_active_case(), _active_case()]})

    assert errors == ["at most one case may have status 掲載中"]
