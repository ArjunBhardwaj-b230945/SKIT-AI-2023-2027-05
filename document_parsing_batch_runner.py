"""Batch review .txt outputs from the existing LlamaParse integration; no API calls."""
import argparse, json
from pathlib import Path
from document_parsing_review import review_file
def run_batch(input_dir, output_path):
    root = Path(input_dir)
    if not root.is_dir(): raise NotADirectoryError(f"Input directory not found: {root}")
    reports = []
    for p in sorted(root.glob("*.txt")):
        name = p.name.lower().replace("_","").replace("-","")
        if "26as" in name: kind = "form26as"
        elif "form16" in name: kind = "form16"
        else: continue
        reports.append(review_file(p, kind))
    result = {"report_type":"taxsathi_document_parsing_batch_review",
              "files_reviewed":len(reports), "reports":reports,
              "note":"Heuristic review only; not verified tax data."}
    Path(output_path).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
def main():
    p=argparse.ArgumentParser(); p.add_argument("input_dir")
    p.add_argument("--output", default="document_parsing_batch_report.json")
    a=p.parse_args(); r=run_batch(a.input_dir,a.output)
    print(f"Reviewed {r['files_reviewed']} matching file(s). Wrote {a.output}")
if __name__=="__main__": main()
