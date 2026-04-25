import sys
import requests, base64, json

sys.stdout.reconfigure(encoding="utf-8")

with open('execution/frontend/assets/sample_xray.png', 'rb') as f:
    img_b64 = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()

r1 = requests.post('http://localhost:8000/api/claims/submit', json={
    'raw_text': 'Patient presents with persistent cough and fever for 5 days. Prescribed Amoxicillin 500mg.',
    'evidence_attached': True, 'bill_attached': True, 'evidence_base64': img_b64
})
cid1 = r1.json()['claim_id']
r2 = requests.post(f'http://localhost:8000/api/claims/process/{cid1}')
d = r2.json()

print('=== PNEUMONIA TEST ===')
print('Status:', d.get('final_status'))
adj = d.get('steps', {}).get('adjudication', {})
print('Adjudication keys:', list(adj.keys()) if adj else 'NONE')
print('Decision:', adj.get('decision'))
print('Reasoning:', adj.get('reasoning', adj.get('adjudication_reasoning', 'N/A'))[:400])
print('Amount Approved:', adj.get('amount_approved_myr'))
print('Confidence:', adj.get('confidence'))

# Check claim detail endpoint
r3 = requests.get(f'http://localhost:8000/api/claims/{cid1}')
claim = r3.json()
print('\n=== CLAIM DETAIL ===')
print('Status:', claim.get('status'))
print('Diagnosis:', claim.get('diagnosis'))
print('ICD10:', claim.get('icd10_code'))
print('Amount:', claim.get('total_amount_myr'))
