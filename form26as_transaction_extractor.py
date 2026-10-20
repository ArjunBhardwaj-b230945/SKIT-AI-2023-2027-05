"""Heuristic extraction of transaction-like rows from LlamaParse Form 26AS text.

This module extracts reviewable candidates only. It does not certify tax credits or
replace verification against the original Form 26AS PDF.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import re
from typing import Iterable, Optional


DATE_RE = re.compile(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
TAN_RE = re.compile(r"\b[A-Z]{4}\d{5}[A-Z]\b")
AMOUNT_RE = re.compile(r"(?<![A-Za-z])(?:₹\s*)?(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?![A-Za-z])")
SECTION_RE = re.compile(r"\b(?:section\s*)?(194[A-Z]?|192|193|194|195|206C(?:\([A-Z]\))?)\b", re.I)


@dataclass
class Form26ASTransaction:
    source_file: str
    source_line: int
    raw_text: str
    date: Optional[str]
    tan: Optional[str]
    section: Optional[str]
    amounts: list[str]
    candidate_amount: Optional[str]
    status: str = "review_required"
    warnings: list[str] | None = None

    def to_dict(self):
        return asdict(self)


def _decimal_text(value: str) -> Optional[str]:
    cleaned = value.replace(",", "").strip()
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return None
    if number < 0:
        return None
    return str(number.quantize(Decimal("0.01")))


def _amounts(line: str) -> list[str]:
    values = []
    for match in AMOUNT_RE.finditer(line):
        # Ignore years and date fragments accidentally matched by the amount regex.
        raw = match.group(1)
        normalized = _decimal_text(raw)
        if normalized is not None and normalized not in values:
            values.append(normalized)
    return values


def extract_transactions(text: str, source_file: str = "<memory>") -> list[Form26ASTransaction]:
    """Return row candidates from lines with transaction clues and numeric values.

    LlamaParse output can vary by document. A line is retained only when it has
    at least one amount and a date, TAN, section label, or common TDS/TCS keyword.
    """
    results: list[Form26ASTransaction] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = " ".join(raw_line.split()).strip(" |")
        if not line:
            continue
        amounts = _amounts(line)
        date_match = DATE_RE.search(line)
        tan_match = TAN_RE.search(line)
        section_match = SECTION_RE.search(line)
        has_keyword = bool(re.search(r"\b(TDS|TCS|tax deducted|tax collected|deductor|collector|credit)\b", line, re.I))
        if not amounts or not (date_match or tan_match or section_match or has_keyword):
            continue

        warnings = []
        if len(amounts) == 1:
            warnings.append("Only one numeric amount detected; confirm whether it is tax deducted/collected or another column.")
        if not tan_match:
            warnings.append("TAN not detected on this line.")
        if not date_match:
            warnings.append("Date not detected on this line.")
        if len(amounts) > 1:
            warnings.append("Multiple numeric amounts detected; candidate amount is the final amount and requires verification.")

        results.append(Form26ASTransaction(
            source_file=source_file,
            source_line=line_number,
            raw_text=line,
            date=date_match.group(1) if date_match else None,
            tan=tan_match.group(0) if tan_match else None,
            section=section_match.group(1).upper() if section_match else None,
            amounts=amounts,
            candidate_amount=amounts[-1] if amounts else None,
            warnings=warnings,
        ))
    return results


def extract_file(input_path: str | Path, output_path: str | Path) -> dict:
    input_path = Path(input_path)
    text = input_path.read_text(encoding="utf-8", errors="replace")
    rows = extract_transactions(text, source_file=input_path.name)
    payload = {
        "source_file": input_path.name,
        "transaction_candidate_count": len(rows),
        "status": "review_required",
        "transactions": [row.to_dict() for row in rows],
        "notice": "Heuristic candidates only. Verify each row and amount against the original Form 26AS.",
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract reviewable transaction candidates from parsed Form 26AS text.")
    parser.add_argument("input_txt", help="LlamaParse-generated Form 26AS .txt file")
    parser.add_argument("--output", default="form26as_transaction_candidates.json")
    args = parser.parse_args()
    payload = extract_file(args.input_txt, args.output)
    print(f"Candidates: {payload['transaction_candidate_count']} | Output: {args.output} | Status: review_required")


if __name__ == "__main__":
    main()
