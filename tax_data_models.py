"""Intermediate candidate data models; not the final ITR-1 schema."""
from dataclasses import dataclass, field, asdict
from typing import Optional, List
@dataclass
class ExtractedField:
    value: Optional[str] = None
    source_document: Optional[str] = None
    evidence: Optional[str] = None
    status: str = "not_extracted"
@dataclass
class TaxpayerIdentity:
    pan: ExtractedField = field(default_factory=ExtractedField)
    assessment_year: ExtractedField = field(default_factory=ExtractedField)
    financial_year: ExtractedField = field(default_factory=ExtractedField)
@dataclass
class SalaryTaxData:
    gross_salary: ExtractedField = field(default_factory=ExtractedField)
    taxable_salary: ExtractedField = field(default_factory=ExtractedField)
    tds_from_salary: ExtractedField = field(default_factory=ExtractedField)
@dataclass
class Form26ASTaxData:
    total_tax_deducted: ExtractedField = field(default_factory=ExtractedField)
    total_tax_deposited: ExtractedField = field(default_factory=ExtractedField)
@dataclass
class TaxDataExtractionResult:
    taxpayer: TaxpayerIdentity = field(default_factory=TaxpayerIdentity)
    salary: SalaryTaxData = field(default_factory=SalaryTaxData)
    form26as: Form26ASTaxData = field(default_factory=Form26ASTaxData)
    warnings: List[str] = field(default_factory=list)
    review_required: bool = True
    def to_dict(self): return asdict(self)
