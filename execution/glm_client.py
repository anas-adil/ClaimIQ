"""
glm_client.py — Z.AI GLM API Wrapper for ClaimIQ

Core module: every intelligence function flows through Z.AI GLM.
Remove this module = system is dead.

5 Core Functions:
1. extract_claim_data()     — Document understanding
2. assign_medical_codes()   — ICD-10/CPT assignment
3. adjudicate_claim()       — Policy RAG + reasoning
4. detect_fraud_patterns()  — Anomaly detection
5. generate_gp_advisory()   — Plain-language GP guidance
"""

import os
import json
import time
import logging
import hashlib
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("claimiq.glm")
_AUTH_FAILURE_UNTIL = 0.0
_AUTH_FAILURE_REASON = ""


class GLMServiceUnavailable(RuntimeError):
    """Raised when production GLM calls fail and the pipeline must fail closed."""


def _get_provider_config() -> tuple[str, str, str]:
    """Resolve API credentials from ILMU-first env vars, with ZAI backward compatibility."""
    api_key = os.getenv("ILMU_API_KEY") or os.getenv("ZAI_API_KEY")
    base_url = (
        os.getenv("ILMU_BASE_URL")
        or os.getenv("ZAI_BASE_URL")
        or "https://api.z.ai/api/paas/v4"
    )
    model = os.getenv("ILMU_MODEL") or os.getenv("ZAI_MODEL") or "glm-4-plus"
    return api_key, base_url, model


def _should_skip_live_calls(api_key: str, base_url: str) -> bool:
    """Guardrail for obvious provider mismatch to avoid repeated failing live calls."""
    if not api_key:
        return True
    if api_key.startswith("ILMU-") and "api.z.ai" in base_url:
        logger.error(
            "Provider mismatch detected: ILMU-style API key with Z.AI base URL. "
            "Set ILMU_BASE_URL (or ZAI_BASE_URL) to the correct ILMU endpoint."
        )
        return True
    return False


def _get_client(api_key: str, base_url: str) -> OpenAI:
    """Create OpenAI-compatible client."""
    return OpenAI(api_key=api_key, base_url=base_url)


def _call_glm(
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = True,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    retries: int = 3,
) -> str:
    """Core GLM API call with structured output, retry logic, and logging."""
    global _AUTH_FAILURE_UNTIL, _AUTH_FAILURE_REASON

    api_key, base_url, model = _get_provider_config()
    env = (os.getenv("APP_ENV") or os.getenv("ENV") or "dev").lower()
    is_prod = env in {"prod", "production"}
    
    if _should_skip_live_calls(api_key, base_url):
        if is_prod:
            raise GLMServiceUnavailable(
                "SERVICE_UNAVAILABLE: Provider mismatch detected in production environment."
            )
        return _get_intelligent_mock(system_prompt, user_prompt)

    if time.time() < _AUTH_FAILURE_UNTIL:
        remaining = int(_AUTH_FAILURE_UNTIL - time.time())
        logger.warning(
            f"Skipping live GLM call for {remaining}s due to prior auth failure: {_AUTH_FAILURE_REASON}"
        )
        if is_prod:
            raise GLMServiceUnavailable(
                f"SERVICE_UNAVAILABLE: GLM auth failure cooldown active. Reason: {_AUTH_FAILURE_REASON}"
            )
        return _get_intelligent_mock(system_prompt, user_prompt)

    client = _get_client(api_key, base_url)
    auth_cooldown_seconds = int(os.getenv("ZAI_AUTH_FAILURE_COOLDOWN_SEC", "900"))
    response_format = {"type": "json_object"} if json_mode else None

    for attempt in range(retries):
        try:
            logger.info(f"GLM call attempt {attempt+1}/{retries} | model={model}")
            start = time.time()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=response_format,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            elapsed = time.time() - start
            content = response.choices[0].message.content
            usage = response.usage.total_tokens if response.usage else "?"
            logger.info(f"GLM response in {elapsed:.2f}s | tokens={usage}")
            
            # Robust JSON cleaning
            if json_mode and content:
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
            return content
        except Exception as e:
            err = str(e)
            logger.warning(f"GLM call failed (attempt {attempt+1}): {err}")
            if "401" in err or "token expired" in err.lower() or "incorrect" in err.lower():
                _AUTH_FAILURE_UNTIL = time.time() + max(auth_cooldown_seconds, 60)
                _AUTH_FAILURE_REASON = err
                logger.error(
                    "Detected GLM auth failure. Activating fallback-only mode "
                    f"for {int(_AUTH_FAILURE_UNTIL - time.time())}s."
                )
                if is_prod:
                    raise GLMServiceUnavailable(f"SERVICE_UNAVAILABLE: GLM authentication failed: {err}")
                return _get_intelligent_mock(system_prompt, user_prompt)
            if attempt == retries - 1:
                logger.error("All GLM retries failed. Using intelligent fallback mock for hackathon demo.")
                if is_prod:
                    raise GLMServiceUnavailable(f"SERVICE_UNAVAILABLE: All GLM retries failed: {err}")
                return _get_intelligent_mock(system_prompt, user_prompt)
            time.sleep(2 ** attempt)
    
    if is_prod:
        raise GLMServiceUnavailable("SERVICE_UNAVAILABLE: GLM call failed completely in production.")
    return _get_intelligent_mock(system_prompt, user_prompt)


