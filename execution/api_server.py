"""
api_server.py (v2) — FastAPI server for ClaimIQ

New endpoints (v2):
- POST /api/claims/scrub         — Pre-adjudication validation
- POST /api/claims/eligibility   — Member eligibility check
- POST /api/claims/appeal/{id}   — Submit appeal
- GET  /api/analytics/kpis       — KPI metrics
- GET  /api/analytics/clinics    — Clinic performance
- GET  /api/analytics/denials    — Denial breakdown
- GET  /api/analytics/weekly-report — GLM weekly narrative report
- POST /api/claims/{id}/chat     — Ask GLM about a claim
"""

import sys, os, json, logging
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from dotenv import load_dotenv
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import database as db
import claims_processor
import glm_client
import rag_engine
import claim_scrubber
import eligibility_engine

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("claimiq.api")

app = FastAPI(title="ClaimIQ API v2", version="2.0.0",
              description="Z.AI GLM-Powered TPA Claims Intelligence")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
if "*" in ALLOWED_ORIGINS and (os.getenv("APP_ENV") or "dev").lower() in ("prod", "production"):
    raise RuntimeError("Wildcard CORS is forbidden in production. Set explicit ALLOWED_ORIGINS.")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT"], allow_headers=["Authorization", "Content-Type"])


import requests

# --- Request Models ---
from pydantic import BaseModel, Field, constr
import re

class ClaimSubmission(BaseModel):
    raw_text: constr(min_length=10, max_length=5000)
    bill_attached: Optional[bool] = False
    evidence_attached: Optional[bool] = False
    evidence_base64: Optional[str] = None
    invoice_base64: Optional[str] = None
    patient_name: constr(min_length=2, max_length=100)
    patient_ic: constr(pattern=r"^\d{6}-\d{2}-\d{4}$")
    clinic_name: constr(min_length=2, max_length=150)
    total_amount_myr: float = Field(..., ge=0.0, le=100000.0)
    visit_date: constr(pattern=r"^\d{4}-\d{2}-\d{2}$")

class DemoGenerate(BaseModel):
    count: int = 50

class AppealSubmission(BaseModel):
    appeal_reason: str
    supporting_evidence: Optional[str] = ""

class ChatQuestion(BaseModel):
    question: str


class EligibilityRequest(BaseModel):
    ic_number: constr(pattern=r"^\d{6}-\d{2}-\d{4}$")
    visit_date: constr(pattern=r"^\d{4}-\d{2}-\d{2}$")
    total_amount_myr: float = Field(..., ge=0.0, le=100000.0)


def _require_operator_role(authorization: Optional[str] = Header(default=None)):
    expected = os.getenv("API_BEARER_TOKEN", "").strip()
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    token = authorization.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="AUTH_FORBIDDEN")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "VALIDATION_ERROR", "details": exc.errors()},
    )


# --- Helpers ---
def _parse_json_fields(obj: dict, fields: list) -> dict:
    for f in fields:
        if obj.get(f) and isinstance(obj[f], str):
            try:
                obj[f] = json.loads(obj[f])
            except (json.JSONDecodeError, TypeError):
                pass
    return obj

# _call_huggingface_vision removed (Phase 5) - Replaced by MedGemma client

# ── Claims ─────────────────────────────────────────────────

@app.post("/api/claims/submit")
async def submit_claim(body: ClaimSubmission):
    # Store everything, parse nothing yet.
    # Evidence parsing will be handled during processing via MedGemma.
    initial_data = {}
    if body.patient_name:
        initial_data["patient_name"] = body.patient_name
    if body.patient_ic:
        initial_data["patient_ic"] = body.patient_ic
    if body.clinic_name:
        initial_data["clinic_name"] = body.clinic_name
    initial_data["visit_date"] = body.visit_date
    initial_data["total_amount_myr"] = body.total_amount_myr
    if body.evidence_base64:
        initial_data["_evidence_base64"] = body.evidence_base64
    if body.invoice_base64:
        initial_data["_invoice_base64"] = body.invoice_base64
    initial_data["_evidence_attached"] = body.evidence_attached

    # We preserve the raw text as the primary medical packet
    medical_packet = (
        f"--- PATIENT INFO ---\n"
        f"Name: {body.patient_name or 'UNKNOWN'}\n"
        f"IC: {body.patient_ic or 'UNKNOWN'}\n"
        f"Clinic: {body.clinic_name or 'UNKNOWN'}\n"
        f"Date: {body.visit_date}\n\n"
        f"--- CLINICAL NOTES ---\n{body.raw_text}\n\n"
        f"--- ATTACHED EVIDENCE ---\n"
        f"Itemized Bill Attached: {'YES' if body.bill_attached else 'NO'}\n"
        f"Lab Results/X-Rays Attached: {'YES' if body.evidence_attached else 'NO'}\n"
        f"Vision Analysis Source: MEDGEMMA_PENDING\n"
    )

    claim_id = db.insert_claim(medical_packet, extracted=initial_data if initial_data else None)
    return {"claim_id": claim_id, "status": "INTAKE"}


