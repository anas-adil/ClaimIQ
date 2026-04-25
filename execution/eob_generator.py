"""
eob_generator.py — Structured EOB generation

Generates an Explanation of Benefits (EOB) document representation
based on adjudication results and member eligibility.
"""

import sys, os, json, logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
import database as db

logger = logging.getLogger("claimiq.eob")

def generate_eob(claim_id: int, claim_data: dict, adjudication: dict, eligibility: dict) -> dict:
    """Generate structured EOB."""
    total_billed = claim_data.get("total_amount_myr", 0)
    decision = adjudication.get("decision", "DENIED")
    
    if decision == "APPROVED":
        covered = adjudication.get("amount_approved_myr", 0)
        patient_resp = total_billed - covered
        denial_code = None
        denial_desc = None
        eob_text = f"Claim for RM {total_billed:.2f} approved. Plan covers RM {covered:.2f}. Patient responsibility: RM {patient_resp:.2f}."
        eob_text_bm = f"Tuntutan sebanyak RM {total_billed:.2f} diluluskan. Pelan menanggung RM {covered:.2f}. Tanggungjawab pesakit: RM {patient_resp:.2f}."
    else:
        covered = 0
        patient_resp = total_billed
        denial_code = adjudication.get("denial_reason_code", "4")
        denial_desc = adjudication.get("denial_reason_description", "The service/drug/supply is not covered")
        eob_text = f"Claim for RM {total_billed:.2f} denied. Reason code {denial_code}: {denial_desc}. Patient responsibility: RM {patient_resp:.2f}."
        eob_text_bm = f"Tuntutan sebanyak RM {total_billed:.2f} ditolak. Kod sebab {denial_code}: {denial_desc}. Tanggungjawab pesakit: RM {patient_resp:.2f}."

    result = {
        "billed_amount_myr": total_billed,
        "covered_amount_myr": covered,
        "patient_responsibility_myr": patient_resp,
        "denial_code": denial_code,
        "denial_description": denial_desc,
        "eob_text": eob_text,
        "eob_text_bm": eob_text_bm,
    }
    
    db.insert_eob(claim_id, result)
    return result