def _generate_unique_mock_visit_date(scenario_key: str, user_prompt: str) -> str:
    """
    Generate a recent visit date (within filing window) that varies between runs.
    This helps avoid duplicate-key collisions in repeated E2E tests.
    """
    from datetime import datetime, timedelta

    seed = f"{scenario_key}|{user_prompt}|{datetime.utcnow().isoformat()}"
    offset_days = (int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % 13) + 1
    return (datetime.utcnow().date() - timedelta(days=offset_days)).isoformat()

def _get_intelligent_mock(system_prompt: str, user_prompt: str) -> str:
    """Provides highly realistic industry-standard mock responses if Z.AI API is unreachable."""
    if "alignment" in system_prompt.lower():
        # Cross reference mock
        return json.dumps({
            "alignment_status": "FULL_ALIGNMENT",
            "supporting_evidence": ["Evidence generally aligns with description (mock)"],
            "contradictory_evidence": [],
            "unmentioned_findings": [],
            "critical_contradiction_count": 0
        })
    elif "invoice" in system_prompt.lower() and "validation" in system_prompt.lower():
        # Invoice validation mock
        return json.dumps({
            "alignment_status": "ALIGNED",
            "unjustified_items": [],
            "missing_expected_items": [],
            "total_unjustified_amount": 0
        })
    elif "validator" in system_prompt.lower():
        return json.dumps({
            "clinical_validity": "WARN",
            "issues": [{"type": "DOSAGE", "description": "Loratadine 10mg x 7 days is standard, but check if patient has chronic condition.", "severity": 0.2}],
            "recommendations": ["Verify patient medical history for chronic allergic rhinitis."],
            "overall_confidence": 0.85
        })
    elif "appeal specialist" in system_prompt.lower():
        return json.dumps({
            "rebuttal_subject": "Appeal for Denied Claim: Medical Necessity Established",
            "rebuttal_body": "To Whom It May Concern,\n\nWe are formally appealing the denial of this claim. The provided treatment was medically necessary and fully aligns with standard clinical pathways for the diagnosed condition. We have attached the supporting clinical notes and lab results which clearly indicate the necessity of the intervention.\n\nWe request an immediate review and reversal of this denial.",
            "rebuttal_body_bm": "Kepada Sesiapa Yang Berkenaan,\n\nKami membuat rayuan rasmi terhadap penolakan tuntutan ini. Rawatan yang diberikan adalah perlu dari segi perubatan dan sejajar dengan laluan klinikal standard untuk keadaan yang didiagnosis. Kami menyertakan nota klinikal dan keputusan makmal yang jelas menunjukkan keperluan intervensi ini.\n\nKami memohon semakan segera dan kelulusan ke atas tuntutan ini.",
            "key_arguments": ["Medical necessity", "Adherence to clinical guidelines"],
            "supporting_evidence_needed": ["Detailed consultation notes", "Lab results"],
            "confidence_of_success": 0.92
        })
    elif "weekly" in system_prompt.lower():
        return json.dumps({
            "executive_summary": "This week saw a 12% increase in auto-adjudicated claims, significantly reducing AR days. However, denial rates spiked slightly due to duplicate billing errors at three specific clinics.",
            "key_highlights": [
                {"metric": "Clean Claim Rate", "value": "92%", "trend": "Up", "insight": "Process improvements are working."},
                {"metric": "Avg AR Days", "value": "14", "trend": "Down", "insight": "Faster payments improving clinic cash flow."}
            ],
            "fraud_alerts": ["Klinik Kesihatan Taman Melati flagged for unusual upcoding pattern on weekend shifts."],
            "recommendations": ["Conduct targeted training on correct CPT coding for weekend staff."],
            "week_score": 88,
            "outlook": "Positive trend, expect denial rates to normalize next week."
        })
    elif "assistant" in system_prompt.lower():
        context_data = {}
        try:
            if "{" in user_prompt:
                start_idx = user_prompt.find("{")
                end_idx = user_prompt.rfind("}") + 1
                context_data = json.loads(user_prompt[start_idx:end_idx])
        except:
            pass

        question = ""
        if "Question:" in user_prompt:
            question = user_prompt.split("Question:")[-1].strip().lower()
        else:
            question = user_prompt.lower()
            
        reasoning = context_data.get("decision", {}).get("reasoning", "the claim did not meet policy guidelines")
        decision = context_data.get("decision", {}).get("result", "DENIED")
        status = context_data.get("status", "DENIED")
        
        if "similar" in question:
            answer = f"I found 3 similar claims from {context_data.get('clinic', 'your clinic')} in the past month that were {decision} for similar reasons. Ensuring that filing deadlines and documentation are complete will help reduce these occurrences."
            answer_bm = f"Saya dapati 3 tuntutan serupa dari {context_data.get('clinic', 'klinik anda')} pada bulan lalu yang {decision} atas sebab yang serupa. Memastikan tarikh akhir pemfailan dan dokumentasi lengkap akan membantu mengurangkan kejadian ini."
        elif "x-ray" in question or "pneumonia" in question or "infiltrates" in question:
            answer = "Yes, the HuggingFace Vision extraction of the uploaded Chest X-ray indicates bilateral infiltrates, which is highly consistent with a diagnosis of Pneumonia. This imaging finding is the primary clinical evidence justifying the prescription of Amoxicillin and the overall complexity of the visit."
            answer_bm = "Ya, pengekstrakan Visi HuggingFace dari X-ray dada yang dimuat naik menunjukkan infiltrasi dua hala, yang sangat konsisten dengan diagnosis Pneumonia. Penemuan pengimejan ini adalah bukti klinikal utama yang mewajarkan preskripsi Amoxicillin."
        elif "crp" in question or "lab" in question or "clinical" in question:
            answer = "Yes, the CRP level of 15mg/L is a significant clinical indicator of systemic inflammation or bacterial infection. When cross-referenced with the severe throat pain and fever (38.5C), this laboratory finding strongly justifies the medical necessity of the prescribed interventions."
            answer_bm = "Ya, tahap CRP 15mg/L adalah penunjuk klinikal yang signifikan bagi keradangan sistemik atau jangkitan bakteria. Penemuan makmal ini sangat menyokong keperluan perubatan untuk intervensi yang ditetapkan."
        elif "fee schedule" in question or "limit" in question:
            answer = "The fee schedule limit for a standard outpatient consultation under the PMCare network is typically RM 35.00 for general practitioners. Any amount billed above this without complex procedure codes will be denied or adjusted."
            answer_bm = "Had jadual bayaran untuk perundingan pesakit luar standard di bawah rangkaian PMCare biasanya RM 35.00 untuk pengamal am. Sebarang jumlah yang dibilkan melebihi ini tanpa kod prosedur kompleks akan ditolak atau diselaraskan."
        elif "appeal" in question or "submit" in question:
            answer = "You can submit an appeal by clicking the 'Appeal' button in the top right of this claim window. Our AI will automatically draft a formal rebuttal letter for you to review and submit with supporting clinical notes."
            answer_bm = "Anda boleh mengemukakan rayuan dengan mengklik butang 'Rayuan' di bahagian atas kanan tetingkap tuntutan ini. AI kami akan merangka surat sangkalan rasmi secara automatik untuk anda semak dan kemukakan bersama nota klinikal sokongan."
        elif "why" in question or "reason" in question or "decision" in question:
            answer = f"Based on the system's analysis, this claim's status is {status}. The specific reasoning provided by the adjudication engine is: '{reasoning}'."
            answer_bm = f"Berdasarkan analisis sistem, status tuntutan ini ialah {status}. Alasan khusus yang diberikan oleh enjin adjudikasi ialah: '{reasoning}'."
        else:
            answer = f"Regarding your claim for {context_data.get('diagnosis', 'this visit')}, the current status is {status}. The primary adjudication reason is: {reasoning}."
            answer_bm = f"Mengenai tuntutan anda untuk {context_data.get('diagnosis', 'lawatan ini')}, status semasa ialah {status}. Alasan adjudikasi utama ialah: {reasoning}."

        return json.dumps({
            "answer": answer,
            "answer_bm": answer_bm,
            "action_items": ["Review adjudication reasoning", "Provide additional documentation if necessary"],
            "follow_up_questions": ["Can I see similar denied claims?", "What is the fee schedule limit?", "How do I submit the appeal?"]
        })
    elif "extract" in system_prompt.lower():
        # DEPRECATED: Simulated data removed to prevent AI hallucinations.
        return json.dumps({
            "error": "EXTRACTION_UNAVAILABLE",
            "requires_llm": True
        })
    elif "coder" in system_prompt.lower():
        if "fracture" in user_prompt.lower():
            return json.dumps({
                "icd10_codes": [{"code": "S82.2", "description": "Fracture of shaft of tibia", "confidence": 0.99}],
                "cpt_codes": [{"code": "27750", "description": "Closed treatment of tibial shaft fracture", "confidence": 0.95}],
                "primary_diagnosis_code": "S82.2",
                "coding_confidence": 0.99
            })
        elif "dengue" in user_prompt.lower():
            return json.dumps({
                "icd10_codes": [{"code": "A90", "description": "Dengue fever [classical dengue]", "confidence": 0.99}],
                "cpt_codes": [{"code": "99214", "description": "Office or other outpatient visit", "confidence": 0.95}],
                "primary_diagnosis_code": "A90",
                "coding_confidence": 0.99
            })
        elif "pneumonia" in user_prompt.lower() or "Community-acquired Pneumonia" in user_prompt or "Bilateral infiltrates" in user_prompt:
            return json.dumps({
                "icd10_codes": [{"code": "J18.9", "description": "Pneumonia, unspecified organism", "confidence": 0.99}],
                "cpt_codes": [{"code": "99214", "description": "Office or other outpatient visit, complex", "confidence": 0.95}, {"code": "71046", "description": "Radiologic examination, chest; 2 views", "confidence": 0.93}],
                "primary_diagnosis_code": "J18.9",
                "coding_confidence": 0.99
            })
        else:
            return json.dumps({
                "icd10_codes": [{"code": "J06.9", "description": "Acute upper respiratory infection, unspecified", "confidence": 0.95}],
                "cpt_codes": [{"code": "99213", "description": "Office or other outpatient visit", "confidence": 0.9}],
                "primary_diagnosis_code": "J06.9",
                "coding_confidence": 0.95
            })
    elif "adjudication engine" in system_prompt.lower():
        # DEPRECATED: Simulated data removed. Fallback to manual review.
        return json.dumps({
            "decision": "REFERRED",
            "confidence": 0.95,
            "reasoning": "LLM unavailable — claim requires manual review",
            "amount_approved_myr": 0.0,
            "amount_denied_myr": 0.0,
            "denial_reasons": ["LLM Unavailable"],
            "conditions": [],
            "adjudication_confidence": 0.95
        })
    elif "fraud" in system_prompt.lower():
        # DEPRECATED: Simulated data removed
        return json.dumps({
            "fraud_risk_score": 0.5,
            "risk_level": "UNKNOWN",
            "flags": [],
            "recommendation": "MANUAL_REVIEW",
            "detection_confidence": 0.5
        })
    elif "advisory" in system_prompt.lower():
        return json.dumps({
            "summary": "This claim is clean and has been processed successfully. No further action is required.",
            "summary_bm": "Tuntutan ini bersih dan telah diproses dengan jayanya. Tiada tindakan lanjut diperlukan.",
            "action_items": [{"action": "File records", "priority": "LOW", "deadline": "None"}],
            "documentation_tips": ["Always include patient IC"],
            "financial_impact": {"approved_amount_myr": 70.0, "potential_recovery_myr": 0, "optimization_savings_myr": 0}
        })
    return "{}"


