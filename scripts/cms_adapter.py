"""Read-only contract adapter; no assumptions about an existing CMS database."""
import argparse,json,os
from pathlib import Path
import httpx
p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--token-file',required=True);p.add_argument('--ca',required=True);p.add_argument('--cursor-file',required=True);a=p.parse_args()
token=Path(a.token_file).read_text().strip();cursor_path=Path(a.cursor_file);cursor=int(cursor_path.read_text()) if cursor_path.exists() else 0
with httpx.Client(base_url=a.url,headers={'Authorization':'Bearer '+token},verify=a.ca,timeout=15) as c:
    while True:
        r=c.get('/api/v1/events',params={'after':cursor,'limit':100});r.raise_for_status();events=r.json()
        if not events:break
        for event in events:
            # Replace this receiver only after reviewing the actual CMS contract.
            print(json.dumps(event,ensure_ascii=False))
            cursor=event['seq']
            tmp=cursor_path.with_suffix('.tmp');tmp.write_text(str(cursor));tmp.chmod(0o600);os.replace(tmp,cursor_path)
