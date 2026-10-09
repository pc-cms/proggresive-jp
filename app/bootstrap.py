import getpass
from psycopg.types.json import Jsonb
from .db import connection, migrate, lock
from .security import PH, uid

TIERS = [
 {'code':1,'name':'Flush','seed':200000,'contribution':35,'fixed':25000,'approval':'none'},
 {'code':2,'name':'Full House','seed':500000,'contribution':45,'fixed':50000,'approval':'none'},
 {'code':3,'name':'Four of a Kind','seed':1000000,'contribution':70,'fixed':200000,'approval':'pit'},
 {'code':4,'name':'Straight Flush','seed':5000000,'contribution':130,'fixed':500000,'approval':'pit'},
 {'code':5,'name':'Royal Flush','seed':12500000,'contribution':220,'fixed':1000000,'approval':'pit'}]

def initialize(password, name='admin'):
    if len(password)<12: raise ValueError('Use a unique password of at least 12 characters')
    migrate()
    with connection() as c:
        lock(c)
        if c.execute('SELECT id FROM casino').fetchone(): raise ValueError('Already initialized; database left unchanged')
        config={'version':1,'stake':5000,'tiers':TIERS,'announcement_seconds':12,'engine':'premier-progressive-2026-09-11-v1'}
        s={'casino_id':'premier','environment':'test','config':config,'pools':{str(t['code']):t['seed'] for t in TIERS},'tables':{},'rounds':{},'claims':{},'announcement_end':None}
        c.execute('INSERT INTO casino VALUES(%s,%s)',('premier',Jsonb(s)))
        actor=uid()
        c.execute('INSERT INTO principals(id,name,password_hash,role) VALUES(%s,%s,%s,%s)',(actor,name,PH.hash(password),'admin'))
        from .engine import journal
        journal(c,'initialized',actor,s,{'pool_delta':s['pools'],'initial_funding':19200000})

if __name__=='__main__':
    initialize(getpass.getpass('Unique administrator password (min 12 characters): '))
    print('Initialized TEST casino. Production release gate remains closed; see docs/RELEASE_GATE.md.')
