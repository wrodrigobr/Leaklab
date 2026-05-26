import sys, os, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
os.environ["GTO_WIZARD_ENABLED"] = "true"
from leaklab.gto_wizard_client import get_status

for i in range(20):
    s = get_status()
    auth = s.get("auth_ok")
    age  = s.get("age_sec")
    print(f"[{i*15:3d}s] auth={auth}  age={age}")
    if auth:
        print("Auth OK!")
        break
    time.sleep(15)
else:
    print("Timeout — auth nao capturada em 5 min")
