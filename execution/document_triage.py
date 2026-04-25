"""
document_triage.py — Document Classification & Quality Gate

Responsibilities:
- Determine document type (XRAY, LAB_REPORT, INVOICE, UNKNOWN)
- Check image quality (blur, resolution, size)
"""

import base64
import io
import logging
import cv2
import numpy as np
from PIL import Image

import medgemma_client

logger = logging.getLogger("claimiq.triage")

def check_image_quality(image_b64: str) -> dict:
    """
    Check image resolution, blur, and size.
    Returns: {"quality": "GOOD"|"POOR"|"BLURRY"|"SUSPECT", "details": {...}, "warnings": [...]}
    """
    warnings = []
    quality = "GOOD"
    
    try:
        # Strip data URL prefix if present
        if image_b64.startswith("data:"):
            image_b64 = image_b64.split(",", 1)[-1]
            
        img_data = base64.b64decode(image_b64)
        file_size_kb = len(img_data) / 1024
        
        if file_size_kb < 10:
            quality = "SUSPECT"
            warnings.append(f"File size too small ({file_size_kb:.1f} KB)")
            
        img = Image.open(io.BytesIO(img_data))
        width, height = img.size
        
        if width < 500 or height < 500:
            if quality == "GOOD": quality = "POOR"
            warnings.append(f"Low resolution ({width}x{height})")
            
        # Blur detection using OpenCV variance of Laplacian
        # Safely handle various image modes (RGBA, L, CMYK, etc.)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if blur_score < 100:
            if quality in ("GOOD", "POOR"): quality = "BLURRY"
            warnings.append(f"Image appears blurry (score: {blur_score:.1f})")
            
        return {
            "quality": quality,
            "details": {
                "resolution": f"{width}x{height}",
                "blur_score": round(blur_score, 1),
                "file_size_kb": round(file_size_kb, 1)
            },
            "warnings": warnings
        }
    except Exception as e:
        logger.error(f"Image quality check failed: {e}")
        return {
            "quality": "UNKNOWN",
            "details": {"error": str(e)},
            "warnings": ["Failed to analyze image quality"]
        }

def classify_document(image_b64: str) -> dict:
    """
    Classify document type using MedGemma.
    Returns: {"doc_type": "...", "confidence": ..., "reasoning": "..."}
    """
    result = medgemma_client.classify_document(image_b64)
    if "error" in result:
        logger.warning(f"Classification failed, defaulting to UNKNOWN: {result['error']}")
        return {"doc_type": "UNKNOWN", "confidence": 0.0, "reasoning": result["error"]}
        
    doc_type = result.get("doc_type", "UNKNOWN").upper()
    if doc_type not in ["XRAY", "LAB_REPORT", "INVOICE"]:
        doc_type = "UNKNOWN"
        
    return {
        "doc_type": doc_type,
        "confidence": result.get("confidence", 0.0),
        "reasoning": result.get("reasoning", "")
    }

def triage_evidence(image_b64: str) -> dict:
    """Run full triage pipeline."""
    quality_result = check_image_quality(image_b64)
    class_result = classify_document(image_b64)
    insufficient = quality_result["quality"] in {"POOR", "BLURRY", "SUSPECT", "UNKNOWN"}
    
    return {
        "doc_type": class_result["doc_type"],
        "doc_type_confidence": class_result["confidence"],
        "quality": quality_result["quality"],
        "quality_details": quality_result["details"],
        "warnings": quality_result["warnings"],
        "insufficient_evidence": insufficient,
    }
