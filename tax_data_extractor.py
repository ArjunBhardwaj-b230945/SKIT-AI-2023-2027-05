"""Initial label-based extraction from parsed text. Values are candidates, not verified tax facts."""
import re, json
from pathlib import Path
from tax_data_models import ExtractedField, TaxDataExtractionResult
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.I)
YEAR_RE = r"(20\d{2}\s*[-–]\s*\d{2,4})"
MONEY_RE = re.compile(r"(?:₹|Rs\.?|INR)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)", re.I)
def _field(value, source, evidence):
    return ExtractedField(value=value, source_document=source if value is not None else None,
      evidence=evidence, status="extracted_candidate" if value is not None else "missing")
def _identity(text, source):
    pan=PAN_RE.search(text.upper())
    ay=re.search(r"assessment\s+year\s*[:\-]?\s*"+YEAR_RE,text,re.I)
    fy=re.search(r"financial\s+year\s*[:\-]?\s*"+YEAR_RE,text,re.I)
    return (_field(pan.group(0).upper() if pan else None,source,pan.group(0) if pan else None),
      _field(ay.group(1).replace(" ","") if ay else None,source,ay.group(0) if ay else None),
      _field(fy.group(1).replace(" ","") if fy else None,source,fy.group(0) if fy else None))
def _after_label(text, labels, max_chars=140):
    for label in labels:
        m=re.search(label,text,re.I)
        if not m: continue
        tail=text[m.end():m.end()+max_chars]
        line=tail.splitlines()[0] if tail.splitlines() else tail
        line=re.sub(r"^[\s:|=\-–]+","",line).strip()
        if not line: continue
        money=MONEY_RE.search(line)
        if money: return money.group(1).replace(",",""), text[max(0,m.start()-25):m.end()+len(line)].strip()
        token=line.strip()
        if len(token)<=80: return token,text[max(0,m.start()-25):m.end()+len(line)].strip()
    return None,None
def extract_tax_data(form16_text, form26as_text):
    r=TaxDataExtractionResult()
    pan16,ay16,fy16=_identity(form16_text,"Form 16")
    pan26,ay26,fy26=_identity(form26as_text,"Form 26AS")
    r.taxpayer.pan=pan16 if pan16.value else pan26
    r.taxpayer.assessment_year=ay16 if ay16.value else ay26
    r.taxpayer.financial_year=fy16 if fy16.value else fy26
    gross,ge=_after_label(form16_text,[r"gross\s+salary",r"salary\s+as\s+per\s+section\s+17"])
    taxable,te=_after_label(form16_text,[r"income\s+chargeable\s+under\s+the\s+head\s+salaries",r"taxable\s+salary"])
    tds,de=_after_label(form16_text,[r"tax\s+deducted\s+at\s+source",r"tds\s+deducted"])
    r.salary.gross_salary=_field(gross,"Form 16",ge)
    r.salary.taxable_salary=_field(taxable,"Form 16",te)
    r.salary.tds_from_salary=_field(tds,"Form 16",de)
    r.form26as.total_tax_deducted.status="review_required"
    r.form26as.total_tax_deposited.status="review_required"
    r.warnings += ["Candidate values must be verified against source PDFs.",
      "Form 26AS totals are not summed because multiple deductor rows need table-aware parsing.",
      "No tax calculation, full cross-form reconciliation, ITR-1 mapping, validation, or filing is performed."]
    if pan16.value and pan26.value and pan16.value!=pan26.value:
        r.warnings.append("PAN mismatch detected between Form 16 and Form 26AS; stop and review.")
    if ay16.value and ay26.value and ay16.value!=ay26.value:
        r.warnings.append("Assessment-year mismatch detected between Form 16 and Form 26AS; review.")
    return r
def extract_from_files(form16_path,form26as_path,output_path):
    p16,p26=Path(form16_path),Path(form26as_path)
    result=extract_tax_data(p16.read_text(encoding="utf-8",errors="replace"),
      p26.read_text(encoding="utf-8",errors="replace")).to_dict()
    result["input_files"]={"form16":p16.name,"form26as":p26.name}
    Path(output_path).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return result
def main():
    import argparse
    p=argparse.ArgumentParser(); p.add_argument("form16_txt"); p.add_argument("form26as_txt")
    p.add_argument("--output",default="tax_data_extraction_report.json"); a=p.parse_args()
    print(json.dumps(extract_from_files(a.form16_txt,a.form26as_txt,a.output),indent=2,ensure_ascii=False))
if __name__=="__main__": main()
