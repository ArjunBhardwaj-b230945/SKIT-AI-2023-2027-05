"""Format-level checks for extracted Form 26AS candidate rows; not tax verification."""
import json, re
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation

TAN = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")
SECTION = re.compile(r"^(192|193|194[A-Z]?|195|206C(?:\([A-Z]\))?)$", re.I)

def valid_date(value):
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            datetime.strptime(str(value), fmt)
            return True
        except (ValueError, TypeError):
            pass
    return False

def valid_amount(value):
    try:
        n = Decimal(str(value).replace(",", "").replace("₹", "").strip())
        return n.is_finite() and n >= 0
    except (InvalidOperation, ValueError, TypeError):
        return False

def validate_candidate(row):
    checks = {
        "tan_format_valid": bool(row.get("tan") and TAN.fullmatch(str(row["tan"]).strip().upper())),
        "date_format_valid": valid_date(row.get("date")),
        "section_format_valid": bool(row.get("section") and SECTION.fullmatch(str(row["section"]).strip())),
        "candidate_amount_valid": valid_amount(row.get("candidate_amount")),
        "source_evidence_present": bool(row.get("raw_text") and row.get("source_file") and row.get("source_line")),
    }
    failed = [k for k, v in checks.items() if not v]
    return {"source_file": row.get("source_file"), "source_line": row.get("source_line"),
            "checks": checks, "passed_check_count": sum(checks.values()),
            "failed_checks": failed,
            "status": "review_required" if failed else "format_checks_passed_review_required"}

def validate_payload(payload):
    results = [validate_candidate(r) for r in payload.get("transactions", [])]
    passed = sum(not r["failed_checks"] for r in results)
    return {"source_file": payload.get("source_file"), "candidate_count": len(results),
            "all_format_checks_passed": passed, "candidates_with_format_issues": len(results)-passed,
            "results": results, "status": "review_required",
            "notice": "Passing format checks does not confirm tax-credit correctness. Verify against the original Form 26AS."}

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("candidate_json"); p.add_argument("--output", default="form26as_candidate_validation.json")
    a=p.parse_args()
    data=json.loads(Path(a.candidate_json).read_text(encoding="utf-8"))
    report=validate_payload(data)
    out=Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Candidates: {report['candidate_count']} | Format issues: {report['candidates_with_format_issues']} | Output: {out}")
if __name__ == "__main__": main()
