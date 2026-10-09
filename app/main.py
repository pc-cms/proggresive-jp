import asyncio
import csv
import io
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg import IntegrityError
from pydantic import BaseModel, ConfigDict, Field
from .db import connection, migrate, lock, state, save
from .security import authenticate, login, digest, uid, now, issue, fail
from .engine import execute, journal, text, canonical, business_date

@asynccontextmanager
async def lifespan(app):
    migrate()
    yield

app=FastAPI(title='Premier Progressive',version='1.0.0-test',lifespan=lifespan)

@app.middleware('http')
async def headers(request:Request,call_next):
    # Only local reverse proxy may be trusted; uvicorn trusts 127.0.0.1 by default.
    if request.url.path.startswith('/api/') and os.environ.get('REQUIRE_TLS','1')=='1' and request.url.scheme!='https':
        return Response('HTTPS required',status_code=426)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-src 'self'; frame-ancestors 'self'"
    return response

class Strict(BaseModel): model_config=ConfigDict(extra='forbid',strict=True)
class Login(Strict): name:str=Field(max_length=80); password:str=Field(max_length=200)
class Pair(Strict): code:str=Field(max_length=128); name:str=Field(max_length=80); app_version:str=Field(max_length=40); table_id:str|None=Field(default=None,pattern=r"^[0-9a-f]{32}$")
class Command(Strict): command_id:str=Field(max_length=128); op:str=Field(max_length=80); payload:dict; operator_id:str|None=None; sequence:int|None=Field(default=None,ge=1)
class Lease(Strict): operator_id:str=Field(min_length=16,max_length=128)
class Metadata(Strict): winner_name:str|None=Field(default=None,max_length=120); cms_player_id:str|None=Field(default=None,max_length=120); note:str|None=Field(default=None,max_length=500)

def actor(authorization:str=Header(default=''),x_premier_table:str|None=Header(default=None)):
    if not authorization.startswith('Bearer '): fail(401,'Bearer token required')
    principal=authenticate(authorization[7:])
    if x_premier_table is not None and principal['role']=='device' and principal['table_id']!=x_premier_table:
        fail(403,'Device is bound to another table; use that table URL or pair this kiosk')
    return principal

def read_access(a):
    if a['role'] not in ('admin','pit','device','cms_read','cms_metadata'): fail(403,'No read scope')

def view(s,a):
    from .baccarat import empty
    tables=[{**t,'baccarat':t.get('baccarat',empty()),'kiosk_path':f"/table/{t['id']}"} for t in s['tables'].values()]
    rounds=list(s['rounds'].values())
    claims=list(s['claims'].values())
    if a['role']=='device':
        tables=[{**t,'device_sequence':t.get('device_sequences',{}).get(a['id'],0)} for t in tables if t['id']==a['table_id']]
        rounds=[r for r in rounds if r['table_id']==a['table_id'] and r['status']=='confirmed']
        claims=[{k:v for k,v in x.items() if k not in ('winner_name','cms_player_id','note','approvals')} for x in claims if x['table_id']==a['table_id']]
    return {'casino_id':s['casino_id'],'environment':s['environment'],'production_released':False,'config':s['config'],'pools':s['pools'],'tables':tables,'rounds':rounds,'claims':claims,'server_time':now().isoformat(),'business_date':business_date(now())}

@app.get('/health')
def health():
    with connection() as c: c.execute('SELECT 1')
    return {'status':'ok','version':'1.0.0-test'}

@app.post('/api/v1/login')
def signin(body:Login): return login(body.name,body.password)

@app.post('/api/v1/logout')
def signout(a=Depends(actor)):
    with connection() as c: c.execute('DELETE FROM sessions WHERE token_hash=%s',(a['token_hash'],))
    return {'logged_out':True}

