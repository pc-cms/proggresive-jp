"""All mutations are serialized under one PostgreSQL transaction per casino.
Pending claims pause only their table; payout approvals execute sequentially.
No reservation or lost contribution: rejected commands never accept stakes.
"""
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from psycopg.types.json import Jsonb
from .db import connection, lock, state, save
from .security import uid, now, fail, digest, PH, issue

def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'))
def business_date(dt): return (dt.astimezone(ZoneInfo('Africa/Dar_es_Salaam'))-timedelta(hours=7)).date().isoformat()
def journal(c,kind,actor,s,payload,table_id=None,round_id=None):
    previous=c.execute('SELECT hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
    prev=previous['hash'] if previous else '0'*64
    event={'id':uid(),'casino_id':s['casino_id'],'kind':kind,'actor':actor,'table_id':table_id,'round_id':round_id,'business_date':business_date(now()),'occurred_at':now().isoformat(),'payload':payload,'previous_hash':prev}
    h=hashlib.sha256(canonical(event).encode()).hexdigest()
    seq=c.execute('INSERT INTO events(id,casino_id,kind,actor,table_id,round_id,business_date,occurred_at,payload,previous_hash,hash) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING seq',(event['id'],event['casino_id'],kind,actor,table_id,round_id,event['business_date'],event['occurred_at'],Jsonb(payload),prev,h)).fetchone()['seq']
    return seq

def integer(v,low=0,high=10**12):
    if type(v) is not int or not low<=v<=high: fail(422,'Expected an integer in range')
    return v

def text(v,limit=200):
    if not isinstance(v,str) or not v.strip() or len(v)>limit: fail(422,'Required text missing or too long')
    return v.strip()

def reason(p): return text(p.get('reason'))
def admin(a):
    if a['role']!='admin': fail(403,'Administrator authority required')
def pending(s): return [x for x in s['claims'].values() if x['status'] in ('pending','disputed')]
def no_pending(s,table_id=None):
    if any(table_id is None or x['table_id']==table_id for x in pending(s)): fail(409,'Pending/disputed claims: financial changes paused; no stakes accepted')

def table(s,a,p):
    tid=p.get('table_id') or a.get('table_id')
    t=s['tables'].get(tid)
    if not t: fail(404,'Table not found')
    if a['role']=='device' and a['table_id']!=tid: fail(403,'Device belongs to another table')
    if a['role'] not in ('device','admin','pit'): fail(403,'Table operation not allowed')
    return t

def current(s,t,p):
    r=s['rounds'].get(t.get('round_id'))
    if not r or r['id']!=p.get('round_id') or r['status']!='confirmed': fail(409,'Round is not current/confirmed')
    return r

def approve(c,s,a,claim):
    if claim['status']=='approved':
        if a['role'] not in ('admin','pit'): fail(403,'Approval authority required')
        return claim
    if claim['status']!='pending': fail(409,'Claim requires review; automatic payout blocked')
    policy=claim['conditions']['approval']
    approvals=claim['approvals']
    if policy=='admin': admin(a)
    elif policy=='pit':
        if a['role'] not in ('pit','admin'): fail(403,'Pit authority required')
    elif policy=='pit_admin':
        if not approvals:
            if a['role']!='pit': fail(403,'First approval must be from pit')
            approvals.append(a['id'])
            journal(c,'claim_stage_approved',a['id'],s,{'claim_id':claim['id'],'stage':'pit'},claim['table_id'],claim['round_id'])
            return claim
        admin(a)
        if a['id'] in approvals: fail(403,'Separate administrator required')
    elif a['role'] not in ('device','admin','pit'): fail(403,'Approval denied')
    tier=str(claim['tier']); before=s['pools'][tier]; cfg=claim['conditions']
    if claim['type']=='progressive':
        amount=before; debit=before; reset=cfg['seed']; shortfall=0; after=reset
    else:
        amount=cfg['fixed']; debit=min(amount,max(0,before-cfg['seed'])); reset=0; shortfall=amount-debit; after=before-debit
    s['pools'][tier]=after
    start=max(now()+timedelta(seconds=2),datetime.fromisoformat(s['announcement_end']) if s['announcement_end'] else now())
    end=start+timedelta(seconds=s['config']['announcement_seconds'])
    s['announcement_end']=end.isoformat()
    claim.update(status='approved',win_id=uid(),amount=amount,pool_before=before,pool_after=after,pool_debit=debit,restoration=reset,house_shortfall=shortfall,approved_by=a['id'],approved_at=now().isoformat(),business_date=business_date(now()),payout_status='unpaid',show_at=start.isoformat(),show_until=end.isoformat())
    approvals.append(a['id'])
    if claim['type']=='progressive': s.setdefault('last_progressive',{})[tier]=claim['created_at']
    payload={k:claim[k] for k in ('win_id','table_id','round_id','box','tier','type','amount','pool_before','pool_after','pool_debit','restoration','house_shortfall','show_at','show_until')}
    payload['table_number']=s['tables'][claim['table_id']]['number']
    payload['table_name']=s['tables'][claim['table_id']]['name']
    payload['pool_delta']={tier:after-before}
    journal(c,'win_approved',a['id'],s,payload,claim['table_id'],claim['round_id'])
    return claim

def execute(actor,command_id,op,p):
    text(command_id,128)
    if actor['role'] in ('cms_read','cms_metadata'): fail(403,'Integration credentials cannot execute commands')
    fingerprint=digest(canonical({'op':op,'payload':{k:v for k,v in p.items() if k!='_operator_id'}}))
    with connection() as c:
        lock(c)
        active=c.execute('SELECT 1 FROM sessions s JOIN principals p ON p.id=s.principal_id WHERE s.token_hash=%s AND p.id=%s AND p.active AND s.expires_at>now()', (actor['token_hash'],actor['id'])).fetchone()
        if not active: fail(401,'Credentials revoked or expired')
        old=c.execute('SELECT * FROM commands WHERE id=%s',(command_id,)).fetchone()
        if old:
            if old['principal_id']!=actor['id'] or old['request_hash']!=fingerprint: fail(409,'command_id already used for different intent')
            return old['response']
        s=state(c)
        if actor['role']=='device':
            lease=s['tables'][actor['table_id']].get('operator')
            if not lease or lease['id']!=p.get('_operator_id') or datetime.fromisoformat(lease['until'])<=now(): fail(409,'Active operator lease required')
        if actor['role']=='device':
            expected=s['tables'][actor['table_id']].get('device_sequences',{}).get(actor['id'],0)+1
            if p.get('_sequence')!=expected: fail(409,'sequence mismatch; fetch authoritative state')
        result=dispatch(c,s,actor,op,p)
        if actor['role']=='device': s['tables'][actor['table_id']].setdefault('device_sequences',{})[actor['id']]=p['_sequence']
        save(c,s)
        response={'command_id':command_id,'result':result,'acknowledgment':{'sequence':p.get('_sequence'),'committed':True}}
        c.execute('INSERT INTO commands(id,principal_id,request_hash,response) VALUES(%s,%s,%s,%s)',(command_id,actor['id'],fingerprint,Jsonb(response)))
        return response

def dispatch(c,s,a,op,p):
    if op=='table_register':
        admin(a); tid=uid(); number=text(p.get('number'),32)
        if any(t['number']==number for t in s['tables'].values()): fail(409,'Table number already exists')
        game=p.get('game','poker')
        if game not in ('poker','baccarat'): fail(422,'Choose poker or baccarat table')
        t={'id':tid,'casino_id':s['casino_id'],'number':number,'name':text(p.get('name')),'game':game,'boxes':integer(p.get('boxes',7),1,32),'active':True,'minimum':integer(p.get('minimum',0)),'maximum':integer(p.get('maximum',0)),'modes':['progressive','baccarat'],'mode':'baccarat' if game=='baccarat' else 'progressive','next_round_id':uid(),'round_id':None,'kiosk_path':f'/table/{tid}'}
        s['tables'][tid]=t; journal(c,op,a['id'],s,t,tid); return t
    if op=='table_update':
        admin(a); t=table(s,a,p)
        if 'game' in p and p['game']!=t['game']: fail(409,'Register a separate table for another game')
        for k in ('name',):
            if k in p: t[k]=text(p[k])
        if any(k in p for k in ('minimum','maximum')): t['limits_version']=t.get('limits_version',1)+1
        for k in ('minimum','maximum'):
            if k in p: t[k]=integer(p[k])
        if 'modes' in p:
            modes=p['modes']
            if not isinstance(modes,list) or not modes or any(m not in ('progressive','baccarat') for m in modes) or len(set(modes))!=len(modes): fail(422,'Invalid display modes')
            if t['mode'] not in modes: fail(409,'Switch mode before disabling it')
            t['modes']=modes
        if 'active' in p:
            if type(p['active']) is not bool: fail(422,'active must be boolean')
            t['active']=p['active']
        if 'boxes' in p:
            if t['round_id']: fail(409,'Cannot change boxes during round')
            t['boxes']=integer(p['boxes'],1,32)
        journal(c,op,a['id'],s,p,t['id']); return t
    if op=='pair_create':
        admin(a); t=table(s,a,p); code=uid()
        c.execute('INSERT INTO pairing VALUES(%s,%s,%s)',(digest(code),t['id'],now()+timedelta(minutes=10)))
        journal(c,op,a['id'],s,{'expires_in':600},t['id']); return {'pairing_code':code,'expires_in':600}
    if op=='device_revoke':
        admin(a); did=text(p.get('device_id')); reason(p)
        row=c.execute("UPDATE principals SET active=false WHERE id=%s AND role='device' RETURNING table_id",(did,)).fetchone()
        if not row: fail(404,'Device not found')
        journal(c,op,a['id'],s,{'device_id':did,'reason':p['reason']},row['table_id']); return {'revoked':did}
    if op=='principal_create':
        admin(a); role=p.get('role')
        if role not in ('admin','pit','cms_read','cms_metadata'): fail(422,'Invalid role')
        name=text(p.get('name'),80)
        password=p.get('password')
        if role in ('admin','pit') and (not isinstance(password,str) or len(password)<12): fail(422,'Password must be at least 12 characters')
        pid=uid(); c.execute('INSERT INTO principals(id,name,password_hash,role) VALUES(%s,%s,%s,%s)',(pid,name,PH.hash(password) if password else None,role))
        journal(c,op,a['id'],s,{'principal_id':pid,'name':name,'role':role})
        return {'id':pid,'role':role,'token':issue(c,pid,365) if role.startswith('cms_') else None}
    if op=='principal_revoke':
        admin(a); pid=text(p.get('principal_id')); reason(p)
        row=c.execute('SELECT * FROM principals WHERE id=%s AND active',(pid,)).fetchone()
        if not row: fail(404,'Active principal not found')
        if row['id']==a['id']: fail(409,'Self-revocation forbidden')
        if row['role']=='admin' and c.execute("SELECT count(*) AS n FROM principals WHERE active AND role='admin'").fetchone()['n']<=1: fail(409,'Cannot revoke last administrator')
        c.execute('UPDATE principals SET active=false WHERE id=%s',(pid,))
        journal(c,op,a['id'],s,{'principal_id':pid,'reason':p['reason']}); return {'revoked':pid}
    if op=='config_update':
        admin(a); no_pending(s)
        cfg=copy.deepcopy(p.get('config'))
        if not isinstance(cfg,dict) or set(cfg)!= {'stake','tiers','announcement_seconds'}: fail(422,'Complete financial configuration required')
        integer(cfg['stake'],1); integer(cfg['announcement_seconds'],1,120)
        if not isinstance(cfg['tiers'],list) or len(cfg['tiers'])!=5: fail(422,'Five tiers required')
        if {t.get('code') for t in cfg['tiers']}!={1,2,3,4,5}: fail(422,'Tier codes must be 1–5')
        for t in cfg['tiers']:
            integer(t['code'],1,5); text(t['name']); integer(t['seed'],1); integer(t['contribution']); integer(t['fixed'],1)
            if t['approval'] not in ('none','pit','admin','pit_admin'): fail(422,'Invalid policy')
            if t['code']>=3 and t['approval'] not in ('pit','admin','pit_admin'): fail(422,'Upper tiers require PIT/Admin')
        if sum(t['contribution'] for t in cfg['tiers'])>cfg['stake']: fail(422,'Contributions exceed stake')
        cfg.update(version=s['config']['version']+1,engine=s['config']['engine']); s['config']=cfg
        journal(c,op,a['id'],s,{'config':cfg,'reason':reason(p)}); return cfg
    if op=='adjust':
        admin(a); no_pending(s); tier=str(integer(p.get('tier'),1,5)); delta=integer(p.get('delta'),-10**12,10**12)
        if s['pools'][tier]+delta<0: fail(409,'Negative pool prohibited')
        s['pools'][tier]+=delta; journal(c,op,a['id'],s,{'pool_delta':{tier:delta},'reason':reason(p)}); return s['pools']
    if op in ('approve','reject','paid','metadata'):
        claim=s['claims'].get(p.get('claim_id'))
        if not claim: fail(404,'Claim not found')
        if op=='approve': return approve(c,s,a,claim)
        if op=='reject':
            admin(a)
            if claim['status'] not in ('pending','disputed'): fail(409,'Claim already resolved')
            claim.update(status='rejected',rejected_by=a['id'],rejection_reason=reason(p))
        if op=='paid':
            admin(a)
            if claim['status']!='approved': fail(409,'Not approved')
            if claim['payout_status']=='paid': return claim
            claim.update(payout_status='paid',paid_by=a['id'],paid_at=now().isoformat(),payment_reference=text(p.get('reference')))
        if op=='metadata': fail(422,'Use dedicated metadata endpoint')
        journal(c,op,a['id'],s,{'claim_id':claim['id'],'reason':p.get('reason'),'reference':p.get('reference')},claim['table_id'],claim['round_id']); return claim
    t=table(s,a,p)
    if op.startswith('baccarat_'):
        if not t['active']: fail(409,'Table disabled')
        if t['mode']!='baccarat': fail(409,'Switch to Baccarat before recording results')
        from .baccarat import mutate
        removed=copy.deepcopy(t.get('baccarat',{}).get('hands',[None])[-1]) if op=='baccarat_undo' and t.get('baccarat',{}).get('hands') else None
        result=mutate(t,op,p,a['id'])
        journal(c,op,a['id'],s,{'revision':result['revision'],'shoe':result['shoe'],'hand_count':len(result['hands']),'payload':p,'removed_hand':removed,'last_hand':result['hands'][-1] if result['hands'] else None},t['id'])
        return result
    if op=='mode':
        mode=p.get('mode')
        if mode not in t['modes']: fail(409,'Mode unavailable for this table')
        t['mode']=mode; journal(c,op,a['id'],s,{'mode':mode},t['id']); return t
    if op=='claims':
        r=current(s,t,p); boxes=p.get('boxes')
        if not isinstance(boxes,list) or not boxes: fail(422,'Choose winning boxes')
        for box in boxes: integer(box,1,t['boxes'])
        if len(set(boxes))!=len(boxes): fail(422,'Unique winning boxes required')
        # One transaction/intent for all boxes; a later invalid claim rolls back all.
        claims=[dispatch(c,s,a,'claim',{**p,'box':box}) for box in sorted(boxes)]
        return {'claims':claims}
    if op=='confirm':
        if t['game']!='poker': fail(409,'Baccarat table cannot accept Progressive wagers')
        no_pending(s,t['id'])
        if not t['active']: fail(409,'Table disabled')
        if t['round_id'] or p.get('round_id')!=t['next_round_id']: fail(409,'Stale/already confirmed round')
        boxes=p.get('boxes')
        if not isinstance(boxes,list) or len(set(boxes))!=len(boxes): fail(422,'Unique boxes required')
        for box in boxes: integer(box,1,t['boxes'])
        cfg=copy.deepcopy(s['config']); rid=t['next_round_id']; delta={str(x['code']):x['contribution']*len(boxes) for x in cfg['tiers']}
        for k,v in delta.items(): s['pools'][k]+=v
        r={'id':rid,'table_id':t['id'],'device_id':a['id'] if a['role']=='device' else None,'actor':a['id'],'boxes':sorted(boxes),'status':'confirmed','conditions':cfg,'created_at':now().isoformat(),'business_date':business_date(now()),'stake':cfg['stake']*len(boxes),'contributions':delta}
        s['rounds'][rid]=r; t['round_id']=rid
        journal(c,'round_confirmed',a['id'],s,{'boxes':r['boxes'],'stake':r['stake'],'config_version':cfg['version'],'pool_delta':delta},t['id'],rid); return r
    if op=='close':
        r=current(s,t,p)
        if any(x['round_id']==r['id'] and x['status'] in ('pending','disputed') for x in s['claims'].values()): fail(409,'Resolve claims first')
        r['status']='closed'; r['closed_at']=now().isoformat(); t['round_id']=None; t['next_round_id']=uid()
        journal(c,'round_closed',a['id'],s,{'zero_participation':not r['boxes']},t['id'],r['id']); return r
    if op=='reverse':
        admin(a); no_pending(s,t['id']); r=current(s,t,p); reason(p)
        if any(x['round_id']==r['id'] and x['status']=='approved' for x in s['claims'].values()): fail(409,'Paid/approved round needs controlled correction')
        # No reversal across a later payout or adjustment: contribution cannot be recovered twice.
        if c.execute("SELECT 1 FROM events WHERE kind IN ('win_approved','adjust') AND occurred_at>%s LIMIT 1",(r['created_at'],)).fetchone(): fail(409,'Subsequent pool operation: controlled correction required')
        delta={k:-v for k,v in r['contributions'].items()}
        if any(s['pools'][k]+v<0 for k,v in delta.items()): fail(409,'Insufficient pool')
        for k,v in delta.items(): s['pools'][k]+=v
        r['status']='reversed'; t['round_id']=None; t['next_round_id']=uid()
        journal(c,'round_reversed',a['id'],s,{'pool_delta':delta,'stake_reversed':r['stake'],'reason':p['reason']},t['id'],r['id']); return r
    if op=='claim':
        r=current(s,t,p); box=integer(p.get('box'),1,t['boxes']); tier=integer(p.get('tier'),1,5); kind=p.get('type')
        if box not in r['boxes']: fail(409,'Box did not participate')
        if kind not in ('progressive','fixed'): fail(422,'Choose progressive/fixed')
        if any(x['round_id']==r['id'] and x['box']==box and x['status']!='rejected' for x in s['claims'].values()): fail(409,'Box already has a claim: choose only its highest combination; rejected claims may be corrected')
        cfg=copy.deepcopy(next(x for x in r['conditions']['tiers'] if x['code']==tier))
        claim={'id':uid(),'casino_id':s['casino_id'],'table_id':t['id'],'device_id':a['id'] if a['role']=='device' else None,'round_id':r['id'],'box':box,'tier':tier,'type':kind,'status':'pending','conditions':cfg,'created_at':now().isoformat(),'business_date':business_date(now()),'claimed_by':a['id'],'approvals':[],'conflicts':[]}
        s['claims'][claim['id']]=claim
        journal(c,'claim_created',a['id'],s,{'claim_id':claim['id'],'box':box,'tier':tier,'type':kind,'status':claim['status'],'conflicts':claim['conflicts']},t['id'],r['id'])
        if cfg['approval']=='none': approve(c,s,a,claim)
        return claim
    fail(404,'Unknown command')
