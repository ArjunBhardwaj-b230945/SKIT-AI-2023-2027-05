"""Check completeness and basic consistency of normalized Form 16 tax data."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_FOR_REVIEW = ["pan", "assessment_year", "gross_salary"]
OPTIONAL_FIELDS = [
    "financial_year", "salary_17_1", "perquisites_17_2",
    "profit_in_lieu_17_3", "section_10_exemptions", "salary_tds"
]

def check_completeness(normalized: dict) -> dict:
    fields = normalized.get("fields", {})
    missing_required = []
    missing_optional = []
    review_fields = []
    for name in REQUIRED_FOR_REVIEW:
        entry = fields.get(name, {})
        if entry.get("value") in (None, ""):
            missing_required.append(name)
        elif entry.get("status") == "review_required":
            review_fields.append(name)
    for name in OPTIONAL_FIELDS:
        entry = fields.get(name, {})
        if entry.get("value") in (None, ""):
            missing_optional.append(name)
        elif entry.get("status") == "review_required":
            review_fields.append(name)

    # Check component sum only when all three salary components are present.
    component_names = ["salary_17_1", "perquisites_17_2", "profit_in_lieu_17_3"]
    component_values = [fields.get(n, {}).get("value") for n in component_names]
    gross_value = fields.get("gross_salary", {}).get("value")
    consistency_warning = None
    if all(isinstance(v, (int, float)) for v in component_values) and isinstance(gross_value, (int, float)):
        component_total = sum(component_values)
        if abs(component_total - gross_value) > 1.0:
            consistency_warning = (
                "Salary component total differs from gross_salary; check source document "
                "and whether all salary components are represented."
            )

    warnings = []
    if missing_required:
        warnings.append("Required-for-review fields are missing: " + ", ".join(missing_required))
    if missing_optional:
        warnings.append("Optional fields are missing and remain null: " + ", ".join(missing_optional))
    if review_fields:
        warnings.append("Fields need manual review: " + ", ".join(sorted(set(review_fields))))
    if consistency_warning:
        warnings.append(consistency_warning)

    return {
        "report_type": "Form 16 tax-data completeness report",
        "required_fields_missing": missing_required,
        "optional_fields_missing": missing_optional,
        "fields_requiring_review": sorted(set(review_fields)),
        "salary_component_consistency_warning": consistency_warning,
        "warnings": warnings,
        "completeness_status": "review_required" if warnings else "complete_for_review",
        "tax_correctness_verified": False,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("normalized_json")
    parser.add_argument("-o", "--output", default="form16_completeness_report.json")
    args = parser.parse_args()
    data = json.loads(Path(args.normalized_json).read_text(encoding="utf-8"))
    report = check_completeness(data)
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Created {args.output}; status={report['completeness_status']}")

if __name__ == "__main__":
    main()