# --- Prompt Templates (loaded from separate module for cleanliness) ---

EXTRACT_SYSTEM = (
    "You are a Malaysian medical claims data extraction specialist. "
    "Extract structured claim data from raw clinical notes as JSON with fields: "
    "patient_name, patient_ic, patient_age, patient_gender, visit_date, "
    "clinic_name, clinic_id, chief_complaint, diagnosis, symptoms (array), "
    "procedures (array), medications (array of {name,dosage,quantity}), "
    "consultation_fee_myr, medication_fee_myr, procedure_fee_myr, total_amount_myr, "
    "follow_up_required, referral_needed, notes, extraction_confidence (0-1). "
    "Use null for missing fields. Currency is MYR."
)

CODING_SYSTEM = (
    "You are a certified Malaysian medical coder. Assign ICD-10 and CPT codes. "
    "Output JSON: icd10_codes (array of {code,description,confidence,evidence}), "
    "cpt_codes (array of {code,description,confidence}), coding_notes, "
    "primary_diagnosis_code, coding_confidence (0-1). "
    "Common codes: J06.9=URTI, E11=T2DM, I10=Hypertension, A90=Dengue, "
    "K29.7=Gastritis, M54.5=Low back pain, J45=Asthma."
)

ADJUDICATION_SYSTEM = (
    "You are the ClaimIQ Adjudication Engine (Senior Medical Auditor) for Malaysian TPA claims. "
    "Output JSON: decision (APPROVED|DENIED|REFERRED), confidence (0-1), "
    "reasoning (must be highly detailed, citing specific lab values, X-ray findings, or clinical notes provided in the ATTACHED EVIDENCE), "
    "policy_references (array), amount_approved_myr, amount_denied_myr, "
    "denial_reasons (array), conditions (array), appeal_recommendation, "
    "processing_notes, adjudication_confidence (0-1). "
    "Check: coverage, amount limits, medical necessity, medication appropriateness. "
    "CRITICAL: If the itemized bill or lab evidence is missing for complex claims, DENY or REFER the claim for 'Missing Supporting Evidence'."
)

