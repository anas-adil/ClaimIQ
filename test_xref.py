"""Quick test: does cross_reference_engine catch Platelet 15 vs 176?"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.getcwd(), "execution"))
from cross_reference_engine import check_lab_vs_description

# Simulated MedGemma output from the lab report image (Platelets 176)
parsed_results = [
    {"test": "Platelet", "value": 176, "flag": None, "unit": "x10^3/uL", "ref_range": "150-400"},
    {"test": "Hemoglobin", "value": 12.2, "flag": "L", "unit": "g/dL", "ref_range": "13.0-18.0"},
    {"test": "Hematocrit", "value": 37.1, "flag": "L", "unit": "%", "ref_range": "40.0-54.0"},
]

# Doctor's notes claim Platelets 15 and HCT >55%
doctor_notes = (
    "Patient presented with acute febrile illness, severe myalgia, and retro-orbital pain. "
    "Today's stat lab results show severe hemoconcentration with critically high Hematocrit (>55%) "
    "and abnormally high Hemoglobin. "
    "Platelet count has completely crashed to a critical low of 15 x10^3/uL (severe thrombocytopenia)."
)

checks = check_lab_vs_description(parsed_results, doctor_notes)
print(f"Contradictions found: {len(checks)}")
for c in checks:
    print(f"  [{c['result']}] {c['field']}: Doctor says {c['doctor_says']}, Lab shows {c['lab_shows']}")
    print(f"  Note: {c['note']}")
    print()

if len(checks) == 0:
    print("FAIL: No contradictions detected!")
    sys.exit(1)
else:
    print("PASS: Fraud contradictions correctly detected!")