@app.post('/api/v1/pair')
def pair(body:Pair):
    with connection() as c:
        lock(c); s=state(c)
        row=c.execute('DELETE FROM pairing WHERE code_hash=%s AND expires_at>now() RETURNING table_id',(digest(body.code),)).fetchone()
        if not row: fail(401,'Pairing code invalid or expired')
        if body.table_id is not None and row['table_id']!=body.table_id:
            fail(409,'Pairing code belongs to another table; code was not consumed')
        if c.execute("SELECT 1 FROM principals WHERE table_id=%s AND role='device' AND active",(row['table_id'],)).fetchone(): fail(409,'Revoke existing device before pairing replacement')
        pid=uid()
        c.execute("INSERT INTO principals(id,name,role,table_id) VALUES(%s,%s,'device',%s)",(pid,text(body.name,80),row['table_id']))
        token=issue(c,pid,365)
        c.execute('UPDATE sessions SET app_version=%s WHERE token_hash=%s',(body.app_version,digest(token)))
        journal(c,'device_paired',pid,s,{'device_id':pid,'app_version':body.app_version},row['table_id'])
        return {'device_id':pid,'table_id':row['table_id'],'token':token}

@app.post('/api/v1/operator')
def lease(body:Lease,a=Depends(actor)):
    if a['role']!='device': fail(403,'Device required')
    with connection() as c:
        lock(c); s=state(c); t=s['tables'][a['table_id']]
        old=t.get('operator')
        if old and old['id']!=body.operator_id and datetime.fromisoformat(old['until'])>now(): fail(409,'Another operator controls this table')
        t['operator']={'id':body.operator_id,'until':(now()+timedelta(seconds=15)).isoformat()}; save(c,s)
        return {'lease_seconds':15}

@app.post('/api/v1/commands')
def command(body:Command,a=Depends(actor)):
    # Lease validation and mutation share the same transaction lock via execute.
    payload=dict(body.payload)
    if a['role']=='device':
        payload['_operator_id']=body.operator_id
        payload['_sequence']=body.sequence
    try: return execute(a,body.command_id,body.op,payload)
    except IntegrityError as e: raise HTTPException(409,'Conflicting identity or database constraint') from e
    except (KeyError,TypeError,ValueError) as e: raise HTTPException(422,'Malformed command payload') from e

@app.get('/api/v1/commands/{command_id}')
def command_status(command_id:str,a=Depends(actor)):
    with connection() as c: row=c.execute('SELECT response FROM commands WHERE id=%s AND principal_id=%s',(command_id,a['id'])).fetchone()
    if not row: fail(404,'Command not committed')
    return row['response']

@app.get('/api/v1/state')
def snapshot(a=Depends(actor)):
    read_access(a)
    with connection() as c: return view(state(c,False),a)

@app.get('/api/v1/tables')
def tables(a=Depends(actor)): return snapshot(a)['tables']
@app.get('/api/v1/pools')
def pools(a=Depends(actor)): return snapshot(a)['pools']
@app.get('/api/v1/wins')
def wins(a=Depends(actor)): return [x for x in snapshot(a)['claims'] if x['status']=='approved']

@app.get('/api/v1/devices')
def devices(a=Depends(actor)):
    if a['role']!='admin': fail(403,'Administrator required')
    with connection() as c:
        return c.execute("SELECT p.id,p.name,p.table_id,p.active,max(s.last_seen) AS last_seen,max(s.app_version) AS app_version FROM principals p LEFT JOIN sessions s ON s.principal_id=p.id WHERE p.role='device' GROUP BY p.id").fetchall()

@app.patch('/api/v1/wins/{win_id}/metadata')
def metadata(win_id:str,body:Metadata,a=Depends(actor)):
    if a['role'] not in ('admin','cms_metadata'): fail(403,'winner metadata write scope required')
    with connection() as c:
        lock(c); s=state(c); claim=next((x for x in s['claims'].values() if x.get('win_id')==win_id),None)
        if not claim: fail(404,'Win not found')
        update=body.model_dump(exclude_unset=True); before={k:claim.get(k) for k in update}; claim.update(update)
        journal(c,'winner_metadata_updated',a['id'],s,{'win_id':win_id,'before':before,'after':update},claim['table_id'],claim['round_id']); save(c,s)
        return {k:claim.get(k) for k in ('win_id','winner_name','cms_player_id','note')}

