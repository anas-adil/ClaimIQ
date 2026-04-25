## Pitching video

[Pitching Video here](https://drive.google.com/drive/folders/1zzBbxtnOlhPAZAEeuZ46-U1t6RLOH7S9?usp=drive_linkhttps://drive.google.com/drive/folders/1zzBbxtnOlhPAZAEeuZ46-U1t6RLOH7S9?usp=drive_link)


# ClaimIQ: Deterministic Clinical Adjudication & Fraud Intelligence
ClaimIQ is an AI-assisted claims intelligence platform for outpatient medical claims. It is built to help Third-Party Administrators (TPAs), reviewers, and clinic-facing operations teams move from raw claim evidence to a structured, explainable decision workflow with stronger fraud checks and safer manual-review gates.

At the center of the system is `Z.AI GLM`, which handles the reasoning-heavy parts of the pipeline: claim extraction, clinical validation, coding, adjudication, fraud analysis, advisory generation, appeal drafting, weekly reporting, and claim chat. Around that, the project uses deterministic backend logic to keep the workflow auditable and predictable.


## Why ClaimIQ

Medical claims workflows are often slowed down by fragmented evidence, repetitive manual review, and weak traceability. ClaimIQ is designed to reduce that friction by combining:

- structured claim intake
- multimodal evidence parsing
- policy retrieval with FAISS-backed RAG
- GLM-powered adjudication and fraud checks
- manual-review safety gating
- audit-friendly claim state tracking

The result is a demoable end-to-end system that shows how AI can support claims operations without jumping straight to unsafe autonomous decisions.

## What the product does

ClaimIQ currently supports:

- new claim submission and processing
- pre-adjudication scrubbing and eligibility checks
- evidence parsing for invoices, lab reports, and imaging documents
- ICD-10 / CPT coding support
- policy-aware adjudication
- fraud scoring and anomaly review
- bilingual GP advisory output
- appeal drafting
- weekly intelligence reporting
- per-claim chat grounded in claim context
- dashboard, claims queue, denial, and fraud views

## System architecture

The repo follows a practical three-part flow:

1. `Deterministic orchestration`
   - FastAPI routes, validation, claim lifecycle handling, audit logging, and persistence.
2. `Multimodal evidence understanding`
   - document triage and evidence parsing through `MedGemma`, with Gemini-backed paths in the client layer.
3. `Reasoning and decisions`
   - `Z.AI GLM` powers extraction, validation, coding, adjudication, fraud analysis, advisory text, appeals, weekly reports, and claim chat.

This split matters: the model handles reasoning, while the application enforces workflow rules, storage, routing, and manual-review safeguards.

## Processing pipeline

The current processing flow in the codebase is an `8-step pipeline` plus output generation:

1. Scrubbing
2. Eligibility
3. Document extraction
4. Clinical validation
5. Medical coding
6. Adjudication with RAG context
7. Fraud detection
8. GP advisory
9. EOB generation and status handling

Important safety behavior:

- claims are fail-closed when GLM is unavailable
- high-risk fraud signals can force referral
- automatic denials are converted to `REFERRED`
- approvals are also frozen behind human review in the current demo flow

So the system is explicitly built as decision support, not fully autonomous adjudication.

## Tech stack

- `Backend`: FastAPI, Python
- `Database`: SQLite
- `LLM / reasoning`: Z.AI GLM
- `Retrieval`: FAISS + sentence-transformers
- `Multimodal evidence parsing`: MedGemma client flow with Gemini-backed support in the evidence layer
- `Frontend`: Vanilla JavaScript, HTML, CSS

## Repository map

- [execution/api_server.py](execution/api_server.py)  
  FastAPI server, routing, analytics endpoints, appeal flow, claim chat, and demo utilities.

- [execution/claims_processor.py](execution/claims_processor.py)  
  Main processing pipeline, safety gates, fraud overrides, and final decision routing.

- [execution/glm_client.py](execution/glm_client.py)  
  Z.AI GLM wrapper and prompt-driven intelligence functions.

- [execution/database.py](execution/database.py)  
  SQLite schema, claim storage, audit trail, analytics, fraud rows, and appeals.

- [execution/rag_engine.py](execution/database.py)  
  FAISS index loading and policy retrieval for adjudication context.

- [execution/evidence_parser.py](execution/generate_synthetic_data.py)  
  Evidence parsing entrypoint.

- [execution/medgemma_client.py](execution/medgemma_client.py)  
  MedGemma and image-analysis bridge.

- [execution/frontend/](execution/frontend)  
  Dashboard and workflow UI.

- [directives/hackathon_demo.md](directives/hackathon_demo.md)  
  Demo SOP for running the project end to end.

- [docs/](docs/)  
  Submission materials such as the PRD, architecture docs, and deck.

## Quick start

### Prerequisites

- Python `3.10+`
- a valid `ZAI_API_KEY`
- a valid `GEMINI_API_KEY` if you want image-analysis support

### Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file based on [.env.example](C:/Users/harlo/Downloads/ClaimIQ-main/ClaimIQ-main/.env.example).

3. Build the policy index:

```bash
python execution/build_policy_index.py
```

4. Start the API server:

```bash
python execution/api_server.py
```

5. Open:

```text
http://localhost:8000
```

### Demo flow

Once the app is running, you can:

- seed demo claims
- review dashboard metrics
- inspect claim decisions and audit trail
- open the fraud view
- submit a new claim through the UI
- ask claim-specific questions through Claim Chat
- draft an appeal from a referred or denied claim

## Key endpoints

- `POST /api/claims/submit`
- `POST /api/claims/scrub`
- `POST /api/claims/eligibility`
- `GET /api/claims`
- `GET /api/claims/{claim_id}`
- `POST /api/claims/{claim_id}/appeal`
- `POST /api/claims/{claim_id}/chat`
- `GET /api/analytics/summary`
- `GET /api/analytics/kpis`
- `GET /api/analytics/denials`
- `GET /api/analytics/fraud-heatmap`
- `GET /api/analytics/weekly-report`

## Notes on current scope

This repository is strongest as a hackathon demo and technical proof of concept. A few things are intentionally lightweight today:

- SQLite is used for the current persistence layer
- several analytics and demo flows are optimized for showcase use
- MedGemma setup may require extra local or hosted configuration depending on your environment
- claim decisions are deliberately gated toward human review for safety

## Documentation

Supporting docs live in [docs](docs/).


---

Built for the Z.AI Hackathon.
