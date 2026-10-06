import argparse,json
from pathlib import Path
from document_layout_normalizer import normalize_document_text
from form16_extraction import extract_form16
from form26as_extraction import extract_form26as

def parse_document(text, document_type):
    normalized=normalize_document_text(text)
    if document_type=="form16": data=extract_form16(normalized)
    elif document_type=="form26as": data=extract_form26as(normalized)
    else: raise ValueError("document_type must be form16 or form26as")
    return {"document_type":document_type,"source_text_length":len(text),"normalized_text_length":len(normalized),"data":data}

def process_text_file(input_file,document_type,output_dir="structured_output"):
    p=Path(input_file); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    result=parse_document(p.read_text(encoding="utf-8"),document_type)
    dest=out/f"{p.stem}_structured.json"
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return dest

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("input_file"); ap.add_argument("--type",required=True,choices=["form16","form26as"]); ap.add_argument("--output-dir",default="structured_output")
    a=ap.parse_args(); print(f"Structured output saved to: {process_text_file(a.input_file,a.type,a.output_dir)}")
