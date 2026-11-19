"""
TaxSathi - Structured Document Parsing Output
Week: 25-09-2026 to 01-10-2026

Converts detected Form 16 / Form 26AS fields into a consistent,
JSON-serializable structure. This is an extraction layer only.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Optional
import json


@dataclass
class Form16StructuredData:
    employee_pan: Optional[str] = None
    employer_tan: Optional[str] = None
    assessment_year: Optional[str] = None
    salary_17_1: Optional[float] = None
    perquisites_17_2: Optional[float] = None
    profit_in_lieu_17_3: Optional[float] = None
    travel_concession_10_5: Optional[float] = None
    hra_10_13a: Optional[float] = None
    standard_deduction_16_ia: Optional[float] = None
    tax_deducted: Optional[float] = None


@dataclass
class Form26ASStructuredData:
    pan: Optional[str] = None
    assessment_year: Optional[str] = None
    tds_rows: list[dict[str, Any]] = field(default_factory=list)
    advance_tax_rows: list[dict[str, Any]] = field(default_factory=list)


def build_form16(data: dict[str, Any]) -> Form16StructuredData:
    return Form16StructuredData(**{
        key: data.get(key)
        for key in Form16StructuredData.__dataclass_fields__
    })


def build_form26as(data: dict[str, Any]) -> Form26ASStructuredData:
    return Form26ASStructuredData(
        pan=data.get("pan"),
        assessment_year=data.get("assessment_year"),
        tds_rows=data.get("tds_rows", []),
        advance_tax_rows=data.get("advance_tax_rows", []),
    )


def to_json(data: Any) -> str:
    """Return structured extraction as readable JSON."""
    return json.dumps(asdict(data), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    data = build_form16({
        "employee_pan": "ABCDE1234F",
        "assessment_year": "2026-27",
        "salary_17_1": 750000,
    })
    print(to_json(data))
