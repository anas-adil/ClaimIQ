"""
build_policy_index.py — Generate synthetic PMCare-style policy documents and build FAISS index.

Creates realistic Malaysian TPA policy docs covering:
- General coverage rules
- Exclusions and waiting periods
- Fee schedules and limits
- Medication formulary
- Fraud prevention guidelines
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from rag_engine import build_index

# Synthetic PMCare-style policy documents
POLICY_DOCUMENTS = [
    {
        "id": "POL-001",
        "title": "General Outpatient Coverage",
        "category": "Coverage",
        "content": (
            "PMCare General Outpatient Benefit:\n"
            "1. Coverage includes consultation, examination, and treatment by panel GP.\n"
            "2. Consultation fee limit: RM 30 - RM 80 per visit depending on plan tier.\n"
            "3. Covered conditions include acute illnesses, minor injuries, and chronic disease management.\n"
            "4. Maximum 2 visits per day per member.\n"
            "5. Members must present valid membership card and NRIC at point of service.\n"
            "6. Claims must be submitted via Mediline within 14 days of service date."
        ),
    },
    {
        "id": "POL-002",
        "title": "Medication Coverage and Formulary",
        "category": "Medications",
        "content": (
            "Medication Benefit Rules:\n"
            "1. Medication limit per visit: RM 10 - RM 200 depending on plan tier.\n"
            "2. Generic medications preferred; branded requires prior authorization.\n"
            "3. Maximum 7-day supply for acute conditions, 30-day for chronic.\n"
            "4. Antibiotics require documented clinical indication.\n"
            "5. Controlled substances (Schedule 1-5) require additional documentation.\n"
            "6. Over-the-counter supplements and vitamins are excluded.\n"
            "7. Common covered medications: Paracetamol, Amoxicillin, Metformin, "
            "Amlodipine, Omeprazole, Cetirizine, Salbutamol inhaler."
        ),
    },
    {
        "id": "POL-003",
        "title": "Exclusions and Waiting Periods",
        "category": "Exclusions",
        "content": (
            "The following are NOT covered under outpatient benefits:\n"
            "1. Cosmetic procedures and treatments.\n"
            "2. Pre-existing conditions within first 120 days of coverage.\n"
            "3. Work-related injuries (covered under SOCSO/PERKESO).\n"
            "4. Self-inflicted injuries.\n"
            "5. Dental treatment (unless covered under separate dental rider).\n"
            "6. Traditional/alternative medicine (TCM, Ayurveda).\n"
            "7. Health screening and preventive care (unless employer-approved).\n"
            "8. Maternity-related outpatient visits (separate maternity benefit).\n"
            "9. Experimental or investigational treatments."
        ),
    },
    {
        "id": "POL-004",
        "title": "Procedure Coverage and Limits",
        "category": "Procedures",
        "content": (
            "Outpatient Procedure Benefits:\n"
            "1. Minor procedures covered: wound dressing, injection, nebulization, ECG.\n"
            "2. Procedure fee limit: RM 50 - RM 500 depending on complexity.\n"
            "3. Laboratory tests require clinical indication documented in notes.\n"
            "4. X-ray and imaging: covered at panel facility with referral.\n"
            "5. Minor surgical procedures (e.g., abscess drainage): covered with documentation.\n"
            "6. Physiotherapy: limited to 6 sessions per condition per year."
        ),
    },
    {
        "id": "POL-005",
        "title": "Chronic Disease Management",
        "category": "Coverage",
        "content": (
            "Chronic Disease Management Protocol:\n"
            "1. Covered chronic conditions: Diabetes (E11), Hypertension (I10), "
            "Asthma (J45), Dyslipidemia (E78), Gout (M10).\n"
            "2. Follow-up visits: monthly for unstable, quarterly for stable.\n"
            "3. Lab monitoring: HbA1c every 3 months, lipid panel every 6 months.\n"
            "4. Medication continuity: up to 30-day supply per visit.\n"
            "5. Annual complication screening is covered.\n"
            "6. Referral to specialist if targets not met after 6 months."
        ),
    },
    {
        "id": "POL-006",
        "title": "Fraud Prevention Guidelines",
        "category": "Fraud",
        "content": (
            "Claims Integrity Rules:\n"
            "1. Claims exceeding 150% of benchmark for diagnosis type will be queried.\n"
            "2. Multiple claims for same patient on same day require justification.\n"
            "3. Medication quantities must be clinically appropriate.\n"
            "4. Upcoding (using higher-severity ICD code than warranted) is prohibited.\n"
            "5. Phantom billing (billing for services not rendered) is grounds for panel termination.\n"
            "6. Clinics must respond to claim queries within 14 days.\n"
            "7. Pattern analysis: clinics with >20% deviation from peer benchmarks trigger audit.\n"
            "8. Benchmark consultation amounts by area: Urban RM 35-65, Rural RM 25-50."
        ),
    },
    {
        "id": "POL-007",
        "title": "Common Acute Conditions Coverage",
        "category": "Coverage",
        "content": (
            "Coverage for Common Acute Conditions:\n"
            "1. URTI (J06.9): Consultation + symptomatic medication. Limit RM 80 total.\n"
            "2. Gastritis (K29.7): Consultation + PPI/antacid. Limit RM 100 total.\n"
            "3. UTI (N39.0): Consultation + antibiotics + urinalysis. Limit RM 120 total.\n"
            "4. Dengue (A90): Consultation + FBC + supportive care. Limit RM 150 total.\n"
            "5. Acute gastroenteritis (A09): Consultation + ORS + meds. Limit RM 100 total.\n"
            "6. Dermatitis (L30.9): Consultation + topical treatment. Limit RM 90 total.\n"
            "7. Low back pain (M54.5): Consultation + analgesics + MC. Limit RM 100 total.\n"
            "8. Pneumonia (J18.9): Consultation + chest X-ray (PA and lateral) + FBC + CRP "
            "+ antibiotics (first-line: Amoxicillin/Augmentin, max 7-day acute supply, may "
            "extend to 14 days with documented clinical justification) + supportive care. "
            "Limit RM 300 total. Referral letter required for imaging.\n"
            "9. Fracture — limb (S82.x, S52.x, S42.x): Consultation + X-ray + casting/splinting "
            "+ analgesics. Limit RM 500 total. Imaging referral documentation required.\n"
            "10. Asthma exacerbation (J45): Consultation + nebulization + bronchodilator "
            "+ corticosteroid if severe. Limit RM 200 total."
        ),
    },
    {
        "id": "POL-008",
        "title": "Claims Submission Requirements",
        "category": "Process",
        "content": (
            "Claims Submission via Mediline:\n"
            "1. All claims must be submitted through Mediline system.\n"
            "2. Submission deadline: within 14 days of date of service.\n"
            "3. Late submissions will not be processed or paid.\n"
            "4. Required fields: member IC, diagnosis (ICD-10), procedures, medications, fees.\n"
            "5. Supporting documents for claims > RM 200 must be uploaded.\n"
            "6. Invoice listing must be signed and stamped monthly.\n"
            "7. Payment processing: within 60 days of complete claim receipt.\n"
            "8. Queried claims: 60-day clock starts after satisfactory response."
        ),
    },
]


def main():
    """Build the FAISS policy index from synthetic PMCare policy documents."""
    print(f"Building policy index from {len(POLICY_DOCUMENTS)} documents...")
    build_index(POLICY_DOCUMENTS)
    print("Policy index built successfully!")


if __name__ == "__main__":
    main()
