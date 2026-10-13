"""Review field-label evidence from already-parsed text."""
import json
from pathlib import Path
from parsing_field_rules import FORM16_FIELDS, FORM26AS_FIELDS, normalize_text, review_fields
def review_document(text, document_type):
    t = document_type.strip().lower().replace(" ", "").replace("_", "")
    if t == "form16": rules, canonical = FORM16_FIELDS, "form16"
    elif t == "form26as": rules, canonical = FORM26AS_FIELDS, "form26as"
    else: raise ValueError("document_type must be form16 or form26as")
    normalized = normalize_text(text)
    return {"document_type": canonical, "character_count": len(normalized),
            "fields": review_fields(normalized, rules),
            "limitations": ["Heuristic label detection; wording/layout may differ.",
              "Evidence snippets are not verified values.", "No tax calculation, reconciliation, or ITR generation.",
              "Human review against source PDFs is required."]}
def review_file(input_path, document_type, output_path=None):
    p = Path(input_path)
    report = review_document(p.read_text(encoding="utf-8", errors="replace"), document_type)
    report["source_file"] = p.name
    if output_path: Path(output_path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("input"); p.add_argument("--type", required=True, choices=["form16","form26as"])
    p.add_argument("--output")
    a = p.parse_args()
    print(json.dumps(review_file(a.input,a.type,a.output), indent=2, ensure_ascii=False))
if __name__ == "__main__": main()