@app.post("/api/claims/scrub")
async def scrub_claim_endpoint(body: ClaimSubmission):
    """Run pre-adjudication scrub checks without full processing."""
    claim_data = {"raw_text": body.raw_text}
    result = claim_scrubber.scrub_claim(claim_data)
    return result


@app.post("/api/claims/eligibility")
async def check_eligibility(body: EligibilityRequest):
    """Check member eligibility by IC number."""
    result = eligibility_engine.check_eligibility(
        body.ic_number,
        body.visit_date,
        body.total_amount_myr,
    )
    return result


@app.post("/api/claims/process/{claim_id}")
async def process_claim(claim_id: int, _: None = Depends(_require_operator_role)):
    claim = db.get_claim(claim_id)
    if not claim:
        raise HTTPException(404, f"Claim {claim_id} not found")
    result = claims_processor.process_claim(claim_id=claim_id)
    return result


@app.get("/api/claims/{claim_id}")
async def get_claim(claim_id: int):
    result = db.get_full_claim(claim_id)
    if not result:
        raise HTTPException(404, f"Claim {claim_id} not found")
    _parse_json_fields(result, ["extracted_data", "coded_data", "scrub_result", "eligibility_result"])
    if result.get("decision"):
        _parse_json_fields(result["decision"], ["full_result", "policy_references", "conditions"])
    if result.get("fraud"):
        _parse_json_fields(result["fraud"], ["full_result", "flags"])
    if result.get("advisory"):
        _parse_json_fields(result["advisory"], ["full_result", "action_items"])
    return result


@app.get("/api/claims/")
async def list_claims(limit: int = 100, status: Optional[str] = None, clinic: Optional[str] = None):
    claims = db.list_claims(limit=limit, status=status, clinic=clinic)
    for c in claims:
        _parse_json_fields(c, ["extracted_data"])
    return {"claims": claims, "total": len(claims)}


@app.post("/api/claims/{claim_id}/appeal")
async def submit_appeal(claim_id: int, body: AppealSubmission, _: None = Depends(_require_operator_role)):
    """Submit an appeal and get GLM-drafted rebuttal."""
    claim = db.get_full_claim(claim_id)
    if not claim:
        raise HTTPException(404, f"Claim {claim_id} not found")
    if claim.get("status") not in ("DENIED", "REFERRED"):
        raise HTTPException(400, "Can only appeal DENIED or REFERRED claims")

    denial = claim.get("decision") or {}
    claim_data = claim.get("extracted_data") or {}
    if isinstance(claim_data, str):
        try:
            claim_data = json.loads(claim_data)
        except Exception:
            claim_data = {}

    try:
        rebuttal = glm_client.draft_appeal_rebuttal(denial, claim_data, body.appeal_reason)
        appeal_id = db.insert_appeal(
            claim_id,
            reason=body.appeal_reason,
            evidence=body.supporting_evidence or "",
            rebuttal=rebuttal.get("rebuttal_body", ""),
            rebuttal_bm=rebuttal.get("rebuttal_body_bm", ""),
        )
        return {"appeal_id": appeal_id, "rebuttal": rebuttal}
    except Exception as e:
        raise HTTPException(500, f"Appeal processing failed: {e}")


