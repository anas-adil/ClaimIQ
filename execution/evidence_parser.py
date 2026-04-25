"""
evidence_parser.py — Main Evidence Parsing Orchestrator
"""

import logging
import document_triage
import medgemma_client

logger = logging.getLogger("claimiq.parser")

def parse_evidence(image_b64: str) -> dict:
    """
    Full evidence parsing pipeline.
    Returns: {
        "triage": {...},          # from document_triage
        "parsed_evidence": {...}, # from MedGemma
        "source": "MEDGEMMA_LIVE" | "PARSE_FAILED" | "NO_EVIDENCE",
        "parsing_confidence": 0.0-1.0
    }
    """
    if not image_b64:
        return {"source": "NO_EVIDENCE", "parsing_confidence": 1.0}
        
    logger.info("Triaging evidence document...")
    triage = document_triage.triage_evidence(image_b64)
    logger.info(f"Triage result: {triage['doc_type']} (Quality: {triage['quality']})")
    
    doc_type = triage["doc_type"]
    
    if triage["quality"] in ["POOR", "BLURRY", "SUSPECT"]:
        logger.warning(f"Parsing suboptimal image: {triage['warnings']}")
        
    logger.info(f"Routing to MedGemma parser for {doc_type}...")
    
    if doc_type == "XRAY":
        parsed = medgemma_client.analyze_xray(image_b64)
    elif doc_type == "LAB_REPORT":
        parsed = medgemma_client.analyze_lab_report(image_b64)
    elif doc_type == "INVOICE":
        parsed = medgemma_client.analyze_invoice(image_b64)
    else: # UNKNOWN
        logger.warning("Document type UNKNOWN, attempting fallback lab report parsing...")
        parsed = medgemma_client.analyze_lab_report(image_b64)
        
    if "error" in parsed:
        logger.error(f"Evidence parsing failed: {parsed['error']}")
        return {
            "triage": triage,
            "parsed_evidence": parsed,
            "source": "PARSE_FAILED",
            "parsing_confidence": 0.0
        }
        
    confidence_key = "confidence" if doc_type == "XRAY" else "extraction_confidence"
    conf = parsed.get(confidence_key, 0.0)
    
    return {
        "triage": triage,
        "parsed_evidence": parsed,
        "source": parsed.get("_source", "MEDGEMMA_LIVE"),
        "parsing_confidence": conf
    }