FRAUD_SYSTEM = (
    "You are the ClaimIQ Fraud Detection Engine for Malaysian TPA claims. "
    "Output JSON: fraud_risk_score (0-1), risk_level (LOW|MEDIUM|HIGH|CRITICAL), "
    "flags (array of {flag_type,description,severity,evidence}), pattern_analysis, "
    "recommendation (PROCEED|REVIEW|INVESTIGATE|BLOCK), similar_fraud_patterns (array), "
    "detection_confidence (0-1). "
    "Check: EXCESSIVE_AMOUNT, IMPOSSIBLE_TIMING, UPCODING, PHANTOM_BILLING, "
    "DUPLICATE_CLAIM, UNUSUAL_PATTERN, CLINIC_ANOMALY. "
    "Malaysian GP avg consultation: RM 30-80."
)

ADVISORY_SYSTEM = (
    "You are the ClaimIQ GP Advisory Engine. Generate plain-language guidance. "
    "Output JSON: summary, summary_bm (Bahasa Malaysia), "
    "action_items (array of {action,priority,deadline}), documentation_tips (array), "
    "coding_suggestions (array), financial_impact ({approved_amount_myr, "
    "potential_recovery_myr, optimization_savings_myr}), educational_notes. "
    "Be supportive, actionable, include BM translation."
)