@app.post("/api/claims/{claim_id}/chat")
async def claim_chat(claim_id: int, body: ChatQuestion, _: None = Depends(_require_operator_role)):
    """Ask GLM a question about a specific claim."""
    claim = db.get_full_claim(claim_id)
    if not claim:
        raise HTTPException(404, f"Claim {claim_id} not found")

    # Build a clean context dict for GLM
    ctx = {
        "claim_id": claim_id,
        "patient": claim.get("patient_name"),
        "clinic": claim.get("clinic_name"),
        "diagnosis": claim.get("diagnosis"),
        "amount_myr": claim.get("total_amount_myr"),
        "status": claim.get("status"),
        "visit_date": claim.get("visit_date"),
        "extracted_data": claim.get("extracted_data"),
        "raw_text_evidence": claim.get("raw_text_evidence"),
    }
    if claim.get("decision"):
        d = claim["decision"]
        ctx["decision"] = {
            "result": d.get("decision"),
            "confidence": d.get("confidence"),
            "reasoning": d.get("reasoning"),
            "approved_myr": d.get("amount_approved_myr"),
            "denied_myr": d.get("amount_denied_myr"),
            "denial_code": d.get("denial_reason_code"),
        }
    if claim.get("fraud"):
        ctx["fraud"] = {
            "risk_score": claim["fraud"].get("risk_score"),
            "risk_level": claim["fraud"].get("risk_level"),
            "recommendation": claim["fraud"].get("recommendation"),
        }

    if claim.get("parsed_evidence"):
        try:
            ctx["parsed_evidence"] = json.loads(claim["parsed_evidence"]) if isinstance(claim["parsed_evidence"], str) else claim["parsed_evidence"]
        except Exception:
            ctx["parsed_evidence"] = claim["parsed_evidence"]

    if claim.get("cross_ref_result"):
        try:
            ctx["cross_ref_result"] = json.loads(claim["cross_ref_result"]) if isinstance(claim["cross_ref_result"], str) else claim["cross_ref_result"]
        except Exception:
            ctx["cross_ref_result"] = claim["cross_ref_result"]
            
    if claim.get("raw_text"):
        ctx["raw_evidence_packet"] = claim["raw_text"]

    try:
        answer = glm_client.answer_claim_question(body.question, ctx)
        return answer
    except Exception as e:
        raise HTTPException(500, f"Chat failed: {e}")


# ── Analytics ───────────────────────────────────────────────

@app.get("/api/analytics/summary")
async def analytics_summary():
    return db.get_analytics_summary()


@app.get("/api/analytics/kpis")
async def analytics_kpis():
    summary = db.get_analytics_summary()
    return summary.get("kpis", {})


@app.get("/api/analytics/clinics")
async def analytics_clinics():
    return {"clinics": db.get_clinic_analytics()}


@app.get("/api/analytics/denials")
async def analytics_denials():
    return {"breakdown": db.get_denial_breakdown()}


