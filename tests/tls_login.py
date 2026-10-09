"""Verify login and authenticated state over actual HTTPS with certificate trust."""
import subprocess,json
from pathlib import Path
base=['curl','--silent','--show-error','--fail','--noproxy','*','--cacert','/tmp/premier-compose-root.crt','--resolve','progressive.test:8443:127.0.0.1']
r=subprocess.run(base+['-H','Content-Type: application/json','--data-binary','@-','https://progressive.test:8443/api/v1/login'],input=json.dumps({'name':'admin','password':Path('/tmp/premier-compose-admin-password').read_text()}),text=True,capture_output=True,check=True)
token=json.loads(r.stdout)['token']
# Pass authorization by stdin config, never emit credentials or put token in URL.
r=subprocess.run(base+['--config','-','https://progressive.test:8443/api/v1/state'],input='header = "Authorization: Bearer '+token+'"\n',text=True,capture_output=True,check=True)
s=json.loads(r.stdout);assert s['environment']=='test' and s['production_released'] is False
assert len(s['pools'])==5
print('Actual HTTPS login and authenticated authoritative state: passed; CA verification enabled.')
