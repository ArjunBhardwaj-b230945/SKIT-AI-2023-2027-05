"""Evidence-aware comparison of Form 16 salary TDS and Form 26AS candidates."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
import json
from pathlib import Path


def _decimal(value: Any):
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("₹", "").strip())
    except (InvalidOperation, ValueError):
        return None


def reconcile_tds(form16_salary_tds: Any, form26as_tax_credit_candidates: list[Any], tolerance: str = "1.00") -> dict:
    """Compare Form 16 salary TDS with a supplied list of candidate Form 26AS credits.

    Caller must ensure the list contains only relevant salary TDS credits and not
    all TDS/TCS categories. Because heuristic rows may include non-tax amounts,
    the result remains review_required even when totals match.
    """
    form16 = _decimal(form16_salary_tds)
    credits = [_decimal(item) for item in form26as_tax_credit_candidates]
    invalid_count = sum(item is None for item in credits)
    valid_credits = [item for item in credits if item is not None]
    form26as_total = sum(valid_credits, Decimal("0"))
    tol = _decimal(tolerance) or Decimal("1.00")

    if form16 is None:
        difference = None
        comparison = "not_comparable_missing_form16_tds"
    else:
        difference = form26as_total - form16
        if invalid_count:
            comparison = "not_comparable_invalid_candidate_amounts"
        elif abs(difference) <= tol:
            comparison = "candidate_totals_match_within_tolerance"
        else:
            comparison = "candidate_totals_differ"

    return {
        "form16_salary_tds": str(form16.quantize(Decimal("0.01"))) if form16 is not None else None,
        "form26as_candidate_total": str(form26as_total.quantize(Decimal("0.01"))),
        "difference_form26as_minus_form16": str(difference.quantize(Decimal("0.01"))) if difference is not None else None,
        "candidate_count": len(credits),
        "valid_candidate_count": len(valid_credits),
        "invalid_candidate_count": invalid_count,
        "tolerance": str(tol.quantize(Decimal("0.01"))),
        "comparison": comparison,
        "status": "review_required",
        "warnings": [
            "This is a candidate-level comparison, not a tax-credit confirmation.",
            "Confirm each Form 26AS row belongs to the taxpayer and relevant salary TDS category.",
            "Do not use this result alone to file an ITR."
        ],
    }


def reconcile_json(input_json: str | Path, output_json: str | Path) -> dict:
    """Input shape: {'form16_salary_tds': '...', 'form26as_credit_candidates': ['...']}."""
    source = json.loads(Path(input_json).read_text(encoding="utf-8"))
    result = reconcile_tds(
        source.get("form16_salary_tds"),
        source.get("form26as_credit_candidates", []),
        source.get("tolerance", "1.00"),
    )
    Path(output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compare Form 16 salary TDS with selected Form 26AS credit candidates.")
    parser.add_argument("input_json")
    parser.add_argument("--output", default="tds_reconciliation_report.json")
    args = parser.parse_args()
    result = reconcile_json(args.input_json, args.output)
    print(f"Comparison: {result['comparison']} | Status: review_required | Output: {args.output}")


if __name__ == "__main__":
    main()
