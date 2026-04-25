import requests
import base64
import json

with open("execution/frontend/assets/sample_xray.png", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

payload = {
    "raw_text": "Patient presents with cough. Diagnosed with pneumonia.",
    "evidence_attached": True,
    "evidence_base64": img_b64
}

res = requests.post("http://localhost:8000/api/claims/submit", json=payload)
print(res.json())