@app.get('/api/v1/events')
def events(after:int=0,limit:int=100,a=Depends(actor)):
    if a['role'] not in ('admin','pit','cms_read','cms_metadata'): fail(403,'Journal read scope required')
    if after<0 or not 1<=limit<=1000: fail(422,'Invalid cursor/limit')
    with connection() as c: return c.execute('SELECT * FROM events WHERE seq>%s ORDER BY seq LIMIT %s',(after,limit)).fetchall()

@app.get('/api/v1/stream')
def stream(request:Request,after:int=0,a=Depends(actor)):
    read_access(a)
    def read_batch(cursor):
        # Blocking PostgreSQL work runs outside the event loop. Read snapshots
        # do not lock the financial aggregate; persisted journal is the outbox.
        authenticate(request.headers.get('authorization','')[7:])
        with connection() as c:
            c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            s=state(c,False)
            rows=c.execute("SELECT seq,payload FROM events WHERE seq>%s AND kind='win_approved' ORDER BY seq LIMIT 100",(cursor,)).fetchall()
            latest=c.execute('SELECT coalesce(max(seq),0) AS seq FROM events').fetchone()['seq']
        return s, rows, latest
    async def generate():
        cursor=max(0,after)
        while not await request.is_disconnected():
            try: s,rows,latest=await asyncio.to_thread(read_batch,cursor)
            except HTTPException: break
            for row in rows:
                cursor=row['seq']; data=row['payload']
                if datetime.fromisoformat(data['show_until'])>now():
                    yield f"id: {cursor}\nevent: winner\ndata: {canonical(data)}\n\n"
            if len(rows)<100: cursor=latest
            yield f"event: state\ndata: {canonical(view(s,a))}\n\n"
            await asyncio.sleep(0.2)
    return StreamingResponse(generate(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})

