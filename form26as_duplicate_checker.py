"""Flag exact duplicate-like Form 26AS candidate rows; never deletes source rows."""
import hashlib, json
from collections import defaultdict
from pathlib import Path

def fingerprint(row):
    parts = [str(row.get(k) or "").strip().lower() for k in
             ("tan", "date", "section", "candidate_amount", "raw_text")]
    parts[0] = parts[0].upper()
    return hashlib.sha256("|".join(" ".join(x.split()) for x in parts).encode()).hexdigest()

def find_duplicates(payload):
    groups=defaultdict(list)
    for i,row in enumerate(payload.get("transactions", [])):
        groups[fingerprint(row)].append({"index":i, "source_file":row.get("source_file"),
                                         "source_line":row.get("source_line"), "raw_text":row.get("raw_text")})
    duplicates=[{"fingerprint":key, "occurrence_count":len(rows), "occurrences":rows,
                 "status":"manual_review_required"} for key,rows in groups.items() if len(rows)>1]
    return {"source_file":payload.get("source_file"), "input_row_count":len(payload.get("transactions", [])),
            "possible_duplicate_group_count":len(duplicates),
            "possible_duplicate_row_count":sum(g["occurrence_count"] for g in duplicates),
            "duplicate_groups":duplicates, "status":"review_required",
            "notice":"Rows are flagged, not removed. Repeated entries may be legitimate; verify against the source."}

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("candidate_json"); p.add_argument("--output", default="form26as_duplicate_report.json")
    a=p.parse_args()
    data=json.loads(Path(a.candidate_json).read_text(encoding="utf-8"))
    report=find_duplicates(data)
    out=Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Possible duplicate groups: {report['possible_duplicate_group_count']} | Output: {out}")
if __name__ == "__main__": main()
