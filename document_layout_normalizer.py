import re

def normalize_document_text(text: str) -> str:
    """Normalize parsed document text while preserving useful lines."""
    if not text: return ""
    text=text.replace("\x00"," ").replace("\r\n","\n").replace("\r","\n")
    for a,b in {"\u2013":"-","\u2014":"-","\u2212":"-","\u00a0":" "}.items(): text=text.replace(a,b)
    lines=[]
    for line in text.splitlines():
        line=re.sub(r"[ \t]+"," ",line).strip()
        if re.fullmatch(r"(?:page\s*)?\d+(?:\s+of\s+\d+)?",line,re.I): continue
        if line: lines.append(line)
    return "\n".join(lines)

def normalize_label(label: str) -> str:
    label=label.lower(); label=re.sub(r"[^a-z0-9]+"," ",label)
    return re.sub(r"\s+"," ",label).strip()