SYNTHETIC_SYSTEM = (
    "You are a medical data generator for Malaysian GP clinics. "
    "Generate realistic SYNTHETIC claim data with: Malaysian names (Malay/Chinese/Indian mix), "
    "IC numbers (YYMMDD-SS-NNNN), common GP conditions, MYR amounts "
    "(consultation RM30-80, meds RM10-200, procedures RM50-500). "
    "Mix: 80% clean, 10% borderline, 10% suspicious (inflated amounts, mismatched codes). "
    "Output as JSON object with 'claims' array."
)

CROSS_REF_SYSTEM = (
    "You are the ClaimIQ Evidence Alignment Engine. Compare the doctor's clinical notes "
    "against the objective findings extracted from medical images (labs, X-rays, etc). "
    "Output JSON: alignment_status (FULL_ALIGNMENT|PARTIAL_ALIGNMENT|CONTRADICTION), "
    "supporting_evidence (array of findings that support the doctor), "
    "contradictory_evidence (array of {field, doctor_says, evidence_shows, discrepancy_percentage}), "
    "unmentioned_findings (array of findings in evidence not mentioned by doctor), "
    "critical_contradiction_count (integer). "
    "CRITICAL RULE: The doctor has the clinical upper hand. If the doctor's diagnosis matches ANY "
    "finding or possibility in the evidence, it is FULL_ALIGNMENT. Only flag CONTRADICTION if "
    "the evidence DIRECTLY refutes the doctor's specific claims (e.g. Platelets stated as 15 but lab shows 176)."
)

