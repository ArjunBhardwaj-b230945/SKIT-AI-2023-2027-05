import re
from typing import Any, Optional

PAN=r"[A-Z]{5}[0-9]{4}[A-Z]"
TAN=r"[A-Z]{4}[0-9]{5}[A-Z]"

def _amount(v: str)->Optional[float]:
    try: return float(v.replace(",","").replace("₹","").strip())
    except (ValueError,AttributeError): return None

def _value(text, patterns):
    for p in patterns:
        m=re.search(p,text,re.I|re.M)
        if m: return m.group(1).strip()
    return None

def _money(text, patterns):
    v=_value(text,patterns); return _amount(v) if v is not None else None

def extract_form16(text: str)->dict[str,Any]:
    return {
      "employee_pan":_value(text,[rf"(?:employee|deductee).*?PAN\s*[:\-]?\s*({PAN})",rf"\bPAN\s*[:\-]?\s*({PAN})"]),
      "employer_tan":_value(text,[rf"(?:employer|deductor).*?TAN\s*[:\-]?\s*({TAN})",rf"\bTAN\s*[:\-]?\s*({TAN})"]),
      "assessment_year":_value(text,[r"Assessment\s*Year\s*[:\-]?\s*((?:20)?\d{2}\s*[-/]\s*(?:20)?\d{2})"]),
      "salary_17_1":_money(text,[r"salary\s+as\s+per\s+section\s+17\s*\(\s*1\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)"]),
      "perquisites_17_2":_money(text,[r"perquisites.*?17\s*\(\s*2\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)"]),
      "profit_in_lieu_17_3":_money(text,[r"profits?\s+in\s+lieu.*?17\s*\(\s*3\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)"]),
      "travel_concession_10_5":_money(text,[r"travel\s+concession.*?10\s*\(\s*5\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)"]),
      "hra_10_13a":_money(text,[r"(?:house\s+rent\s+allowance|HRA).*?10\s*\(\s*13A\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)"]),
      "standard_deduction_16_ia":_money(text,[r"standard\s+deduction.*?16\s*\(\s*ia\s*\).*?₹?\s*([\d,]+(?:\.\d+)?)"]),
      "tax_deducted":_money(text,[r"(?:total\s+)?tax\s+deducted.*?₹?\s*([\d,]+(?:\.\d+)?)"]),
    }
