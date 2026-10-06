import re

PAN=r"[A-Z]{5}[0-9]{4}[A-Z]"
TAN=r"[A-Z]{4}[0-9]{5}[A-Z]"

def _num(v):
    try: return float(v.replace(",","").replace("₹","").strip())
    except (ValueError,AttributeError): return None

def extract_form26as(text):
    result={"pan":None,"assessment_year":None,"tds_rows":[],"advance_tax_rows":[]}
    m=re.search(rf"\bPAN\s*[:\-]?\s*({PAN})",text,re.I)
    if m: result["pan"]=m.group(1).upper()
    m=re.search(r"Assessment\s*Year\s*[:\-]?\s*((?:20)?\d{2}\s*[-/]\s*(?:20)?\d{2})",text,re.I)
    if m: result["assessment_year"]=m.group(1).replace(" ","")
    for line in text.splitlines():
        line=line.strip()
        if not line: continue
        tan=re.search(rf"\b({TAN})\b",line)
        nums=re.findall(r"₹?\s*\d[\d,]*(?:\.\d+)?",line)
        amounts=[x for x in (_num(v) for v in nums) if x is not None]
        if tan and amounts:
            result["tds_rows"].append({"deductor_tan":tan.group(1).upper(),"amounts_found":amounts,"source_line":line})
        elif re.search(r"\b\d{2}[-/]\d{2}[-/]\d{4}\b",line) and amounts:
            result["advance_tax_rows"].append({"amounts_found":amounts,"source_line":line})
    return result
