"""Detection-coverage report for Form 26AS candidate extraction."""
from pathlib import Path
import json

def build_quality_report(payload, reconciliation=None):
    rows=payload.get("transactions", [])
    fields={"TAN":"tan", "Date":"date", "Section":"section", "Candidate amount":"candidate_amount"}
    checks=[]
    for label, key in fields.items():
        missing=sum(1 for r in rows if r.get(key) in (None, ""))
        found=len(rows)-missing
        checks.append({"field":label, "detected":found, "missing":missing,
                       "coverage_percent":round(found*100/len(rows), 2) if rows else 0.0})
    warning_rows=sum(bool(r.get("warnings")) for r in rows)
    warnings=[]
    if not rows: warnings.append("No candidate rows found; check input/parser output.")
    if warning_rows: warnings.append(f"{warning_rows} row(s) have extraction warnings.")
    if reconciliation: warnings.append("Reconciliation is informational and requires manual verification.")
    return {"source_file":payload.get("source_file"), "candidate_count":len(rows),
            "rows_with_extraction_warnings":warning_rows, "checks":checks,
            "reconciliation_comparison":reconciliation.get("comparison") if reconciliation else None,
            "warnings":warnings, "status":"review_required",
            "notice":"Detection coverage does not prove tax correctness or credit eligibility."}

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("candidate_json"); p.add_argument("--reconciliation-json")
    p.add_argument("--output", default="tax_data_quality_report.json")
    a=p.parse_args()
    data=json.loads(Path(a.candidate_json).read_text(encoding="utf-8"))
    recon=json.loads(Path(a.reconciliation_json).read_text(encoding="utf-8")) if a.reconciliation_json else None
    result=build_quality_report(data, recon)
    out=Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Rows: {result['candidate_count']} | Status: review_required | Output: {out}")
if __name__ == "__main__": main()
