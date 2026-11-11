"""Export a Form 26AS review queue to a compact JSON summary and CSV."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

FIELDS = [
    "review_id", "tan", "deductor_tan", "date", "transaction_date",
    "section", "section_code", "candidate_amount", "amount",
    "duplicate_candidate", "review_status", "review_decision",
    "source_file", "source_line", "raw_text",
]

def create_summary(data: dict) -> dict:
    rows = data.get("candidates", [])
    status_counts = {}
    error_counts = {}
    for row in rows:
        status = row.get("review_status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        for error in row.get("validation_errors", []):
            error_counts[error] = error_counts.get(error, 0) + 1
    return {
        "report_type": "Form 26AS review summary",
        "total_candidates": len(rows),
        "status_counts": status_counts,
        "validation_error_counts": error_counts,
        "manual_review_required": sum(
            row.get("review_status") in {
                "pending_manual_review", "validation_failed", "duplicate_candidate",
                "reviewer_needs_clarification"
            } for row in rows
        ),
        "tax_correctness_verified": False,
    }

def export_csv(data: dict, path: str | Path) -> None:
    rows = data.get("candidates", [])
    with Path(path).open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["raw_text"] = str(flat.get("raw_text", flat.get("text", ""))).replace("\n", " ")
            writer.writerow(flat)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review_queue_json")
    parser.add_argument("--csv", default="form26as_review_report.csv")
    parser.add_argument("--summary", default="form26as_review_summary.json")
    args = parser.parse_args()
    data = json.loads(Path(args.review_queue_json).read_text(encoding="utf-8"))
    summary = create_summary(data)
    export_csv(data, args.csv)
    Path(args.summary).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Created {args.csv} and {args.summary}")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
