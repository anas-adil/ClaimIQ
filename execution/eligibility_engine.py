"""
eligibility_engine.py — Member eligibility verification

Real TPA equivalent: EDI 270/271 eligibility check.
Verifies active coverage, benefit limits, patient responsibility.
"""

import sys, os, json, logging
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
import database as db

logger = logging.getLogger("claimiq.eligibility")

SYNTHETIC_MEMBERS = [
    {"member_id": "PMC-001", "ic_number": "900215-14-3456", "name": "Siti Nurhaliza binti Mohd",
     "plan_id": "PMC-GOLD", "benefit_tier": "GOLD", "coverage_start_date": "2024-01-01",
     "coverage_end_date": "2026-12-31", "deductible": 0, "copay": 5, "max_per_visit": 300, "outpatient_limit": 2000},
    {"member_id": "PMC-002", "ic_number": "850315-14-5234", "name": "Ahmad bin Ibrahim",
     "plan_id": "PMC-STANDARD", "benefit_tier": "STANDARD", "coverage_start_date": "2024-01-01",
     "coverage_end_date": "2026-12-31", "deductible": 50, "copay": 10, "max_per_visit": 200, "outpatient_limit": 1000},
    {"member_id": "PMC-003", "ic_number": "780503-07-1234", "name": "Tan Wei Ming",
     "plan_id": "PMC-BRONZE", "benefit_tier": "BRONZE", "coverage_start_date": "2025-06-01",
     "coverage_end_date": "2026-05-31", "deductible": 100, "copay": 15, "max_per_visit": 150, "outpatient_limit": 600},
    {"member_id": "PMC-004", "ic_number": "880505-10-5555", "name": "Siti Nurhaliza",
     "plan_id": "PMC-GOLD", "benefit_tier": "GOLD", "coverage_start_date": "2024-01-01",
     "coverage_end_date": "2026-12-31", "deductible": 0, "copay": 5, "max_per_visit": 300, "outpatient_limit": 2000},
    {"member_id": "PMC-005", "ic_number": "900101-14-1234", "name": "Lee Chong Wei",
     "plan_id": "PMC-GOLD", "benefit_tier": "GOLD", "coverage_start_date": "2024-01-01",
     "coverage_end_date": "2026-12-31", "deductible": 0, "copay": 5, "max_per_visit": 500, "outpatient_limit": 3000},
]


def ensure_members_seeded():
    """Seed or update synthetic members."""
    db.seed_members(SYNTHETIC_MEMBERS)
    logger.info(f"Synchronized {len(SYNTHETIC_MEMBERS)} synthetic members to database")


def check_eligibility(ic_number: str, visit_date_str: str, total_amount: float = 0, claim_id: int = None) -> dict:
    """
    Verify member eligibility for a claim.
    Returns structured eligibility result.
    """
    if not db.has_members_seeded():
        return {
            "eligible": False,
            "reason": "MEMBER_REGISTRY_UNAVAILABLE",
            "carc_code": "MA130",
            "message": "Member registry is empty. Run seed/migration command before adjudication.",
            "member": None,
            "patient_responsibility_myr": 0.0,
        }
    
    # Normalize IC (remove non-digits for flexible lookup if needed, but DB currently has dashes)
    # Actually, let's keep dashes for now as per DB, but strip whitespace.
    ic_number = (ic_number or "").strip()
    try:
        total_amount = float(total_amount or 0.0)
    except (TypeError, ValueError):
        total_amount = 0.0
    member = db.get_member_by_ic(ic_number)

    if not member:
        return {
            "eligible": False,
            "reason": "MEMBER_NOT_FOUND",
            "carc_code": "MA130",
            "message": f"No member found with IC {ic_number}",
            "member": None,
            "patient_responsibility_myr": total_amount,
        }

    # Check active coverage
    today = date.today()
    try:
        start = date.fromisoformat(member["coverage_start_date"])
        end = date.fromisoformat(member["coverage_end_date"])
        visit_date = date.fromisoformat(visit_date_str) if visit_date_str else today
    except (ValueError, TypeError):
        visit_date = today
        start = today
        end = today

    if not member["is_active"]:
        return {"eligible": False, "reason": "COVERAGE_INACTIVE", "carc_code": "27",
                "message": "Member's coverage is not active", "member": dict(member),
                "patient_responsibility_myr": total_amount}

    if visit_date < start or visit_date > end:
        return {"eligible": False, "reason": "OUTSIDE_COVERAGE_PERIOD", "carc_code": "27",
                "message": f"Service date {visit_date_str} outside coverage {start}–{end}",
                "member": dict(member), "patient_responsibility_myr": total_amount}

    # Check outpatient limit
    used = member["outpatient_used_myr"] or 0
    limit = member["annual_outpatient_limit_myr"] or 1000
    if used >= limit:
        return {"eligible": False, "reason": "BENEFIT_EXHAUSTED", "carc_code": "97",
                "message": f"Annual outpatient limit of RM {limit:.2f} has been fully utilised",
                "member": dict(member), "patient_responsibility_myr": total_amount}

    # Calculate patient responsibility
    copay = member["copay_myr"] or 10
    max_visit = member["max_per_visit_myr"] or 200
    covered = max(0.0, min(total_amount, max_visit, limit - used))
    patient_resp = total_amount - covered + copay
    patient_resp = max(0, patient_resp)

    # Transactionally preserve utilization if this check belongs to a claim run.
    if claim_id:
        db.consume_member_outpatient_limit(
            claim_id=claim_id,
            member_id=member["member_id"],
            ic_number=ic_number,
            covered_amount_myr=covered,
        )

    return {
        "eligible": True,
        "reason": "ELIGIBLE",
        "carc_code": None,
        "message": f"Member eligible under {member['plan_id']} ({member['benefit_tier']} tier)",
        "member": dict(member),
        "benefit_tier": member["benefit_tier"],
        "covered_amount_myr": round(covered, 2),
        "patient_responsibility_myr": round(patient_resp, 2),
        "copay_myr": copay,
        "remaining_benefit_myr": round(limit - used - covered, 2),
        "max_per_visit_myr": max_visit,
    }


def simulate_eligibility_for_unknown(total_amount: float) -> dict:
    """Deprecated simulation path; now deterministic fail-closed for safety."""
    try:
        total_amount = float(total_amount or 0.0)
    except (TypeError, ValueError):
        total_amount = 0.0
    return {
        "eligible": False,
        "reason": "MEMBER_NOT_FOUND",
        "carc_code": "MA130",
        "message": "Member not found in PMCare registry.",
        "patient_responsibility_myr": total_amount,
    }
