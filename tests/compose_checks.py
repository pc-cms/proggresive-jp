"""Populated TEST database, TLS request, actual process restart persistence."""
import subprocess,json
from pathlib import Path
code='''
import sys,uuid,json
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app,base_url="https://testserver")
r=c.post("/api/v1/login",json={"name":"admin","password":sys.stdin.read().strip()});assert r.status_code==200
c.headers["Authorization"]="Bearer "+r.json()["token"]
assert c.get("/api/v1/state").json()["environment"]=="test"
def cmd(op,p):
 r=c.post("/api/v1/commands",json={"command_id":str(uuid.uuid4()),"op":op,"payload":p});assert r.status_code==200,r.text;return r.json()["result"]
existing=c.get("/api/v1/state").json()
if any(x["status"] in ("pending","disputed") for x in existing["claims"]):
 print(json.dumps({k:existing[k] for k in ("pools","rounds","claims","tables")}));sys.exit(0)
suffix=uuid.uuid4().hex[:6]
t=cmd("table_register",{"number":"fixture-"+suffix,"name":"TEST fixture"})
r=cmd("confirm",{"table_id":t["id"],"round_id":t["next_round_id"],"boxes":[1,2]})
cmd("claim",{"table_id":t["id"],"round_id":r["id"],"box":1,"tier":1,"type":"fixed"})
cmd("claim",{"table_id":t["id"],"round_id":r["id"],"box":2,"tier":5,"type":"progressive"})
s=c.get("/api/v1/state").json()
print(json.dumps({k:s[k] for k in ("pools","rounds","claims","tables")}))
'''
# Password passed over stdin, never in CLI args/output.
r=subprocess.run(['docker','compose','exec','-T','app','python','-c',code],input=Path('/tmp/premier-compose-admin-password').read_text(),text=True,capture_output=True,check=True)
before=json.loads(r.stdout)
assert any(x['status']=='pending' for x in before['claims'])
subprocess.run(['docker','compose','restart','app'],check=True,capture_output=True)
read_code='''
import sys,json,time
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app,base_url="https://testserver")
r=c.post("/api/v1/login",json={"name":"admin","password":sys.stdin.read().strip()});assert r.status_code==200
c.headers["Authorization"]="Bearer "+r.json()["token"]
s=c.get("/api/v1/state").json();print(json.dumps({k:s[k] for k in ("pools","rounds","claims","tables")}))
'''
r=subprocess.run(['docker','compose','exec','-T','app','python','-c',read_code],input=Path('/tmp/premier-compose-admin-password').read_text(),text=True,capture_output=True,check=True)
assert json.loads(r.stdout)==before
r=subprocess.run(['curl','--silent','--show-error','--fail','--noproxy','*','--cacert','/tmp/premier-compose-root.crt','--resolve','progressive.test:8443:127.0.0.1','https://progressive.test:8443/health'],text=True,capture_output=True,check=True)
assert json.loads(r.stdout)['status']=='ok'
print(json.dumps({'compose_populated_financial_api':True,'actual_app_process_restart':True,'funds_rounds_claims_persisted':True,'verified_tls_https_health':True},indent=2))