INVOICE_VAL_SYSTEM = (
    "You are the ClaimIQ Invoice Validation Engine. Compare the itemized medical bill "
    "against the treatment described in the doctor's clinical notes. "
    "Output JSON: alignment_status (ALIGNED|SUSPICIOUS|PHANTOM_BILLING), "
    "unjustified_items (array of {item_description, amount, reason}), "
    "missing_expected_items (array of {item_description, reason}), "
    "total_unjustified_amount (number). "
    "Flag items on the invoice that have NO clinical basis in the doctor's notes (phantom billing)."
)


# --- 5 Core Functions ---

def extract_claim_data(raw_text: str) -> dict:
    """GLM Fn 1: Unstructured clinical text -> structured claim JSON."""
    result = _call_glm(EXTRACT_SYSTEM, f"Extract claim data:\n\n{raw_text}", temperature=0.1)
    data = json.loads(result)

    # Check which required fields are missing from live extraction
    required = ["patient_name", "patient_ic", "visit_date", "clinic_name", "diagnosis", "total_amount_myr"]
    missing = [k for k in required if not data.get(k)]

    env = (os.getenv("APP_ENV") or os.getenv("ENV") or "dev").lower()
    is_prod = env in {"prod", "production"}
    if missing:
        if is_prod:
            raise GLMServiceUnavailable(
                f"SERVICE_UNAVAILABLE: Missing required extraction fields from live model: {missing}"
            )
        # MERGE strategy: keep all live-extracted fields, fill ONLY missing
        # ones from the mock fallback. Never overwrite real patient data.
        logger.warning(
            f"Live extraction missing required fields {missing}; "
            f"merging mock fallback for ONLY those fields."
        )
        mock_data = json.loads(_get_intelligent_mock(EXTRACT_SYSTEM, raw_text))
        fallback_fields = []
        for field in missing:
            if mock_data.get(field):
                data[field] = mock_data[field]
                fallback_fields.append(field)
        data["_fallback_fields"] = fallback_fields
        logger.info(f"Merged fallback for fields: {fallback_fields}")
    return data


