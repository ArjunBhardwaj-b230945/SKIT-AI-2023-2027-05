"""Label rules and evidence snippets for parsed Form 16/Form 26AS text; no OCR."""
import re
FORM16_FIELDS = {
    "employee_name": [r"\bname of the employee\b", r"\bemployee name\b"],
    "employer_name": [r"\bname and address of the employer\b", r"\bemployer name\b"],
    "pan_employee": [r"\bpan of the employee\b", r"\bemployee pan\b", r"\bpan\b"],
    "assessment_year": [r"\bassessment year\b"],
    "gross_salary": [r"\bgross salary\b", r"\b17\(1\)\b"],
    "perquisites": [r"\bvalue of perquisites\b", r"\b17\(2\)\b"],
    "profits_in_lieu": [r"\bprofits in lieu of salary\b", r"\b17\(3\)\b"],
    "exemptions": [r"\bexempt allowances\b", r"\bsection 10\b"],
    "standard_deduction": [r"\bstandard deduction\b"],
    "taxable_salary": [r"\bincome chargeable under the head salaries\b", r"\btaxable salary\b"],
    "tds_deducted": [r"\btax deducted at source\b", r"\btds\b"],
}
FORM26AS_FIELDS = {
    "pan_taxpayer": [r"\bpan of the taxpayer\b", r"\btaxpayer pan\b", r"\bpan\b"],
    "assessment_year": [r"\bassessment year\b"],
    "financial_year": [r"\bfinancial year\b"],
    "deductor_name": [r"\bname of deductor\b", r"\bdeductor name\b"],
    "tan_deductor": [r"\btan of deductor\b", r"\bdeductor tan\b"],
    "section": [r"\bsection\b"],
    "amount_paid_credited": [r"\bamount paid\b", r"\bamount credited\b"],
    "tax_deducted": [r"\btax deducted\b"],
    "tax_deposited": [r"\btax deposited\b"],
    "refund": [r"\brefund\b"],
}
def normalize_text(text):
    text = text.replace("\x00", " ")
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
def find_label_evidence(text, patterns, window=160):
    hits = []
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.I):
            hits.append({"label": m.group(0), "start": m.start(),
                         "snippet": text[max(0,m.start()-40):min(len(text),m.end()+window)].replace("\n"," ").strip()})
    return sorted(hits, key=lambda h:h["start"])[:5]
def review_fields(text, rules):
    return {name: {"found": bool(ev), "evidence": ev,
                   "status": "review_required" if ev else "missing_or_unrecognized"}
            for name, patterns in rules.items()
            for ev in [find_label_evidence(text, patterns)]}
