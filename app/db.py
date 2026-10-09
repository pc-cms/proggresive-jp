import os
from pathlib import Path
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

DSN = os.environ['DATABASE_URL']
POOL = ConnectionPool(DSN,min_size=1,max_size=24,timeout=10,open=True,kwargs={'row_factory':dict_row})

@contextmanager
def connection():
    with POOL.connection() as c:
        yield c

def migrate():
    with connection() as c:
        c.execute('SELECT pg_advisory_xact_lock(714005)')
        exists = c.execute("SELECT to_regclass('public.schema_migrations') AS t").fetchone()['t']
        if not exists:
            c.execute((Path(__file__).parent.parent / 'migrations/001_initial.sql').read_text())
        elif c.execute('SELECT max(version) AS v FROM schema_migrations').fetchone()['v'] != 1:
            raise RuntimeError('Unsupported database schema')

def lock(c):
    c.execute('SELECT pg_advisory_xact_lock(714006)')

def state(c, for_update=True):
    row = c.execute('SELECT state FROM casino WHERE id=%s' + (' FOR UPDATE' if for_update else ''), ('premier',)).fetchone()
    if not row:
        raise RuntimeError('Run python -m app.bootstrap first')
    return row['state']

def save(c, s):
    c.execute('UPDATE casino SET state=%s WHERE id=%s', (Jsonb(s), 'premier'))
