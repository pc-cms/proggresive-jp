"""Test the real shipped backup/restore scripts on the isolated Compose DB."""
import subprocess,hashlib,json,os,time
from pathlib import Path

def run(args,**kwargs):return subprocess.run(args,check=True,capture_output=True,**kwargs)
def query(db,sql):
    return run(['docker','compose','exec','-T','db','psql','-U','progressive','-d',db,'-Atc',sql]).stdout.strip()
backup=run(['./scripts/backup.sh'],text=True).stdout.strip()
target='progressive_restore_acceptance_'+str(int(time.time()))
run(['./scripts/restore.sh',backup,target])
for sql in ['SELECT state FROM casino ORDER BY id','SELECT id,hash FROM events ORDER BY seq','SELECT id,request_hash FROM commands ORDER BY id','SELECT id,name,role FROM principals ORDER BY id','SELECT version FROM schema_migrations ORDER BY version']:
    assert query('progressive',sql)==query(target,sql),sql
print(json.dumps({'backup_script':'passed','restore_to_clean_database':'passed','funds_rounds_claims':'identical','journal_hashes':'identical','commands_idempotency_records':'identical','principals_and_migrations':'identical'},indent=2))
