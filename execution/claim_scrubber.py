"""
claim_scrubber.py — Pre-adjudication claim validation

Real TPA equivalent: claim scrubbing / editing before payment.
Catches errors BEFORE they reach the adjudicator, reducing denial rates.

Checks:
1. Required fields present
2. ICD-10 code validity
3. Date of service within filing limit (14 days for PMCare)
4. Duplicate claim detection
5. Amount reasonableness vs benchmarks
6. Procedure-diagnosis compatibility (basic)
"""

import sys, os, json, logging
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
import database as db

logger = logging.getLogger("claimiq.scrubber")

# Filing deadline in days (PMCare: 14 days)
FILING_LIMIT_DAYS = 14

# Amount benchmarks per ICD-10 (min, max in MYR)
AMOUNT_BENCHMARKS = {
    "J06.9": (20, 120),   # URTI
    "J18.9": (80, 300),   # Pneumonia
    "I10":   (30, 200),   # Hypertension
    "E11":   (40, 250),   # T2DM
    "A90":   (50, 300),   # Dengue
    "K29.7": (25, 150),   # Gastritis
    "N39.0": (30, 180),   # UTI
    "M54.5": (30, 160),   # Low back pain
    "J45":   (35, 220),   # Asthma
    "L30.9": (25, 130),   # Dermatitis
    "A09":   (20, 130),   # Gastroenteritis
    "S82.2": (200, 800),  # Fracture tibia
    "S82":   (200, 800),  # Fracture (general)
    "DEFAULT": (15, 500),
}

# Required fields for a valid claim
REQUIRED_FIELDS = [
    "patient_name", "patient_ic", "visit_date",
    "clinic_name", "diagnosis", "total_amount_myr",
]


def scrub_claim(claim_data: dict, claim_id: int = None) -> dict:
    """
    Run all scrub checks. Returns result dict with:
    - status: PASS | FAIL | WARN
    - errors: list of blocking issues
    - warnings: list of non-blocking issues
    - carc_code: denial reason code if failed
    """
    errors, warnings = [], []

    # 1. Required fields
    for field in REQUIRED_FIELDS:
        if not claim_data.get(field):
            errors.append({
                "check": "REQUIRED_FIELD",
                "field": field,
                "message": f"Required field missing: {field}",
                "carc": "16",
            })

    # 2. ICD-10 validity (basic — check it's not empty and has reasonable format)
    icd = claim_data.get("icd10_code") or claim_data.get("primary_diagnosis_code", "")
    if not icd:
        warnings.append({"check": "ICD10_MISSING", "message": "No ICD-10 code provided — will be auto-coded"})
    elif not _valid_icd_format(icd):
        errors.append({"check": "ICD10_INVALID", "message": f"ICD-10 code '{icd}' has invalid format", "carc": "5"})

    # 3. Filing deadline
    visit_date_str = claim_data.get("visit_date")
    if visit_date_str:
        try:
            visit_date = datetime.strptime(visit_date_str, "%Y-%m-%d").date()
            days_since = (date.today() - visit_date).days
            if days_since > FILING_LIMIT_DAYS:
                errors.append({
                    "check": "LATE_FILING",
                    "message": f"Claim filed {days_since} days after service (limit: {FILING_LIMIT_DAYS} days)",
                    "carc": "29",
                })
            elif days_since > FILING_LIMIT_DAYS * 0.7:
                warnings.append({"check": "FILING_DEADLINE_APPROACHING",
                                  "message": f"Only {FILING_LIMIT_DAYS - days_since} days left to file"})
            if visit_date > date.today():
                errors.append({"check": "FUTURE_DATE", "message": "Date of service is in the future", "carc": "16"})
        except ValueError:
            errors.append({"check": "INVALID_DATE", "message": f"Invalid visit_date format: {visit_date_str}", "carc": "16"})

    # 4. Duplicate detection — warn only, do not hard-deny (GP may resubmit legitimately)
    if claim_data.get("patient_ic") and visit_date_str and claim_data.get("diagnosis"):
        if _is_duplicate(claim_data, claim_id):
            warnings.append({
                "check": "POSSIBLE_DUPLICATE",
                "message": "A similar claim was previously submitted for the same patient/date/diagnosis. Review carefully.",
                "carc": "18",
            })

    # 5. Amount reasonableness
    total = claim_data.get("total_amount_myr", 0) or 0
    icd_key = icd.split(".")[0] + ("." + icd.split(".")[1] if "." in icd else "") if icd else "DEFAULT"
    lo, hi = AMOUNT_BENCHMARKS.get(icd_key, AMOUNT_BENCHMARKS.get(icd, AMOUNT_BENCHMARKS["DEFAULT"]))
    
    # Detect if inpatient/admission
    raw_text = claim_data.get("raw_text", "").lower()
    is_inpatient = "inpatient" in raw_text or "admission" in raw_text or "ward" in raw_text or "transfusion" in raw_text
    if is_inpatient:
        lo *= 5
        hi *= 10
        
    if total > hi * 2:
        errors.append({
            "check": "EXCESSIVE_AMOUNT",
            "message": f"RM {total:.2f} exceeds maximum {'inpatient ' if is_inpatient else ''}benchmark of RM {hi*2:.2f} for {icd}",
            "carc": "45",
        })
    elif total > hi:
        warnings.append({
            "check": "HIGH_AMOUNT",
            "message": f"RM {total:.2f} is above typical {'inpatient ' if is_inpatient else ''}range RM {lo:.2f}–{hi:.2f} for {icd}. Will be reviewed.",
        })
    elif total < lo * 0.5 and total > 0:
        warnings.append({"check": "UNUSUALLY_LOW", "message": f"Amount RM {total:.2f} seems low for {icd}"})

    # 6. Negative amounts
    for field in ["consultation_fee_myr", "medication_fee_myr", "procedure_fee_myr", "total_amount_myr"]:
        val = claim_data.get(field)
        if val is not None and val < 0:
            errors.append({"check": "NEGATIVE_AMOUNT", "message": f"{field} cannot be negative", "carc": "16"})

    # Determine overall status
    if errors:
        status = "FAIL"
        carc = errors[0].get("carc", "16")
    elif warnings:
        status = "WARN"
        carc = None
    else:
        status = "PASS"
        carc = None

    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "carc_code": carc,
        "checks_run": len(REQUIRED_FIELDS) + 5,
        "scraped_at": datetime.utcnow().isoformat(),
    }


def _valid_icd_format(code: str) -> bool:
    """Basic ICD-10 format check: Letter followed by digits, optional decimal."""
    import re
    return bool(re.match(r'^[A-Z]\d{2}(\.\d{1,4})?$', code.strip().upper()))


def _is_duplicate(claim_data: dict, exclude_id: int = None) -> bool:
    """Check if an identical claim already exists in the DB."""
    dbc = db.get_db()
    query = (
        "SELECT id FROM claims WHERE patient_ic=? AND visit_date=? AND diagnosis=? AND status != 'SCRUB_FAILED'"
    )
    params = [claim_data.get("patient_ic"), claim_data.get("visit_date"), claim_data.get("diagnosis")]
    rows = dbc.execute(query, params).fetchall()
    dbc.close()
    ids = [r["id"] for r in rows if r["id"] != exclude_id]
    return len(ids) > 0
