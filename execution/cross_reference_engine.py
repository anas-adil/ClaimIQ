"""
cross_reference_engine.py — Deterministic Evidence Cross-Reference
"""

import logging
import re

logger = logging.getLogger("claimiq.xref")

def _normalize_name(name: str) -> str:
    if not name: return ""
    name = name.upper()
    name = re.sub(r'\b(BIN|BINTI|A/L|A/P)\b', '', name)
    return re.sub(r'[^A-Z]', '', name)

def check_identity_match(parsed_name: str, submitted_name: str) -> dict:
    if not parsed_name or not submitted_name:
        return {"match": True, "note": "Identity check skipped (missing data)"}
        
    norm_p = _normalize_name(parsed_name)
    norm_s = _normalize_name(submitted_name)
    
    if not norm_p or not norm_s:
        return {"match": True, "note": "Identity check skipped (unparseable names)"}
        
    if norm_s in norm_p or norm_p in norm_s:
        return {"match": True, "note": "Identity matches"}
        
    tokens_p = set(parsed_name.upper().replace('BINTI', '').replace('BIN', '').split())
    tokens_s = set(submitted_name.upper().replace('BINTI', '').replace('BIN', '').split())
    
    overlap = len(tokens_p.intersection(tokens_s))
    if overlap >= max(1, len(tokens_p) // 2) or overlap >= max(1, len(tokens_s) // 2):
         return {"match": True, "note": "Identity matches (partial)"}
         
    return {"match": False, "note": f"Mismatch: '{parsed_name}' vs '{submitted_name}'"}

def extract_number(text: str):
    if text is None: return None
    if isinstance(text, (int, float)): return float(text)
    match = re.search(r"(\d+(\.\d+)?)", str(text))
    return float(match.group(1)) if match else None

def _find_value_near_keyword(text: str, keywords: list, window: int = 200) -> float:
    """
    Search for a numeric value mentioned near any of the given keywords
    in the text. Uses a context window approach: find each keyword occurrence,
    then look for numbers within `window` characters after it.
    Returns the first matching number, or None.
    """
    text_lower = text.lower()
    for kw in keywords:
        for m in re.finditer(re.escape(kw), text_lower):
            # Extract the text window after the keyword
            start = m.end()
            end = min(start + window, len(text_lower))
            snippet = text_lower[start:end]
            # Find the first standalone number in the window
            num_match = re.search(r'(?<![a-z])(\d+(?:[,.]\d+)?)(?:\s*(?:x\s*10|×\s*10|x10))?', snippet)
            if num_match:
                val = extract_number(num_match.group(1))
                if val is not None and val > 0:
                    return val
    return None


def check_lab_vs_description(parsed_results: list, doctor_description: str) -> list:
    """Finds mismatches between doctor's claims and actual lab values.
    
    Uses a flexible keyword-window approach: for each lab result from the parsed
    image, search the doctor's text for the corresponding keyword (e.g., 'platelet'),
    then find the nearest number within a 200-char window after that keyword.
    If the doctor's stated value differs from the lab's actual value by >50%, flag it.
    """
    checks = []
    if not doctor_description:
        return checks
    
    # Map of: (lab test name keywords) → (doctor text search keywords, field label)
    LAB_CHECKS = [
        {
            "lab_keywords": ["platelet", "plt"],
            "doc_keywords": ["platelet", "plt"],
            "field": "Platelets",
            "normalize_thousands": True,  # handle 15 vs 15000 mismatch
        },
        {
            "lab_keywords": ["hematocrit", "hct"],
            "doc_keywords": ["hematocrit", "hct"],
            "field": "Hematocrit",
            "normalize_thousands": False,
        },
        {
            "lab_keywords": ["hemoglobin", "hgb", "hb "],
            "doc_keywords": ["hemoglobin", "hgb", "hb "],
            "field": "Hemoglobin",
            "normalize_thousands": False,
        },
        {
            "lab_keywords": ["crp", "c-reactive"],
            "doc_keywords": ["crp", "c-reactive"],
            "field": "CRP",
            "normalize_thousands": False,
        },
        {
            "lab_keywords": ["white blood cell", "wbc"],
            "doc_keywords": ["wbc", "white blood cell", "white cell"],
            "field": "WBC",
            "normalize_thousands": True,
        },
    ]
    
    for res in parsed_results:
        test_name = (res.get("test") or "").lower()
        lab_val = extract_number(res.get("value"))
        
        if not test_name or lab_val is None:
            continue
        
        for check_def in LAB_CHECKS:
            # Does this parsed result match this check definition?
            if not any(kw in test_name for kw in check_def["lab_keywords"]):
                continue
                
            # Search doctor's text for the corresponding value
            doc_val = _find_value_near_keyword(doctor_description, check_def["doc_keywords"])
            if doc_val is None:
                continue
            
            # Normalize units if needed (e.g., 15 x10^3 vs 15000)
            compare_doc = doc_val
            compare_lab = lab_val
            if check_def["normalize_thousands"]:
                if compare_doc > 1000 and compare_lab < 1000:
                    compare_doc /= 1000
                if compare_lab > 1000 and compare_doc < 1000:
                    compare_lab /= 1000
            
            # Check for >50% discrepancy
            diff = abs(compare_doc - compare_lab)
            baseline = max(compare_doc, compare_lab)
            if baseline > 0 and diff / baseline > 0.5:
                checks.append({
                    "check": "lab_vs_description",
                    "result": "CRITICAL_CONTRADICTION",
                    "field": check_def["field"],
                    "doctor_says": doc_val,
                    "lab_shows": lab_val,
                    "note": f"⚠️ FRAUD ALERT: Doctor stated {check_def['field']} ~{doc_val}, "
                            f"but the attached lab report shows {lab_val}. "
                            f"Discrepancy: {diff/baseline*100:.0f}%."
                })
            break  # Don't check same result against multiple definitions
            
    return checks

def check_invoice_vs_claim(parsed_invoice: dict, claimed_amount: float) -> dict:
    if not parsed_invoice or claimed_amount is None:
        return None
        
    grand_total = extract_number(parsed_invoice.get("grand_total"))
    if grand_total is not None and claimed_amount > 0:
        if abs(grand_total - claimed_amount) > 1.0: # RM 1 tolerance
            return {
                "check": "invoice_total",
                "result": "WARN",
                "field": "Total Amount",
                "doctor_says": claimed_amount,
                "invoice_shows": grand_total,
                "note": f"Claimed amount (RM {claimed_amount}) differs from invoice total (RM {grand_total})."
            }
    return None

import glm_client

def cross_reference_all(parsed_evidence_list: list, claim_data: dict, raw_text: str = "") -> dict:
    if not parsed_evidence_list:
        return {
            "verdict": "UNABLE_TO_VERIFY",
            "checks": [],
            "contradiction_count": 0,
            "critical_count": 0,
            "note": "No valid parsed evidence to cross-reference."
        }
        
    checks = []
    
    # 1. Identity Check (deterministic is fine)
    for parsed_evidence in parsed_evidence_list:
        if not parsed_evidence or parsed_evidence.get("source") in ["NO_EVIDENCE", "PARSE_FAILED"]:
            continue
            
        triage = parsed_evidence.get("triage", {})
        parsed_data = parsed_evidence.get("parsed_evidence", {})
        doc_type = triage.get("doc_type")
        
        submitted_name = claim_data.get("patient_name")
        parsed_name = None
        if doc_type == "LAB_REPORT":
            parsed_name = parsed_data.get("patient_name_on_report")
        elif doc_type == "INVOICE":
            parsed_name = parsed_data.get("patient_name_on_invoice")
            
        if parsed_name and submitted_name:
            id_check = check_identity_match(parsed_name, submitted_name)
            if not id_check["match"]:
                checks.append({
                    "check": "identity",
                    "result": "CRITICAL_CONTRADICTION",
                    "field": "Patient Name",
                    "note": id_check["note"]
                })
    
    # 2. GLM AI Alignment Check
    try:
        glm_align = glm_client.cross_reference_evidence(parsed_evidence_list, raw_text)
        
        for contra in glm_align.get("contradictory_evidence", []):
            checks.append({
                "check": "ai_evidence_alignment",
                "result": "CRITICAL_CONTRADICTION",
                "field": contra.get("field", "Clinical Evidence"),
                "doctor_says": contra.get("doctor_says", "N/A"),
                "lab_shows": contra.get("evidence_shows", "N/A"),
                "note": f"⚠️ FRAUD ALERT: Doctor stated {contra.get('field')} ~{contra.get('doctor_says')}, but evidence shows {contra.get('evidence_shows')}."
            })
    except Exception as e:
        logger.error(f"GLM Alignment check failed: {e}")
        
    # 3. GLM Invoice Validation
    invoice_list = [ev.get("parsed_evidence", {}) for ev in parsed_evidence_list if ev.get("triage", {}).get("doc_type") == "INVOICE"]
    for inv in invoice_list:
        try:
            glm_inv = glm_client.validate_invoice_against_treatment(inv, raw_text)
            for unjust in glm_inv.get("unjustified_items", []):
                checks.append({
                    "check": "phantom_billing",
                    "result": "CRITICAL_CONTRADICTION",
                    "field": "Invoice Item",
                    "doctor_says": "Not mentioned in clinical notes",
                    "invoice_shows": unjust.get("item_description", "Unknown"),
                    "note": f"⚠️ PHANTOM BILLING: Invoiced item '{unjust.get('item_description')}' (RM {unjust.get('amount')}) is not justified by the doctor's notes. Reason: {unjust.get('reason')}"
                })
        except Exception as e:
            logger.error(f"GLM Invoice check failed: {e}")
        
    critical_count = sum(1 for c in checks if c["result"] == "CRITICAL_CONTRADICTION")
    contradiction_count = len(checks)
    
    verdict = "PASS"
    if critical_count > 0:
        verdict = "FAIL"
    elif contradiction_count > 0:
        verdict = "WARN"
        
    return {
        "verdict": verdict,
        "checks": checks,
        "contradiction_count": contradiction_count,
        "critical_count": critical_count
    }
