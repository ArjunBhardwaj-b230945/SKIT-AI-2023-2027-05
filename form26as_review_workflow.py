"""Create a traceable, manual-review queue from Form 26AS candidate JSON.

This module performs structural checks only. It does not verify tax credits,
determine the correct table column, or make tax/legal decisions.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

TAN_RE = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")
DATE_FORMATS = ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y")
AMOUNT_RE = re.compile(r"^\d+(?:,\d{3})*(?:\.\d{1,2})?$")

def load_records(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = None
        for key in ("candidates", "transactions", "rows", "records", "items"):
            if isinstance(data.get(key), list):
                records = data[key]
                break
        if records is None:
            raise ValueError("JSON object must contain a candidate list (e.g. 'candidates' or 'rows').")
    else:
        raise ValueError("Input JSON must be a list or an object containing a list.")
    return [r for r in records if isinstance(r, dict)]

def _first(record: dict, *keys: str):
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None

def _amount(value: Any) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value >= 0
    if isinstance(value, str):
        return bool(AMOUNT_RE.fullmatch(value.strip().replace("₹", "").strip()))
    return False

def _fingerprint(record: dict) -> str:
    tan = str(_first(record, "tan", "deductor_tan") or "").strip().upper()
    date = str(_first(record, "date", "transaction_date", "payment_date") or "").strip()
    section = str(_first(record, "section", "section_code") or "").strip().upper()
    amount = str(_first(record, "candidate_amount", "amount", "tds_amount") or "").replace(",", "").strip()
    raw = str(_first(record, "raw_text", "text", "source_text") or "").strip().lower()
    payload = "|".join((tan, date, section, amount, raw))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _check_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    from datetime import datetime
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(value.strip(), fmt)
            return True
        except ValueError:
            pass
    return False

def build_review_queue(records: list[dict]) -> dict:
    seen = set()
    queue = []
    for index, source in enumerate(records, start=1):
        row = dict(source)
        tan = _first(row, "tan", "deductor_tan")
        date = _first(row, "date", "transaction_date", "payment_date")
        section = _first(row, "section", "section_code")
        amount = _first(row, "candidate_amount", "amount", "tds_amount")
        raw_text = _first(row, "raw_text", "text", "source_text")
        checks = {
            "tan_format_valid": bool(tan and TAN_RE.fullmatch(str(tan).strip().upper())),
            "date_format_valid": _check_date(date),
            "section_present": bool(section),
            "amount_format_valid": _amount(amount),
            "source_evidence_present": bool(raw_text or _first(row, "source_line", "line_number", "source_page")),
        }
        fingerprint = _fingerprint(row)
        duplicate = fingerprint in seen
        seen.add(fingerprint)
        errors = [name for name, passed in checks.items() if not passed]
        if errors:
            status = "validation_failed"
        elif duplicate:
            status = "duplicate_candidate"
        else:
            status = "pending_manual_review"
        row.update({
            "review_id": f"F26AS-{index:04d}",
            "review_fingerprint": fingerprint,
            "structural_checks": checks,
            "validation_errors": errors,
            "duplicate_candidate": duplicate,
            "review_status": status,
            "review_decision": None,
        })
        queue.append(row)
    counts = {
        "total_candidates": len(queue),
        "pending_manual_review": sum(r["review_status"] == "pending_manual_review" for r in queue),
        "validation_failed": sum(r["review_status"] == "validation_failed" for r in queue),
        "duplicate_candidate": sum(r["review_status"] == "duplicate_candidate" for r in queue),
    }
    return {
        "report_type": "Form 26AS candidate manual-review queue",
        "notice": "Structural checks only; no tax-credit correctness is confirmed.",
        "summary": counts,
        "candidates": queue,
    }

def apply_manual_decisions(queue_data: dict, decisions: dict[str, str]) -> dict:
    """Record reviewer decisions: verified, rejected, or needs_clarification."""
    allowed = {"verified", "rejected", "needs_clarification"}
    result = json.loads(json.dumps(queue_data))
    known = {r["review_id"] for r in result.get("candidates", [])}
    unknown = set(decisions) - known
    if unknown:
        raise ValueError(f"Unknown review_id(s): {', '.join(sorted(unknown))}")
    for row in result.get("candidates", []):
        decision = decisions.get(row["review_id"])
        if decision is not None:
            if decision not in allowed:
                raise ValueError(f"Invalid decision for {row['review_id']}: {decision}")
            row["review_decision"] = decision
            row["review_status"] = f"reviewer_{decision}"
    result["notice"] = (
        "Reviewer decisions are recorded as supplied. 'verified' means manually reviewed "
        "by the user; this tool does not independently verify tax correctness."
    )
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", help="Candidate JSON from the previous extraction steps")
    parser.add_argument("-o", "--output", default="form26as_review_queue.json")
    args = parser.parse_args()
    queue = build_review_queue(load_records(args.input_json))
    Path(args.output).write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Created {args.output} with {queue['summary']['total_candidates']} candidates")
    print(json.dumps(queue["summary"], indent=2))

if __name__ == "__main__":
    main()
