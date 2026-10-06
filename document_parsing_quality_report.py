REQUIRED={"form16":["employee_pan","employer_tan","assessment_year"],"form26as":["pan","assessment_year"]}

def quality_report(document_type,data):
    fields=REQUIRED[document_type.lower()]
    present=[f for f in fields if data.get(f)]
    missing=[f for f in fields if not data.get(f)]
    return {"document_type":document_type,"required_fields":fields,"present_fields":present,"missing_fields":missing,"completeness_percent":round(len(present)/len(fields)*100,2),"status":"PASS" if not missing else "REVIEW"}
