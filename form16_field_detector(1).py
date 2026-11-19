"""
TaxSathi - Form 16 Field Detection
Week: 25-09-2026 to 01-10-2026

Extracts important Form 16 fields from already parsed text.
No tax calculation is performed here.
"""

import re
from typing import Any


def _first(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _amount(patterns: list[str], text: str) -> float | None:
    value = _first(patterns, text)
    if value is None:
        return None
    try:
        return float(value.replace(",", "").replace("₹", "").strip())
    except ValueError:
        return None


def detect_form16_fields(text: str) -> dict[str, Any]:
    """Detect commonly required Form 16 fields."""
    return {
        "employee_pan": _first([
            r"\bPAN\s*(?:of\s*(?:employee|deductee))?\s*[:\-]?\s*([A-Z]{5}[0-9]{4}[A-Z])"
        ], text),
        "employer_tan": _first([
            r"\bTAN\s*(?:of\s*(?:deductor|employer))?\s*[:\-]?\s*([A-Z]{4}[0-9]{5}[A-Z])"
        ], text),
        "assessment_year": _first([
            r"Assessment\s*Year\s*[:\-]?\s*((?:20)?\d{2}\s*[-/]\s*(?:20)?\d{2})"
        ], text),
        "salary_17_1": _amount([
            r"salary\s+as\s+per\s+section\s+17\s*\(\s*1\s*\)\s*[:\-]?\s*₹?\s*([\d,]+(?:\.\d+)?)",
            r"17\s*\(\s*1\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)"
        ], text),
        "perquisites_17_2": _amount([
            r"perquisites.*?17\s*\(\s*2\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)"
        ], text),
        "profit_in_lieu_17_3": _amount([
            r"profits?\s+in\s+lieu.*?17\s*\(\s*3\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)"
        ], text),
        "travel_concession_10_5": _amount([
            r"travel\s+concession.*?10\s*\(\s*5\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)"
        ], text),
        "hra_10_13a": _amount([
            r"house\s+rent\s+allowance.*?10\s*\(\s*13A\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)",
            r"HRA.*?10\s*\(\s*13A\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)"
        ], text),
        "standard_deduction_16_ia": _amount([
            r"standard\s+deduction.*?16\s*\(\s*ia\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)"
        ], text),
        "tax_deducted": _amount([
            r"tax\s+deducted.*?₹?\s*([\d,]+(?:\.\d+)?)",
            r"TDS.*?₹?\s*([\d,]+(?:\.\d+)?)"
        ], text),
    }


if __name__ == "__main__":
    sample = """
    PAN of employee: ABCDE1234F
    TAN of employer: DELA12345B
    Assessment Year: 2026-27
    Salary as per section 17(1): 750000
    Perquisites under section 17(2): 20000
    """
    print(detect_form16_fields(sample))
