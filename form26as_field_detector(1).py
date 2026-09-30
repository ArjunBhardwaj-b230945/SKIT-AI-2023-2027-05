"""
TaxSathi - Form 26AS Field Detection
Week: 25-09-2026 to 01-10-2026

Detects basic Form 26AS identity information and TDS/challan rows
from parsed text. Values are extracted only; no reconciliation is done.
"""

import re
from typing import Any


def _first(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _number(value: str) -> float | None:
    try:
        return float(value.replace(",", "").replace("₹", "").strip())
    except (ValueError, AttributeError):
        return None


def detect_form26as_fields(text: str) -> dict[str, Any]:
    """Extract basic identity fields and recognizable TDS/challan rows."""
    result: dict[str, Any] = {
        "pan": _first([
            r"\bPAN\s*[:\-]?\s*([A-Z]{5}[0-9]{4}[A-Z])"
        ], text),
        "assessment_year": _first([
            r"Assessment\s*Year\s*[:\-]?\s*((?:20)?\d{2}\s*[-/]\s*(?:20)?\d{2})"
        ], text),
        "tds_rows": [],
        "advance_tax_rows": [],
    }

    # Generic line-level extraction. Exact table layouts can vary by source.
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        tan = re.search(r"\b([A-Z]{4}[0-9]{5}[A-Z])\b", line)
        amounts = re.findall(r"₹?\s*[\d,]+(?:\.\d+)?", line)

        if tan and len(amounts) >= 1:
            numeric = [_number(x) for x in amounts]
            numeric = [x for x in numeric if x is not None]
            if numeric:
                result["tds_rows"].append({
                    "deductor_tan": tan.group(1),
                    "amounts_found": numeric,
                    "source_line": line,
                })

        # Typical challan date pattern used as a signal for advance-tax rows.
        date = re.search(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b", line)
        if date and amounts:
            numeric = [_number(x) for x in amounts]
            numeric = [x for x in numeric if x is not None]
            if numeric:
                result["advance_tax_rows"].append({
                    "date": date.group(1),
                    "amounts_found": numeric,
                    "source_line": line,
                })

    return result


if __name__ == "__main__":
    sample = """
    PAN: ABCDE1234F
    Assessment Year: 2026-27
    ABCD12345E Employer Pvt Ltd 450000 45000
    15/07/2026 123456 20000
    """
    print(detect_form26as_fields(sample))
