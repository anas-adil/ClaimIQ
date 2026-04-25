import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), 'execution'))
import database as db

try:
    c = db.get_full_claim(122)
    print("Claim 122:", c is not None)
    
    # Try an insert appeal directly
    cid = db.insert_appeal(122, "Test reason", "Test evidence", "Test Rebuttal", "Test Rebuttal BM")
    print("Inserted appeal:", cid)
except Exception as e:
    import traceback
    traceback.print_exc()
