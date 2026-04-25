import sys
import requests, base64, json

sys.stdout.reconfigure(encoding="utf-8")

# Test 1: Pneumonia X-ray
with open('execution/frontend/assets/sample_xray.png', 'rb') as f:
    img_b64 = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()

r1 = requests.post('http://localhost:8000/api/claims/submit', json={
    'raw_text': 'Patient presents with persistent cough and fever for 5 days. Prescribed Amoxicillin 500mg.',
    'evidence_attached': True, 'bill_attached': True, 'evidence_base64': img_b64,
    'patient_name': 'Siti Nurhaliza binti Mohd', 'patient_ic': '900215-14-3456', 'clinic_name': 'Klinik Famili Ampang',
    'visit_date': '2026-04-01', 'total_amount_myr': 120.0
}, timeout=180)
cid1 = r1.json()['claim_id']
print('Claim submitted, id:', cid1)

r2 = requests.post(f'http://localhost:8000/api/claims/process/{cid1}', timeout=180)
d = r2.json()
print('--- PNEUMONIA TEST ---')
print('Status:', d.get('final_status'))
adj = d.get('steps', {}).get('adjudication', {})
reasoning = adj.get('reasoning', d.get('error', 'N/A'))
print('Reasoning:', reasoning[:300])

# Test 2: Dengue (no image)
r3 = requests.post('http://localhost:8000/api/claims/submit', json={
    'raw_text': 'Patient with dengue fever. High temperature 40C. Prescribed paracetamol and IV fluids.',
    'evidence_attached': True, 'bill_attached': True,
    'patient_name': 'Siti Nurhaliza', 'patient_ic': '880505-10-5555', 'clinic_name': 'Klinik Kesihatan Shah Alam',
    'visit_date': '2026-04-02', 'total_amount_myr': 240.0
}, timeout=180)
cid2 = r3.json()['claim_id']
r4 = requests.post(f'http://localhost:8000/api/claims/process/{cid2}', timeout=180)
d2 = r4.json()
print('\n--- DENGUE TEST ---')
print('Status:', d2.get('final_status'))
adj2 = d2.get('steps', {}).get('adjudication', {})
reasoning2 = adj2.get('reasoning', d2.get('error', 'N/A'))
print('Reasoning:', reasoning2[:300])

# Test 3: Fracture
r5 = requests.post('http://localhost:8000/api/claims/submit', json={
    'raw_text': 'Patient came in with a suspected bone fracture in leg after accident. X-ray taken. Plastered.',
    'evidence_attached': True, 'bill_attached': True,
    'patient_name': 'Lee Chong Wei', 'patient_ic': '900101-14-1234', 'clinic_name': 'Klinik Ortopedik KL',
    'visit_date': '2026-04-03', 'total_amount_myr': 450.0
}, timeout=180)
cid3 = r5.json()['claim_id']
r6 = requests.post(f'http://localhost:8000/api/claims/process/{cid3}', timeout=180)
d3 = r6.json()
print('\n--- FRACTURE TEST ---')
print('Status:', d3.get('final_status'))
adj3 = d3.get('steps', {}).get('adjudication', {})
reasoning3 = adj3.get('reasoning', d3.get('error', 'N/A'))
print('Reasoning:', reasoning3[:300])
