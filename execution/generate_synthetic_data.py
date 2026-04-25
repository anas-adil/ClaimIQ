"""
generate_synthetic_data.py — Generate 500 synthetic Malaysian GP claims

Uses Z.AI GLM to generate realistic claims in batches, then stores them in SQLite.
Falls back to deterministic generation if GLM is unavailable.
"""

import sys
import os
import json
import random
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

import database as db

logger = logging.getLogger("claimiq.synth")

# --- Deterministic fallback data pools ---
MALAY_NAMES = [
    "Ahmad bin Ibrahim", "Siti Nurhaliza binti Mohd", "Muhammad Farhan bin Aziz",
    "Nur Aisyah binti Rahman", "Mohd Hafiz bin Yusof", "Fatimah binti Abdullah",
    "Ismail bin Hassan", "Nurul Huda binti Omar", "Razak bin Kamal", "Aminah binti Sulaiman",
    "Zakaria bin Osman", "Mariam binti Idris", "Faizal bin Samad", "Zainab binti Wahab",
    "Hakim bin Noor", "Raihana binti Jalil", "Azman bin Latif", "Safiya binti Hamid",
]
CHINESE_MY_NAMES = [
    "Tan Wei Ming", "Lim Mei Ling", "Wong Kai Seng", "Lee Shu Fen",
    "Ng Chee Keong", "Ong Pei Shan", "Chan Yew Loong", "Goh Hui Lin",
    "Cheah Boon Huat", "Koh Siew Lan", "Yap Kok Wai", "Teo Li Ying",
]
INDIAN_MY_NAMES = [
    "Rajesh a/l Krishnan", "Priya a/p Subramaniam", "Kumar a/l Rajan",
    "Devi a/p Muthu", "Ganesh a/l Shanmugam", "Lakshmi a/p Naidu",
    "Arjun a/l Pillai", "Meena a/p Govindasamy", "Vikram a/l Sundaram",
]
ALL_NAMES = MALAY_NAMES + CHINESE_MY_NAMES + INDIAN_MY_NAMES
STATES = ["01","02","03","04","05","06","07","08","09","10","11","12","13","14"]
CLINICS = [
    ("Klinik Kesihatan Taman Melati", "KKM-001"),
    ("Klinik Medic Care Subang", "KMC-002"),
    ("Klinik Famili Ampang", "KFA-003"),
    ("Poliklinik Mutiara Shah Alam", "PMA-004"),
    ("Klinik Seri Petaling", "KSP-005"),
    ("Klinik 1Malaysia Kepong", "K1M-006"),
    ("Klinik Primer Kajang", "KPK-007"),
    ("Klinik Harmoni Klang", "KHK-008"),
    ("Klinik Sihat Johor Bahru", "KSJ-009"),
    ("Klinik Nur Ipoh", "KNI-010"),
]
CONDITIONS = [
    {"diagnosis": "Acute upper respiratory tract infection", "icd": "J06.9",
     "symptoms": ["fever","sore throat","runny nose","cough"],
     "meds": [{"name":"Paracetamol","dosage":"500mg","qty":20},{"name":"Loratadine","dosage":"10mg","qty":7}],
     "consult":(35,65),"med_cost":(15,40),"proc_cost":(0,0)},
    {"diagnosis": "Essential hypertension", "icd": "I10",
     "symptoms": ["headache","dizziness","elevated BP"],
     "meds": [{"name":"Amlodipine","dosage":"5mg","qty":30}],
     "consult":(40,70),"med_cost":(20,60),"proc_cost":(0,0)},
    {"diagnosis": "Type 2 diabetes mellitus", "icd": "E11",
     "symptoms": ["polyuria","polydipsia","fatigue"],
     "meds": [{"name":"Metformin","dosage":"500mg","qty":60}],
     "consult":(45,75),"med_cost":(25,80),"proc_cost":(0,30)},
    {"diagnosis": "Dengue fever", "icd": "A90",
     "symptoms": ["high fever","body aches","rash","low platelet"],
     "meds": [{"name":"Paracetamol","dosage":"500mg","qty":20}],
     "consult":(50,80),"med_cost":(15,35),"proc_cost":(30,80)},
    {"diagnosis": "Gastritis", "icd": "K29.7",
     "symptoms": ["epigastric pain","nausea","bloating"],
     "meds": [{"name":"Omeprazole","dosage":"20mg","qty":14}],
     "consult":(35,60),"med_cost":(15,45),"proc_cost":(0,0)},
    {"diagnosis": "Urinary tract infection", "icd": "N39.0",
     "symptoms": ["dysuria","frequency","urgency"],
     "meds": [{"name":"Ciprofloxacin","dosage":"500mg","qty":14}],
     "consult":(40,65),"med_cost":(20,50),"proc_cost":(10,30)},
    {"diagnosis": "Low back pain", "icd": "M54.5",
     "symptoms": ["lower back pain","stiffness","limited mobility"],
     "meds": [{"name":"Diclofenac","dosage":"50mg","qty":14},{"name":"Methocarbamol","dosage":"500mg","qty":14}],
     "consult":(40,65),"med_cost":(20,55),"proc_cost":(0,0)},
    {"diagnosis": "Asthma", "icd": "J45",
     "symptoms": ["wheeze","shortness of breath","cough"],
     "meds": [{"name":"Salbutamol inhaler","dosage":"100mcg","qty":1}],
     "consult":(40,70),"med_cost":(25,60),"proc_cost":(20,50)},
    {"diagnosis": "Dermatitis", "icd": "L30.9",
     "symptoms": ["skin rash","itching","redness"],
     "meds": [{"name":"Hydrocortisone cream","dosage":"1%","qty":1},{"name":"Cetirizine","dosage":"10mg","qty":7}],
     "consult":(35,55),"med_cost":(15,40),"proc_cost":(0,0)},
    {"diagnosis": "Acute gastroenteritis", "icd": "A09",
     "symptoms": ["diarrhoea","vomiting","abdominal cramps"],
     "meds": [{"name":"ORS","dosage":"sachet","qty":6},{"name":"Loperamide","dosage":"2mg","qty":10}],
     "consult":(35,60),"med_cost":(10,35),"proc_cost":(0,0)},
]


