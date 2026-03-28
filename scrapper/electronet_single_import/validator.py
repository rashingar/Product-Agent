from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from .normalize import normalize_whitespace
from .repo_paths import PRODUCT_TEMPLATE_PATH
from .utils import load_template_headers, write_json

REPLACEMENT_CHAR = "\ufffd"
MOJIBAKE_RE = re.compile(r"(?:Ã.|Â.|Î.|Ï.|â€.|â€œ|â€™|â€\x9d)")
C1_CONTROL_RE = re.compile(r"[\u0080-\u009f]")
QUESTION_RUN_RE = re.compile(r"\?{3,}")
REQUIRED_NON_EMPTY_FIELDS = {
    "model",
    "mpn",
    "name",
    "description",
    "characteristics",
    "category",
    "image",
    "manufacturer",
    "price",
    "meta_keyword",
    "meta_title",
    "meta_description",
    "seo_keyword",
    "product_url",
}


def validate_candidate_csv(
    csv_path: str | Path,
    baseline_path: str | Path | None = None,
    template_path: str | Path = PRODUCT_TEMPLATE_PATH,
    llm_errors: list[str] | None = None,
) -> dict[str, Any]:
    csv_path = Path(csv_path)
    report: dict[str, Any] = {
        "ok": True,
        "csv_path": str(csv_path),
        "template_path": str(template_path),
        "baseline_path": str(baseline_path) if baseline_path else "",
        "errors": list(llm_errors or []),
        "warnings": [],
        "field_health": {},
    }

    expected_headers = load_template_headers(template_path)
    report["expected_headers"] = expected_headers
    try:
        headers, row = read_single_row_csv(csv_path)
    except UnicodeDecodeError as exc:
        report["ok"] = False
        report["errors"].append(f"csv_decode_failed:{exc}")
        return report

    report["actual_headers"] = headers
    if headers != expected_headers:
        report["ok"] = False
        report["errors"].append("csv_header_order_mismatch")

    baseline_row: dict[str, str] = {}
    if baseline_path:
        baseline_headers, baseline_row = read_single_row_csv(baseline_path)
        report["baseline_headers"] = baseline_headers
        if baseline_headers != expected_headers:
            report["warnings"].append("baseline_header_order_differs_from_template")

    for header in expected_headers:
        candidate_value = row.get(header, "")
        encoding_issues = detect_text_issues(candidate_value)
        baseline_value = baseline_row.get(header, "")
        status = "empty"
        if candidate_value:
            status = "different_but_valid" if baseline_row else "filled"
        if baseline_row and candidate_value == baseline_value:
            status = "match"
        if encoding_issues:
            status = "encoding_issue"
            report["ok"] = False
        if header in REQUIRED_NON_EMPTY_FIELDS and not normalize_whitespace(candidate_value):
            status = "missing"
            report["ok"] = False
            report["errors"].append(f"required_field_missing:{header}")
        report["field_health"][header] = {
            "status": status,
            "candidate_length": len(candidate_value),
            "baseline_length": len(baseline_value),
            "encoding_issues": encoding_issues,
            "candidate_preview": normalize_whitespace(candidate_value)[:120],
            "baseline_preview": normalize_whitespace(baseline_value)[:120],
        }

    report["summary"] = summarize_health(report["field_health"])
    if report["errors"]:
        report["ok"] = False
    return report


def write_validation_report(report: dict[str, Any], out_path: str | Path) -> None:
    write_json(out_path, report)


def read_single_row_csv(path: str | Path) -> tuple[list[str], dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        row = next(reader, {})
        return headers, {key: value or "" for key, value in row.items()}


def detect_text_issues(text: str) -> list[str]:
    issues: list[str] = []
    if not text:
        return issues
    if REPLACEMENT_CHAR in text:
        issues.append("replacement_character")
    if C1_CONTROL_RE.search(text):
        issues.append("c1_control_character")
    if MOJIBAKE_RE.search(text):
        issues.append("mojibake_pattern")
    if QUESTION_RUN_RE.search(text) and "http" not in text:
        issues.append("question_mark_run")
    return issues


def summarize_health(field_health: dict[str, dict[str, Any]]) -> dict[str, int]:
    summary = {
        "match": 0,
        "different_but_valid": 0,
        "filled": 0,
        "missing": 0,
        "encoding_issue": 0,
        "empty": 0,
    }
    for health in field_health.values():
        status = str(health.get("status", "empty"))
        if status not in summary:
            summary[status] = 0
        summary[status] += 1
    return summary
