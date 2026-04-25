# ClaimIQ Demo Directive

> SOP for running the complete ClaimIQ demo end-to-end.


### Prerequisites

- Python 3.10+
- a valid ZAI_API_KEY
- a valid GEMINI_API_KEY if you want image-analysis support

## Quick Start (5 minutes)

```bash
# 1. Navigate to project
cd c:\Users\User\Downloads\tpa

# 2. Build policy index (one-time, creates FAISS index)
python execution/build_policy_index.py

# 3. Start API server (serves backend + frontend)
python execution/api_server.py

# 4. Open browser to http://localhost:8000
# 5. Click "Seed Demo" button to populate with 50 pre-processed claims
# 6. Browse Dashboard, Claims Queue, Fraud Detection
# 7. Submit a new claim via "Submit Claim" tab
```

## Demo Flow for Judges

### Opening (30 seconds)
"Every day, 9,830 Malaysian GPs lose 4+ hours fighting claim rejections.
ClaimIQ uses Z.AI GLM to process claims in seconds — not months."

### Live Demo (3 minutes)
1. Show Dashboard with seeded data — approval rates, fraud flags, financial summary
2. Open a claim detail → show GLM-generated reasoning, ICD codes, fraud score, GP advisory
3. Go to Submit Claim → paste sample clinical note → watch GLM pipeline animation
4. Show the 5-step process completing in real-time
5. Open the processed claim → walk through each section

### Architecture (1 minute)
"Z.AI GLM powers every step — document understanding, ICD-10 coding,
RAG-based adjudication, fraud detection, and GP advisory.
Remove GLM, and you get blank screens."

### Close (30 seconds)
"60-day processing → 60 seconds. That's ClaimIQ."

## Sample Clinical Note for Demo

```
Patient: Siti Nurhaliza binti Mohd
IC: 900215-14-3456
Date: 2024-03-20
Clinic: Klinik Famili Ampang
Complaint: Persistent cough and fever for 5 days, body aches
Diagnosis: Dengue fever with warning signs
Symptoms: High fever 39.2C, severe body aches, rash on arms, low platelet count
Procedures: Full blood count, dengue NS1 antigen test
Medications: Paracetamol 500mg x 30, ORS sachets x 10
Consultation: RM 65
Procedures: RM 80
Medications: RM 35
Total: RM 180
```

## Troubleshooting

| Issue | Fix |
|:---|:---|
| "ZAI_API_KEY not set" | Check `.env` file, ensure key has no quotes |
| FAISS import error | `pip install faiss-cpu` |
| Port 8000 in use | Change `API_PORT` in `.env` |
| Frontend not loading | Ensure `execution/frontend/` directory exists |
| Slow GLM responses | Normal for first call; subsequent calls are faster |

## Edge Cases Learned

- GLM JSON output occasionally includes markdown fences — `_call_glm()` handles this
- FAISS requires float32 numpy arrays — enforced in `rag_engine.py`
- SQLite concurrent writes — single-writer model, safe for demo
