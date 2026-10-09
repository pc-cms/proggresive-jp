import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException
from .db import connection, lock

PH = PasswordHasher()
def digest(v): return hashlib.sha256(v.encode()).hexdigest()
def uid(): return secrets.token_hex(16)
def now(): return datetime.now(timezone.utc)
def fail(code, message): raise HTTPException(code, message)

def issue(c, principal, days=1):
    token=secrets.token_urlsafe(48)
    c.execute('INSERT INTO sessions(token_hash,principal_id,expires_at) VALUES(%s,%s,%s)', (digest(token), principal, now()+timedelta(days=days)))
    return token

def authenticate(token):
    with connection() as c:
        p=c.execute('SELECT p.*, s.token_hash FROM sessions s JOIN principals p ON p.id=s.principal_id WHERE token_hash=%s AND expires_at>now() AND active', (digest(token),)).fetchone()
        if not p: fail(401, 'Authentication required')
        c.execute('UPDATE sessions SET last_seen=now() WHERE token_hash=%s',(digest(token),))
        return p

def login(name,password):
    invalid=False
    with connection() as c:
        lock(c)
        a=c.execute('SELECT * FROM login_attempts WHERE name=%s',(name,)).fetchone()
        if a and a['blocked_until']>now(): fail(429,'Too many attempts; wait five minutes')
        p=c.execute('SELECT * FROM principals WHERE name=%s AND active',(name,)).fetchone()
        try: valid=p and p['password_hash'] and PH.verify(p['password_hash'],password)
        except VerificationError: valid=False
        if not valid:
            failures=(a['failures'] if a else 0)+1
            c.execute('INSERT INTO login_attempts VALUES(%s,%s,%s) ON CONFLICT(name) DO UPDATE SET failures=EXCLUDED.failures,blocked_until=EXCLUDED.blocked_until', (name,failures,now()+timedelta(minutes=5) if failures>=5 else now()))
            invalid=True
        else:
            c.execute('DELETE FROM login_attempts WHERE name=%s',(name,))
            token=issue(c,p['id'])
    if invalid: fail(401,'Invalid credentials')
    return {'token':token,'role':p['role']}
