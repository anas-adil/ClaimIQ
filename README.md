# ClaimIQ: Deterministic Clinical Adjudication & Fraud Intelligence

## 📺 Pitching Video
**Watch our full pitching video here:** 
👉 **[Link to Pitching Video (Google Drive/Cloud Storage)]** 
*(Participants: Replace this placeholder with your actual recording link)*

---

## 🚀 Key Critical Component: Z AI GLM Integration
**ClaimIQ is powered primarily by Z AI’s GLM (General Language Model) Architecture.** 

As per the competition requirements, Z AI GLM serves as the central brain and main critical component of our solution. We utilize GLM for:
*   **Clinical Adjudication**: Processing extracted clinical data against complex medical policies and RAG-based insurance rules.
*   **Medical Coding**: Mapping doctor descriptions to standard ICD-10 and CPT codes.
*   **Fraud & Anomaly Detection**: Identifying clinical discrepancies between objective lab results and subjective clinical notes.
*   **GP Advisory**: Generating human-readable, professional guidance for clinics and patients.

The system is architected to be **deterministic**—the AI provides decision-support and risk-scoring, but enforces a "Doctor-First" safety freeze where all negative outcomes (denials) are gated for human clinical sign-off.

---

## 📝 Overview
ClaimIQ is a next-generation Third Party Administrator (TPA) platform designed to eliminate unsafe fallback behaviors and automate the clinical adjudication pipeline with 100% auditability. 

### Core Features:
*   **Multi-Modal Evidence Parsing**: Utilizes Vision Agents (Gemini/MedGemma) to extract structured data from X-rays, Lab Reports, and Invoices.
*   **"Double-Agent" Architecture**: Separates Vision Extraction from Reasoning Adjudication (GLM) for maximum reliability.
*   **Safety-First Design**: Automated "Safety Freeze" prevents autonomous denials without human review.
*   **Immutable Audit Trail**: Every decision state change and AI reasoning step is logged with SHA-256 integrity hashes.
*   **Anti-Fraud Engine**: Detects clinical mismatches (e.g., Doctor claims severe dengue, but Lab Report shows normal platelets).

---

## 🛠 Architecture
ClaimIQ operates on a 3-layer architecture:
1.  **Ingestion & Triage**: Validating image quality (blur detection) and identifying document types.
2.  **Evidence Extraction**: Converting unstructured images into structured JSON medical data.
3.  **GLM Intelligence Layer**: 
    *   **Reasoning**: Adjudicating against benefit tiers.
    *   **Cross-Referencing**: Validating the bill against the clinical evidence.
    *   **Fraud Scoring**: Generating a risk level based on clinical consistency.

---

## 📂 Project Structure
*   `execution/`: Core backend logic (Python/FastAPI) and Frontend (Vanilla JS/CSS).
*   `directives/`: Standard Operating Procedures for system logic.
*   `docs/`: Competition deliverables (PRD, SAD, TAD, and Pitch Deck).
*   `database.py`: Immutable audit logs and claim state management.

---

## 🏁 Getting Started

### Prerequisites
*   Python 3.10+
*   Z AI GLM API Key
*   Gemini API Key (for Vision)

### Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install fastapi uvicorn openai google-generativeai pydantic pillow
   ```
3. Set up your `.env` file (see `.env.example` for required keys).
4. Run the server:
   ```bash
   python execution/api_server.py
   ```

---

## 📄 Documentation (In `docs/` Folder)
The following mandatory files are available in the `/docs` directory:
1.  **PRD.pdf** (Product Requirements Document)
2.  **SAD.pdf** (Software Architecture Document)
3.  **TAD.pdf** (Technical Architecture Document)
4.  **Pitch_Deck.pdf**

---
© 2026 ClaimIQ Team | Developed for the Preliminary Round Submission.
