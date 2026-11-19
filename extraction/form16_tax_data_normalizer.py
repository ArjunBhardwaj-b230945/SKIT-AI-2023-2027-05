"""Normalize extracted Form 16 fields into a traceable intermediate tax-data record.

This is a rule-based normalization utility. It does not calculate tax or certify
that an extracted value is correct.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from typing import Any

FIELD_ALIASES = {
    "pan": ["pan", "employee_pan", "taxpayer_pan"],
    "assessment_year": ["assessment_year", "ay"],
    "financial_year": ["financial_year", "fy"],
    "gross_salary": ["gross_salary", "total_gross_salary", "salary_gross"],
    "salary_17_1": ["salary_17_1", "salary_under_17_1", "salary"],
    "perquisites_17_2": ["perquisites_17_2", "perquisites", "salary_perquisites"],
    "profit_in_lieu_17_3": ["profit_in_lieu_17_3", "profits_in_lieu", "profit_in_lieu_of_salary"],
    "section_10_exemptions": ["section_10_exemptions", "exemptions_under_section_10", "section10exemptions"],
    "salary_tds": ["salary_tds", "tds_on_salary", "total_tds"],
}

def _find(source: dict, aliases: list[str]):
    for key in aliases:
        if key in source and source[key] not in (None, ""):
            return source[key], key
    return None, None

def _number(value: Any):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("₹", "").strip()
        if re.fullmatch(r"-?\d+(?:\.\d{1,2})?", cleaned):
            return float(cleaned)
    return None

def _valid_pan(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", value.strip().upper()))

def _valid_year(value: Any, prefix: str) -> bool:
    if not isinstance(value, str):
        return False
    return bool(re.fullmatch(prefix + r"\s*20\d{2}\s*[-/]\s*20\d{2}", value.strip(), re.I))

def normalize_form16(data: dict, source_file: str = "", source_page: Any = None) -> dict:
    """Return normalized fields with original key, evidence and review status."""
    normalized = {}
    warnings = []
    for field, aliases in FIELD_ALIASES.items():
        value, original_key = _find(data, aliases)
        evidence = data.get("source_evidence", {})
        field_evidence = evidence.get(field) if isinstance(evidence, dict) else None
        if field_evidence is None:
            field_evidence = data.get("raw_text") or data.get("source_text")
        status = "extracted" if value is not None else "missing"
        normalized_value = value

        if field in {"gross_salary", "salary_17_1", "perquisites_17_2",
                     "profit_in_lieu_17_3", "salary_tds"} and value is not None:
            parsed = _number(value)
            if parsed is None:
                status = "review_required"
                warnings.append(f"{field}: value is not a recognizable numeric amount")
            else:
                normalized_value = parsed

        if field == "pan" and value is not None and not _valid_pan(str(value)):
            status = "review_required"
            warnings.append("pan: format check failed")

        if field == "assessment_year" and value is not None and not _valid_year(str(value), "AY"):
            status = "review_required"
            warnings.append("assessment_year: expected format such as AY 2026-27")

        if field == "financial_year" and value is not None and not _valid_year(str(value), "FY"):
            status = "review_required"
            warnings.append("financial_year: expected format such as FY 2025-26")

        if value is None:
            warnings.append(f"{field}: not found; left as null rather than assuming zero")

        normalized[field] = {
            "value": normalized_value,
            "status": status,
            "source_key": original_key,
            "source_file": source_file or data.get("source_file"),
            "source_page": source_page if source_page is not None else data.get("source_page"),
            "evidence": field_evidence,
        }

    # Preserve section 10 exemption detail as supplied; do not infer components.
    result = {
        "document_type": "Form 16",
        "schema_version": "1.0",
        "fields": normalized,
        "warnings": warnings,
        "overall_status": "review_required" if warnings else "ready_for_review",
        "tax_correctness_verified": False,
    }
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", help="JSON object containing extracted Form 16 fields")
    parser.add_argument("-o", "--output", default="form16_normalized_tax_data.json")
    parser.add_argument("--source-file", default="")
    parser.add_argument("--source-page", default=None)
    args = parser.parse_args()
    data = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input JSON must contain one object of extracted Form 16 fields.")
    result = normalize_form16(data, args.source_file, args.source_page)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Created {args.output}; status={result['overall_status']}; warnings={len(result['warnings'])}")

if __name__ == "__main__":
    main()