def _gen_ic(age: int) -> str:
    birth_year = datetime.now().year - age
    yy = f"{birth_year % 100:02d}"
    mm = f"{random.randint(1,12):02d}"
    dd = f"{random.randint(1,28):02d}"
    ss = random.choice(STATES)
    nnnn = f"{random.randint(1000,9999)}"
    return f"{yy}{mm}{dd}-{ss}-{nnnn}"


def _gen_claim(is_suspicious: bool = False) -> dict:
    cond = random.choice(CONDITIONS)
    name = random.choice(ALL_NAMES)
    age = random.randint(18, 75)
    gender = random.choice(["M", "F"])
    clinic_name, clinic_id = random.choice(CLINICS)
    days_ago = random.randint(0, 90)
    visit_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

    consult = round(random.uniform(*cond["consult"]), 2)
    med_cost = round(random.uniform(*cond["med_cost"]), 2)
    proc_cost = round(random.uniform(*cond["proc_cost"]), 2)

    meds = []
    for m in cond["meds"]:
        meds.append({"name": m["name"], "dosage": m["dosage"], "quantity": m["qty"]})

    if is_suspicious:
        # Inflate amounts
        consult *= random.uniform(1.8, 3.5)
        med_cost *= random.uniform(2.0, 4.0)
        # Add extra meds
        meds.append({"name": "Vitamin B Complex", "dosage": "tablet", "quantity": 90})
        consult = round(consult, 2)
        med_cost = round(med_cost, 2)

    total = round(consult + med_cost + proc_cost, 2)

    return {
        "patient_name": name,
        "patient_ic": _gen_ic(age),
        "patient_age": age,
        "patient_gender": gender,
        "visit_date": visit_date,
        "clinic_name": clinic_name,
        "clinic_id": clinic_id,
        "chief_complaint": cond["symptoms"][0] if cond["symptoms"] else cond["diagnosis"],
        "diagnosis": cond["diagnosis"],
        "icd10_code": cond["icd"],
        "symptoms": cond["symptoms"],
        "procedures": [],
        "medications": meds,
        "consultation_fee_myr": consult,
        "medication_fee_myr": med_cost,
        "procedure_fee_myr": proc_cost,
        "total_amount_myr": total,
        "follow_up_required": random.random() < 0.3,
        "referral_needed": random.random() < 0.1,
        "is_suspicious": is_suspicious,
    }


def generate(count: int = 500) -> list:
    """Generate synthetic claims — 80% clean, 10% borderline, 10% suspicious."""
    claims = []
    for i in range(count):
        is_sus = i >= int(count * 0.9)  # last 10% suspicious
        claims.append(_gen_claim(is_suspicious=is_sus))
    random.shuffle(claims)
    return claims


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    print(f"Generating {count} synthetic Malaysian GP claims...")

    claims = generate(count)

    # Save to JSON
    out_path = os.getenv("SYNTHETIC_DATA_PATH", ".tmp/synthetic_claims.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(claims, f, indent=2)
    print(f"Saved {len(claims)} claims to {out_path}")

    # Insert into database
    print("Inserting into database...")
    for claim in claims:
        raw = (
            f"Patient: {claim['patient_name']}\n"
            f"IC: {claim['patient_ic']}\n"
            f"Date: {claim['visit_date']}\n"
            f"Clinic: {claim['clinic_name']}\n"
            f"Diagnosis: {claim['diagnosis']}\n"
            f"Total: RM {claim['total_amount_myr']}"
        )
        db.insert_claim(raw, extracted=claim)
    print(f"Inserted {len(claims)} claims into database.")


if __name__ == "__main__":
    main()
