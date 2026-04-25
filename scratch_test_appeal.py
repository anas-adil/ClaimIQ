import requests
import json
import traceback

print("Testing Appeal Endpoint...")
try:
    url = "http://localhost:8000/api/claims/122/appeal"
    payload = {"appeal_reason": "Testing appeal generation", "supporting_evidence": ""}
    res = requests.post(url, json=payload)
    print("Status:", res.status_code)
    print("Response:", res.text)
except Exception as e:
    traceback.print_exc()
