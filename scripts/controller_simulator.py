"""Protocol simulator. No physical pinout or voltage assumptions."""
import argparse,time,uuid
import httpx
p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--token-file',required=True);p.add_argument('--ca',required=True);p.add_argument('--box',type=int,default=1)
a=p.parse_args();operator=str(uuid.uuid4())
with open(a.token_file) as f: token=f.read().strip()
with httpx.Client(base_url=a.url,headers={'Authorization':'Bearer '+token},verify=a.ca,timeout=10) as c:
    c.post('/api/v1/operator',json={'operator_id':operator}).raise_for_status()
    s=c.get('/api/v1/state');s.raise_for_status();t=s.json()['tables'][0]
    command_id=str(uuid.uuid4())
    intent={'command_id':command_id,'sequence':t['device_sequence']+1,'operator_id':operator,'op':'confirm','payload':{'table_id':t['id'],'round_id':t['next_round_id'],'boxes':[a.box]}}
    # Retry SAME intent and ID, even if response was lost. Never create a new ID on timeout.
    for attempt in range(3):
        try:
            r=c.post('/api/v1/commands',json=intent);r.raise_for_status();print(r.json());break
        except httpx.TransportError:
            time.sleep(1)
    else: raise SystemExit('Status unknown: query GET /api/v1/commands/'+command_id)
