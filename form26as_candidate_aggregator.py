"""Review-only aggregation of previously extracted Form 26AS candidate rows."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json

def num(value):
    try:
        return Decimal(str(value).replace(",", "").replace("₹", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return None

def aggregate_candidates(payload):
    rows = payload.get("transactions", [])
    sections, tans = defaultdict(list), defaultdict(list)
    warnings, amounts = [], []
    for row in rows:
        sections[row.get("section") or "section_not_detected"].append(row)
        tans[row.get("tan") or "tan_not_detected"].append(row)
        amount = num(row.get("candidate_amount"))
        if amount is None:
            warnings.append({"source_line": row.get("source_line"), "warning": "Missing/invalid amount; excluded from subtotal."})
        else:
            amounts.append(amount)
    def group_report(groups):
        out = {}
        for key, group in sorted(groups.items()):
            vals = [num(r.get("candidate_amount")) for r in group]
            vals = [v for v in vals if v is not None]
            out[key] = {"row_count": len(group), "rows_with_numeric_amount": len(vals),
                        "candidate_subtotal": str(sum(vals, Decimal("0")).quantize(Decimal("0.01"))),
                        "status": "review_required"}
        return out
    return {"source_file": payload.get("source_file"), "candidate_count": len(rows),
            "rows_with_numeric_amount": len(amounts),
            "candidate_subtotal": str(sum(amounts, Decimal("0")).quantize(Decimal("0.01"))),
            "by_section": group_report(sections), "by_tan": group_report(tans),
            "warnings": warnings, "status": "review_required",
            "notice": "Candidate amounts may be from a non-tax column. Verify every row against the original Form 26AS."}

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("input_json"); p.add_argument("--output", default="form26as_candidate_aggregation.json")
    a=p.parse_args()
    data=json.loads(Path(a.input_json).read_text(encoding="utf-8"))
    result=aggregate_candidates(data)
    out=Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Candidates: {result['candidate_count']} | Status: review_required | Output: {out}")
if __name__ == "__main__": main()