@app.get('/api/v1/reports')
def report(start:str,end:str,table_id:str|None=None,format:str='json',a=Depends(actor)):
    if a['role'] not in ('admin','pit','cms_read','cms_metadata'): fail(403,'Report scope required')
    try:
        d1=datetime.fromisoformat(start).date(); d2=datetime.fromisoformat(end).date()
    except ValueError: fail(422,'ISO business dates required')
    if d2<d1 or (d2-d1).days>3660: fail(422,'Invalid reporting interval')
    with connection() as c:
        allrows=c.execute('SELECT kind,payload,table_id,round_id,business_date FROM events WHERE business_date<=%s ORDER BY seq',(d2,)).fetchall()
        s=state(c)
    other_opening=0; other_closing=0
    opening={str(i):0 for i in range(1,6)}; closing=opening.copy(); period=[]
    for row in allrows:
        payload=row['payload']; other_delta=0
        if row['kind']=='round_confirmed': other_delta=payload['stake']-sum(payload['pool_delta'].values())
        if row['kind']=='round_reversed': other_delta=-payload['stake_reversed']-sum(payload['pool_delta'].values())
        other_closing+=other_delta
        if row['business_date']<d1:
            other_opening+=other_delta
            for k,v in row['payload'].get('pool_delta',{}).items(): opening[k]+=v
        for k,v in row['payload'].get('pool_delta',{}).items(): closing[k]+=v
        if row['business_date']>=d1 and (not table_id or row['table_id']==table_id): period.append(row)
    # Opening/closing always casino-wide. Table delta is an attribution, not an owned pool.
    totals={'non_jackpot_allocated':0,'non_jackpot_reversed':0,'bets_reversed':0,'rounds_confirmed':0,'rounds_closed':0,'zero_participation':0,'boxes':0,'stake':0,'reversals':0,'stake_reversed':0,'claims_created':0,'claims_rejected':0,'wins_approved':0,'payout_amount':0,'actually_paid':0,'pool_debit':0,'restoration':0,'house_shortfall':0,'initial_funding':0}
    contributions={str(i):0 for i in range(1,6)}; adjustments=contributions.copy(); reversals=contributions.copy()
    baccarat={'recorded':0,'undone':0,'net':0,'player':0,'banker':0,'tie':0,'player_pairs':0,'banker_pairs':0}
    for row in period:
        p=row['payload']; k=row['kind']
        if k in ('baccarat_result','baccarat_undo'):
            sign=1 if k=='baccarat_result' else -1
            hand=p.get('last_hand') if sign==1 else p.get('removed_hand')
            baccarat['recorded' if sign==1 else 'undone']+=1; baccarat['net']+=sign
            if hand:
                baccarat[{'P':'player','B':'banker','T':'tie'}[hand['outcome']]]+=sign
                baccarat['player_pairs']+=sign*int(hand['playerPair']); baccarat['banker_pairs']+=sign*int(hand['bankerPair'])
        if k=='initialized': totals['initial_funding']+=p['initial_funding']
        if k=='round_confirmed':
            totals['rounds_confirmed']+=1; totals['boxes']+=len(p['boxes']); totals['stake']+=p['stake']
            totals['non_jackpot_allocated']+=p['stake']-sum(p['pool_delta'].values())
            for tier,v in p['pool_delta'].items(): contributions[tier]+=v
        if k=='round_closed': totals['rounds_closed']+=1; totals['zero_participation']+=int(p['zero_participation'])
        if k=='round_reversed':
            totals['reversals']+=1; totals['stake_reversed']+=p['stake_reversed']
            totals['non_jackpot_reversed']+=p['stake_reversed']+sum(p['pool_delta'].values())
            totals['bets_reversed']+=len(s['rounds'][row['round_id']]['boxes'])
            for tier,v in p['pool_delta'].items(): reversals[tier]+=v
        if k=='adjust':
            for tier,v in p['pool_delta'].items(): adjustments[tier]+=v
        if k=='claim_created': totals['claims_created']+=1
        if k=='reject': totals['claims_rejected']+=1
        if k=='win_approved':
            totals['wins_approved']+=1
            for key,target in [('amount','payout_amount'),('pool_debit','pool_debit'),('restoration','restoration'),('house_shortfall','house_shortfall')]: totals[target]+=p[key]
        if k=='paid': totals['actually_paid']+=s['claims'][p['claim_id']]['amount']
    totals['bets_net']=totals['boxes']-totals['bets_reversed']
    other={'casino_opening':other_opening,'casino_closing':other_closing,'allocated':totals['non_jackpot_allocated'],'reversed':totals['non_jackpot_reversed'],'net':totals['non_jackpot_allocated']-totals['non_jackpot_reversed']}
    statuses={status:sum(x['status']==status and d1.isoformat()<=x['business_date']<=d2.isoformat() and (not table_id or x['table_id']==table_id) for x in s['claims'].values()) for status in ('pending','disputed','approved','rejected')}
    result={'start':d1.isoformat(),'end':d2.isoformat(),'table_id':table_id,'totals':totals,'contributions':contributions,'reversals':reversals,'adjustments':adjustments,'baccarat':baccarat,'non_jackpot_pool':other,'claim_statuses_now':statuses,'casino_opening':opening,'casino_closing':closing,'scope_note':'Shared pool balances are casino-wide; table figures attribute flows only.'}
    if format=='json': return result
    if format!='csv': fail(422,'format must be json/csv')
    out=io.StringIO(); writer=csv.writer(out); writer.writerow(['metric','value'])
    for category,values in result.items():
        if isinstance(values,dict):
            for k,v in values.items(): writer.writerow([f'{category}.{k}',v])
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=progressive-report.csv'})

WEB=Path(__file__).parent.parent/'web'
app.mount('/static',StaticFiles(directory=WEB),name='static')
@app.get('/')
def index(): return FileResponse(WEB/'terminal.html')
@app.get('/table/{table_id}')
def kiosk(table_id:str):
    if not re.fullmatch(r'[0-9a-f]{32}',table_id): fail(404,'Table not found')
    with connection() as c:
        if table_id not in state(c,False)['tables']: fail(404,'Table not found')
    return FileResponse(WEB/'terminal.html')

@app.get('/admin')
def administration(): return FileResponse(WEB/'admin.html')