@app.get("/api/analytics/fraud-heatmap")
async def fraud_heatmap():
    conn = db.get_db()
    rows = conn.execute(
        "SELECT f.risk_level, f.risk_score, c.diagnosis, c.total_amount_myr, c.clinic_name, c.id as claim_id "
        "FROM fraud_scores f JOIN claims c ON f.claim_id = c.id"
    ).fetchall()
    conn.close()
    return {"heatmap_data": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/analytics/gp-performance")
async def gp_performance():
    return {"clinics": db.get_clinic_analytics()}


@app.get("/api/analytics/weekly-report")
async def weekly_report():
    """GLM generates a narrative weekly intelligence report."""
    try:
        analytics = db.get_analytics_summary()
        clinic_data = db.get_clinic_analytics()
        analytics["top_clinics"] = clinic_data[:5]
        report = glm_client.generate_weekly_report(analytics)
        return report
    except Exception as e:
        raise HTTPException(500, f"Weekly report failed: {e}")


# ── Demo ────────────────────────────────────────────────────

@app.post("/api/demo/generate")
async def demo_generate(body: DemoGenerate):
    if (os.getenv("APP_ENV") or "dev").lower() in ("prod", "production"):
        raise HTTPException(403, "DEMO_ENDPOINT_DISABLED_IN_PRODUCTION")
    from generate_synthetic_data import generate
    claims = generate(body.count)
    for claim in claims:
        raw = f"Patient: {claim['patient_name']}\nIC: {claim['patient_ic']}\nDate: {claim['visit_date']}\nClinic: {claim['clinic_name']}\nDiagnosis: {claim['diagnosis']}\nTotal: RM {claim['total_amount_myr']}"
        db.insert_claim(raw, extracted=claim)
    return {"generated": len(claims)}


@app.post("/api/demo/seed")
async def demo_seed():
    if (os.getenv("APP_ENV") or "dev").lower() in ("prod", "production"):
        raise HTTPException(403, "DEMO_ENDPOINT_DISABLED_IN_PRODUCTION")
    import random
    from generate_synthetic_data import generate
    DENIAL_CODES = [
        ("45", "Charge exceeds fee schedule/maximum allowable"),
        ("97", "Claim/service denied — not covered by benefit plan"),
        ("4", "Service/drug/supply is not covered"),
        ("18", "Duplicate claim/service"),
        ("16", "Claim/service lacks information"),
        ("29", "Filing deadline exceeded (>14 days)"),
    ]
    claims = generate(60)
    seeded = 0
    for claim in claims:
        raw = f"Patient: {claim['patient_name']}\nDiagnosis: {claim['diagnosis']}\nTotal: RM {claim['total_amount_myr']}"
        claim_id = db.insert_claim(raw, extracted=claim)
        decisions_pool = ["APPROVED", "APPROVED", "APPROVED", "APPROVED", "DENIED", "REFERRED"]
        decision = random.choice(decisions_pool)
        amt = claim.get("total_amount_myr", 0)
        carc, carc_desc = random.choice(DENIAL_CODES) if decision == "DENIED" else (None, None)
        db.insert_decision(claim_id, {
            "decision": decision, "confidence": round(random.uniform(0.72, 0.98), 2),
            "reasoning": f"Claim for {claim['diagnosis']} assessed against PMCare policy guidelines. "
                         f"{'Coverage confirmed within benefit limits.' if decision == 'APPROVED' else 'Claim does not meet coverage criteria.'}",
            "amount_approved_myr": amt if decision == "APPROVED" else 0,
            "amount_denied_myr": amt if decision == "DENIED" else 0,
            "patient_responsibility_myr": claim.get("consultation_fee_myr", 10) if decision == "APPROVED" else 0,
            "denial_reason_code": carc, "denial_reason_description": carc_desc,
            "is_auto_adjudicated": 1,
        })
        is_sus = claim.get("is_suspicious", False)
        risk = round(random.uniform(0.55, 0.92), 2) if is_sus else round(random.uniform(0.02, 0.35), 2)
        level = "HIGH" if risk > 0.7 else ("MEDIUM" if risk > 0.4 else "LOW")
        db.insert_fraud_score(claim_id, {
            "fraud_risk_score": risk, "risk_level": level,
            "flags": [{"flag_type": "EXCESSIVE_AMOUNT", "description": "Billed amount exceeds peer benchmark by >80%",
                       "severity": risk, "evidence": f"RM {amt:.2f} vs benchmark RM {amt*0.55:.2f}"}] if is_sus else [],
            "recommendation": "INVESTIGATE" if is_sus else "PROCEED",
        })
        db.insert_advisory(claim_id, {
            "summary": f"Your claim for {claim['diagnosis']} (RM {amt:.2f}) has been {decision.lower()}.",
            "summary_bm": f"Tuntutan anda untuk {claim['diagnosis']} (RM {amt:.2f}) telah {'diluluskan' if decision=='APPROVED' else 'ditolak'}.",
            "action_items": [{"action": "No further action needed" if decision == "APPROVED" else "Review denial code and consider appeal", "priority": "LOW" if decision == "APPROVED" else "HIGH", "deadline": "Within 30 days"}],
        })
        db.update_claim(claim_id, status=decision, auto_adjudicated=1,
                        clean_claim_flag=1 if decision == "APPROVED" else 0,
                        fraud_flagged=1 if is_sus else 0,
                        ar_days=round(random.uniform(1, 45), 1),
                        cycle_time_hours=round(random.uniform(0.1, 72), 1))
        seeded += 1
    return {"seeded": seeded, "message": f"Seeded {seeded} fully-processed demo claims"}


# ── Health ──────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "ClaimIQ", "version": "2.0", "engine": "Z.AI GLM"}


# ── Static files ────────────────────────────────────────────

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