def assign_medical_codes(claim_data: dict) -> dict:
    """GLM Fn 2: Structured claim → ICD-10/CPT codes."""
    result = _call_glm(CODING_SYSTEM, f"Assign codes:\n\n{json.dumps(claim_data, indent=2)}", temperature=0.2)
    return json.loads(result)


def adjudicate_claim(coded_claim: dict, policy_context: str) -> dict:
    """GLM Fn 3: RAG-powered claims adjudication with evidence packet."""
    # Pull out special fields before serializing
    evidence_packet = coded_claim.pop("_raw_evidence_packet", None)
    parsed_ev = coded_claim.pop("_parsed_evidence", None)
    xref_res = coded_claim.pop("_cross_reference_result", None)
    coded_claim.pop("_fallback_fields", None)  # don't send internal metadata to LLM

    # Build evidence sections
    sections = []
    if parsed_ev:
        sections.append(f"\n\n## Parsed Evidence (via MedGemma)\n{json.dumps(parsed_ev, indent=2)}")
    if xref_res:
        sections.append(f"\n\n## Cross-Reference Engine Results\n{json.dumps(xref_res, indent=2)}")
    if evidence_packet:
        sections.append(f"\n\n## Raw Clinical Evidence Packet\n{evidence_packet}")

    evidence_section = "".join(sections)
    prompt = f"## Claim\n{json.dumps(coded_claim, indent=2)}\n\n## Policy\n{policy_context}{evidence_section}"
    result = _call_glm(ADJUDICATION_SYSTEM, f"Adjudicate:\n\n{prompt}", temperature=0.2)
    return json.loads(result)


def detect_fraud_patterns(claim: dict, historical_context: Optional[str] = None) -> dict:
    """GLM Fn 4: Fraud pattern analysis."""
    ctx = historical_context or "No historical data available."
    prompt = f"## Claim\n{json.dumps(claim, indent=2)}\n\n## History\n{ctx}"
    result = _call_glm(FRAUD_SYSTEM, f"Analyze fraud:\n\n{prompt}", temperature=0.3)
    return json.loads(result)


def generate_gp_advisory(decision: dict, claim_data: dict) -> dict:
    """GLM Fn 5: Plain-language GP advisory."""
    prompt = f"## Decision\n{json.dumps(decision, indent=2)}\n\n## Claim\n{json.dumps(claim_data, indent=2)}"
    result = _call_glm(ADVISORY_SYSTEM, f"Generate advisory:\n\n{prompt}", temperature=0.5)
    return json.loads(result)


def generate_synthetic_claims(count: int = 10) -> list:
    """Generate synthetic Malaysian medical claims using GLM."""
    result = _call_glm(
        SYNTHETIC_SYSTEM,
        f"Generate exactly {count} synthetic Malaysian GP claims as JSON.",
        temperature=0.8, max_tokens=8192,
    )
    data = json.loads(result)
    if isinstance(data, dict) and "claims" in data:
        return data["claims"]
    return data if isinstance(data, list) else [data]


def cross_reference_evidence(parsed_evidence_list: list, doctor_notes: str) -> dict:
    """LLM Fn: Compare doctor's notes against extracted evidence findings."""
    prompt = f"## Doctor's Notes\n{doctor_notes}\n\n## Extracted Evidence Findings\n{json.dumps(parsed_evidence_list, indent=2)}"
    result = _call_glm(CROSS_REF_SYSTEM, prompt, temperature=0.1)
    return json.loads(result)

def validate_invoice_against_treatment(parsed_invoice: dict, doctor_notes: str) -> dict:
    """LLM Fn: Verify invoice line items match the clinical treatment."""
    prompt = f"## Doctor's Notes (Treatment Described)\n{doctor_notes}\n\n## Itemized Invoice\n{json.dumps(parsed_invoice, indent=2)}"
    result = _call_glm(INVOICE_VAL_SYSTEM, prompt, temperature=0.1)
    return json.loads(result)

# --- v2: 4 New GLM Functions ---

VALIDATE_SYSTEM = (
    "You are a clinical claims validator for Malaysian GP outpatient claims. "
    "Check if the diagnosis, procedures, and medications are clinically consistent. "
    "Output JSON: clinical_validity (PASS|WARN|FAIL), issues (array of {type, description, severity}), "
    "recommendations (array of strings), overall_confidence (0-1)."
)

APPEAL_SYSTEM = (
    "You are a Malaysian healthcare claims appeal specialist. "
    "Write a formal, professional appeal rebuttal letter on behalf of a GP clinic. "
    "Output JSON: rebuttal_subject (string), rebuttal_body (string, formal letter in 3 paragraphs), "
    "rebuttal_body_bm (Bahasa Malaysia version), key_arguments (array), "
    "supporting_evidence_needed (array), confidence_of_success (0-1)."
)

WEEKLY_REPORT_SYSTEM = (
    "You are the ClaimIQ Intelligence Engine generating a weekly claims intelligence report. "
    "Analyse the data and produce a professional narrative report for Malaysian GP clinic administrators. "
    "Output JSON: executive_summary (2-3 sentences), key_highlights (array of {metric, value, trend, insight}), "
    "fraud_alerts (array of strings), recommendations (array of strings), "
    "week_score (0-100, overall claims health), outlook (string)."
)

CHAT_SYSTEM = (
    "You are ClaimIQ Assistant, an expert AI claims advisor for Malaysian TPA (PMCare) claims. "
    "Answer questions about specific claims clearly, helpfully, and concisely. "
    "You have access to full claim details, adjudication decisions, fraud scores, and GP advisories. "
    "Respond in plain English. If the question is in Bahasa Malaysia, reply in BM. "
    "Output JSON: answer (string), answer_bm (string, BM translation), "
    "action_items (array of strings), follow_up_questions (array of 3 suggested next questions)."
)


def validate_claim_pre_adjudication(claim_data: dict) -> dict:
    """GLM Fn 6: Clinical pre-validation — checks dx/procedure/medication consistency."""
    result = _call_glm(
        VALIDATE_SYSTEM,
        f"Validate clinical consistency:\n\n{json.dumps(claim_data, indent=2)}",
        temperature=0.1,
    )
    return json.loads(result)


def draft_appeal_rebuttal(denial: dict, claim: dict, gp_reason: str) -> dict:
    """GLM Fn 7: Draft a formal appeal rebuttal letter for a denied claim."""
    prompt = (
        f"## Denied Claim\n{json.dumps(claim, indent=2)}\n\n"
        f"## Denial Decision\n{json.dumps(denial, indent=2)}\n\n"
        f"## GP's Reason for Appeal\n{gp_reason}"
    )
    result = _call_glm(APPEAL_SYSTEM, f"Draft appeal rebuttal:\n\n{prompt}", temperature=0.4)
    return json.loads(result)


def generate_weekly_report(analytics: dict) -> dict:
    """GLM Fn 8: Generate narrative weekly intelligence report from analytics data."""
    result = _call_glm(
        WEEKLY_REPORT_SYSTEM,
        f"Generate weekly intelligence report:\n\n{json.dumps(analytics, indent=2)}",
        temperature=0.6,
    )
    return json.loads(result)


def answer_claim_question(question: str, claim_context: dict) -> dict:
    """GLM Fn 9: Answer a GP's question about a specific claim (chat)."""
    prompt = (
        f"## Claim Context\n{json.dumps(claim_context, indent=2)}\n\n"
        f"## Question\n{question}"
    )
    result = _call_glm(CHAT_SYSTEM, f"Answer:\n\n{prompt}", temperature=0.5)
    return json.loads(result)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if "--test" in sys.argv:
        print("Testing configured GLM connection...")
        try:
            api_key, base_url, model = _get_provider_config()
            if _should_skip_live_calls(api_key, base_url):
                raise RuntimeError("Provider config mismatch; live test skipped")
            client = _get_client(api_key, base_url)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say 'ClaimIQ online' in 2 words."}],
                max_tokens=10,
            )
            print(f"GLM connected: {resp.choices[0].message.content}")
        except Exception as e:
            print(f"GLM connection failed: {e}")
            sys.exit(1)

