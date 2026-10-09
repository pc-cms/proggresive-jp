import copy
import hashlib
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import connection
from app.engine import business_date,canonical

def cmd(c,op,p={},cid=None): return c.post('/api/v1/commands',json={'command_id':cid or str(uuid.uuid4()),'op':op,'payload':p})
def ok(c,op,p={},cid=None):
    r=cmd(c,op,p,cid); assert r.status_code==200,r.text; return r.json()['result']
def state(c): return c.get('/api/v1/state').json()
def table(c,n='1'): return ok(c,'table_register',{'number':n,'name':'Table '+n})
def bets(c,t,boxes=[1]): return ok(c,'confirm',{'table_id':t['id'],'round_id':t['next_round_id'],'boxes':boxes})
def claim(c,t,r,tier=1,box=1,kind='fixed'): return ok(c,'claim',{'table_id':t['id'],'round_id':r['id'],'box':box,'tier':tier,'type':kind})
def device(c,t,name='device'):
    code=ok(c,'pair_create',{'table_id':t['id']})['pairing_code']
    credentials=c.post('/api/v1/pair',json={'code':code,'name':name,'app_version':'test'}).json()
    d=TestClient(app,base_url='https://testserver');d.headers['Authorization']='Bearer '+credentials['token'];return d,credentials

def test_one_box(env):
    t=table(env);r=bets(env,t);assert r['stake']==5000
    assert r['contributions']=={'1':35,'2':45,'3':70,'4':130,'5':220}

def test_seven_boxes(env):
    r=bets(env,table(env),list(range(1,8)));assert r['stake']==35000
    assert r['contributions']=={'1':245,'2':315,'3':490,'4':910,'5':1540}
    assert sum(r['contributions'].values())==3500

def test_idempotency_and_double_enter(env):
    t=table(env);p={'table_id':t['id'],'round_id':t['next_round_id'],'boxes':[1]};cid=str(uuid.uuid4())
    a=ok(env,'confirm',p,cid);assert ok(env,'confirm',p,cid)==a
    assert cmd(env,'confirm',p).status_code==409
    assert cmd(env,'confirm',{**p,'boxes':[2]},cid).status_code==409
    assert state(env)['pools']['5']==12500220

def test_two_tables_concurrent(env):
    a=table(env,'1');b=table(env,'2')
    with ThreadPoolExecutor(2) as pool: list(pool.map(lambda t:bets(env,t),[a,b]))
    assert state(env)['pools']['5']==12500440

def test_registration_does_not_seed(env):
    before=state(env)['pools'];table(env);table(env,'2');assert state(env)['pools']==before

def test_close_preserves_pools(env):
    t=table(env);r=bets(env,t);before=state(env)['pools'];ok(env,'close',{'table_id':t['id'],'round_id':r['id']});assert state(env)['pools']==before

def test_zero_round_statistics(env):
    t=table(env);r=bets(env,t,[]);ok(env,'close',{'table_id':t['id'],'round_id':r['id']});d=state(env)['business_date']
    stats=env.get('/api/v1/reports',params={'start':d,'end':d}).json()['totals']
    assert stats['rounds_confirmed']==1 and stats['zero_participation']==1 and stats['stake']==0

def test_nonparticipant(env):
    t=table(env);r=bets(env,t)
    assert cmd(env,'claim',{'table_id':t['id'],'round_id':r['id'],'box':2,'tier':1,'type':'fixed'}).status_code==409

@pytest.mark.parametrize('tier',[3,4,5])
def test_upper_tiers_require_admin(env,tier):
    t=table(env);r=bets(env,t);x=claim(env,t,r,tier);assert x['status']=='pending';before=state(env)['pools']
    d,_=device(env,t);d.post('/api/v1/operator',json={'operator_id':'operator-000000001'})
    res=d.post('/api/v1/commands',json={'command_id':str(uuid.uuid4()),'op':'approve','payload':{'claim_id':x['id']},'operator_id':'operator-000000001','sequence':1})
    assert res.status_code==403 and state(env)['pools']==before
    assert env.post('/api/v1/login',json={'name':'admin','password':'wrong'}).status_code==401
    assert state(env)['pools']==before
    assert not env.get('/api/v1/events').json()[-1]['kind']=='win_approved'

def test_progressive_reset_only_one(env):
    t=table(env);r=bets(env,t);before=state(env)['pools'];x=claim(env,t,r,5,kind='progressive');assert x['status']=='pending'
    win=ok(env,'approve',{'claim_id':x['id']});assert win['amount']==12500220
    after=state(env)['pools'];assert after['5']==12500000
    assert all(after[k]==v for k,v in before.items() if k!='5')
    assert win['restoration']==12500000 and win['pool_debit']==12500220

def test_fixed_funding(env):
    t=table(env);r=bets(env,t);x=claim(env,t,r)
    assert x['amount']==25000 and x['pool_debit']==35 and x['house_shortfall']==24965
    assert state(env)['pools']['1']==200000

def test_duplicate_approval_and_actual_payment(env):
    t=table(env);r=bets(env,t);x=claim(env,t,r,3);win=ok(env,'approve',{'claim_id':x['id']});before=state(env)['pools']
    assert ok(env,'approve',{'claim_id':x['id']})==win and state(env)['pools']==before
    assert win['payout_status']=='unpaid';ok(env,'paid',{'claim_id':x['id'],'reference':'cash receipt 1'})
    events=env.get('/api/v1/events').json();assert sum(e['kind']=='win_approved' for e in events)==1

def test_reversal_audit(env):
    t=table(env);r=bets(env,t);ok(env,'reverse',{'table_id':t['id'],'round_id':r['id'],'reason':'mistake'})
    assert state(env)['pools']['5']==12500000
    assert cmd(env,'reverse',{'table_id':t['id'],'round_id':r['id'],'reason':'again'}).status_code==409
    kinds=[e['kind'] for e in env.get('/api/v1/events').json()];assert 'round_confirmed' in kinds and 'round_reversed' in kinds

def test_paid_round_cannot_reverse(env):
    t=table(env);r=bets(env,t);claim(env,t,r)
    assert cmd(env,'reverse',{'table_id':t['id'],'round_id':r['id'],'reason':'bad'}).status_code==409

def test_restart_preserves_state(env):
    t=table(env);r=bets(env,t);claim(env,t,r,5);before=state(env)
    with TestClient(app,base_url='https://testserver',headers=dict(env.headers)) as restarted:
        after=state(restarted)
        for key in ('pools','rounds','claims','tables'): assert after[key]==before[key]

def test_device_lease_and_scope(env):
    t=table(env);other=table(env,'2');d,_=device(env,t)
    payload={'table_id':t['id'],'round_id':t['next_round_id'],'boxes':[1]}
    assert cmd(d,'confirm',payload).status_code==409
    assert d.post('/api/v1/operator',json={'operator_id':'operator-000000001'}).status_code==200
    assert d.post('/api/v1/operator',json={'operator_id':'operator-000000002'}).status_code==409
    assert d.post('/api/v1/commands',json={'command_id':str(uuid.uuid4()),'op':'confirm','payload':{**payload,'table_id':other['id']},'operator_id':'operator-000000001','sequence':1}).status_code==403

def test_business_day_boundary():
    assert business_date(datetime(2026,10,8,3,59,59,tzinfo=timezone.utc))=='2026-10-07'
    assert business_date(datetime(2026,10,8,4,0,0,tzinfo=timezone.utc))=='2026-10-08'

def test_cms_scopes_metadata_only(env):
    t=table(env);r=bets(env,t);x=claim(env,t,r)
    read=ok(env,'principal_create',{'name':'cms-reader','role':'cms_read'})
    meta=ok(env,'principal_create',{'name':'cms-writer','role':'cms_metadata'})
    c=TestClient(app,base_url='https://testserver');c.headers['Authorization']='Bearer '+read['token']
    assert c.get('/api/v1/pools').status_code==200
    assert cmd(c,'adjust',{'tier':1,'delta':1,'reason':'attack'}).status_code==403
    url='/api/v1/wins/'+x['win_id']+'/metadata'
    assert c.patch(url,json={'winner_name':'Jane'}).status_code==403
    c.headers['Authorization']='Bearer '+meta['token']
    assert c.patch(url,json={'winner_name':'Jane','cms_player_id':'123'}).status_code==200
    assert c.patch(url,json={'amount':999,'winner_name':'X'}).status_code==422
    assert state(env)['claims'][0]['amount']==25000

def test_same_tier_two_tables_paid_sequentially(env):
    t=table(env);u=table(env,'2');r=bets(env,t);q=bets(env,u);before=state(env)['pools']
    a=claim(env,t,r,5,kind='progressive');b=claim(env,u,q,5,kind='progressive')
    assert a['status']==b['status']=='pending'
    assert state(env)['pools']==before
    first=ok(env,'approve',{'claim_id':a['id']});second=ok(env,'approve',{'claim_id':b['id']})
    assert first['amount']==12500440 and second['amount']==12500000
    assert second['pool_before']==first['pool_after']
    assert state(env)['pools']['5']==12500000

def test_same_round_different_boxes_paid_sequentially(env):
    t=table(env);r=bets(env,t,[1,2]);a=claim(env,t,r,1,kind='progressive');b=claim(env,t,r,1,box=2,kind='progressive')
    assert a['status']==b['status']=='approved'
    assert a['amount']==200070 and b['amount']==200000
    assert b['pool_before']==a['pool_after']

def test_pending_pauses_only_own_table(env):
    t=table(env);r=bets(env,t);x=claim(env,t,r,5);other=table(env,'2');before=state(env)['pools']
    assert cmd(env,'close',{'table_id':t['id'],'round_id':r['id']}).status_code==409
    assert cmd(env,'reverse',{'table_id':t['id'],'round_id':r['id'],'reason':'pending'}).status_code==409
    bets(env,other)
    assert state(env)['pools']['5']==before['5']+220
    paid=ok(env,'approve',{'claim_id':x['id']})
    assert paid['amount']==1000000  # Royal fixed paytable; other table's stake remains accounted

def test_config_snapshots_balances_unchanged(env):
    t=table(env);r=bets(env,t);before=state(env)['pools'];cfg=copy.deepcopy(state(env)['config']);cfg.pop('version');cfg.pop('engine');cfg['stake']=6000;cfg['tiers'][0]['fixed']=26000
    ok(env,'config_update',{'config':cfg,'reason':'approved test change'});assert state(env)['pools']==before
    x=claim(env,t,r);assert x['amount']==25000

def test_immutable_journal_chain(env):
    t=table(env);bets(env,t);rows=env.get('/api/v1/events').json();previous='0'*64
    for event in rows:
        stored=event.pop('hash');event.pop('seq');assert event['previous_hash']==previous
        assert hashlib.sha256(canonical(event).encode()).hexdigest()==stored;previous=stored
    with pytest.raises(Exception):
        with connection() as c: c.execute('DELETE FROM events')

def test_tls_and_login_lockout(env):
    c=TestClient(app,base_url='http://testserver');assert c.post('/api/v1/login',json={'name':'admin','password':'x'}).status_code==426
    for _ in range(5): assert env.post('/api/v1/login',json={'name':'admin','password':'x'}).status_code==401
    assert env.post('/api/v1/login',json={'name':'admin','password':'unique-test-password-123'}).status_code==429

def test_reconciliation_and_export(env):
    t=table(env);r=bets(env,t);claim(env,t,r);d=state(env)['business_date']
    report=env.get('/api/v1/reports',params={'start':d,'end':d}).json()
    assert report['casino_closing']==state(env)['pools']
    assert report['totals']['payout_amount']==report['totals']['pool_debit']+report['totals']['house_shortfall']
    assert env.get('/api/v1/reports',params={'start':d,'end':d,'format':'csv'}).text.startswith('metric,value')

def test_device_sequence_reconnect_same_id(env):
    t=table(env);d,_=device(env,t);op='operator-000000001';d.post('/api/v1/operator',json={'operator_id':op})
    intent={'command_id':str(uuid.uuid4()),'op':'confirm','payload':{'table_id':t['id'],'round_id':t['next_round_id'],'boxes':[1]},'operator_id':op,'sequence':1}
    first=d.post('/api/v1/commands',json=intent);assert first.status_code==200,first.text
    assert first.json()['acknowledgment']=={'sequence':1,'committed':True}
    assert d.post('/api/v1/commands',json={**intent,'operator_id':'different-reconnect-operator'}).json()==first.json()
    assert state(d)['tables'][0]['device_sequence']==1
    # Fresh command cannot reuse a stale sequence, regardless of op.
    wrong={**intent,'command_id':str(uuid.uuid4()),'op':'close','payload':{'table_id':t['id'],'round_id':t['next_round_id']}}
    assert d.post('/api/v1/commands',json=wrong).status_code==409
    assert state(env)['pools']['5']==12500220

def test_two_stage_approval_and_revocation(env):
    config=copy.deepcopy(state(env)['config']);config.pop('version');config.pop('engine');config['tiers'][2]['approval']='pit_admin'
    ok(env,'config_update',{'config':config,'reason':'two-stage acceptance'})
    pit=ok(env,'principal_create',{'name':'pit','role':'pit','password':'unique-pit-password'})
    login=env.post('/api/v1/login',json={'name':'pit','password':'unique-pit-password'}).json()
    p=TestClient(app,base_url='https://testserver');p.headers['Authorization']='Bearer '+login['token']
    t=table(env);r=bets(env,t);x=claim(env,t,r,3)
    assert cmd(env,'approve',{'claim_id':x['id']}).status_code==403
    assert ok(p,'approve',{'claim_id':x['id']})['status']=='pending'
    assert ok(env,'approve',{'claim_id':x['id']})['status']=='approved'
    from app.security import authenticate
    from app.engine import execute
    from fastapi import HTTPException
    stale_actor=authenticate(login['token'])
    ok(env,'principal_revoke',{'principal_id':pit['id'],'reason':'end of test'})
    with pytest.raises(HTTPException) as revoked:
        execute(stale_actor,str(uuid.uuid4()),'close',{'table_id':t['id'],'round_id':r['id']})
    assert revoked.value.status_code==401
    assert p.get('/api/v1/state').status_code==401

def test_wrong_types_and_large_boxes(env):
    t=table(env)
    assert cmd(env,'confirm',{'table_id':t['id'],'round_id':t['next_round_id'],'boxes':[True]}).status_code==422
    assert cmd(env,'confirm',{'table_id':t['id'],'round_id':t['next_round_id'],'boxes':[8]}).status_code==422
    assert cmd(env,'adjust',{'tier':1,'delta':0.5,'reason':'invalid float'}).status_code==422
    assert cmd(env,'table_register',{'number':'1','name':'duplicate'}).status_code==409

def test_announcement_queue_persisted(env):
    t=table(env);r=bets(env,t,[1,2]);first=claim(env,t,r,1);second=claim(env,t,r,2,box=2)
    assert datetime.fromisoformat(second['show_at'])>=datetime.fromisoformat(first['show_until'])
    rows=env.get('/api/v1/events').json();wins=[x for x in rows if x['kind']=='win_approved']
    assert len(wins)==2 and wins[0]['payload']['win_id']!=wins[1]['payload']['win_id']
    assert all('winner_name' not in x['payload'] for x in wins)

def test_twenty_table_simulation(env):
    tables=[table(env,str(n)) for n in range(1,21)]
    with ThreadPoolExecutor(20) as pool:
        rounds=list(pool.map(lambda t:bets(env,t,[1]),tables))
    assert len(rounds)==20
    assert state(env)['pools']=={'1':200700,'2':500900,'3':1001400,'4':5002600,'5':12504400}
    assert sum(r['stake'] for r in rounds)==100000
    rows=env.get('/api/v1/events').json()
    assert sum(e['kind']=='initialized' for e in rows)==1
    assert sum(e['kind']=='round_confirmed' for e in rows)==20

def test_permanent_kiosk_url(env):
    t=table(env);path='/table/'+t['id']
    assert t['kiosk_path']==path
    assert env.get(path).status_code==200
    assert env.get('/table/'+'0'*32).status_code==404
    assert env.get('/table/not-an-id').status_code==404
    before=state(env)['pools']
    ok(env,'table_update',{'table_id':t['id'],'name':'Renamed','minimum':10000})
    assert state(env)['tables'][0]['kiosk_path']==path
    assert state(env)['pools']==before
    with TestClient(app,base_url='https://testserver',headers=dict(env.headers)) as restarted:
        assert restarted.get(path).status_code==200
        assert state(restarted)['tables'][0]['id']==t['id']

def test_kiosk_url_binding_and_pair_code_not_consumed(env):
    first=table(env);second=table(env,'2')
    code=ok(env,'pair_create',{'table_id':first['id']})['pairing_code']
    body={'code':code,'name':'kiosk-binding-test','app_version':'test','table_id':second['id']}
    assert env.post('/api/v1/pair',json=body).status_code==409
    valid=env.post('/api/v1/pair',json={**body,'table_id':first['id']})
    assert valid.status_code==200,valid.text
    d=TestClient(app,base_url='https://testserver',headers={'Authorization':'Bearer '+valid.json()['token'],'X-Premier-Table':second['id']})
    before=state(env)['pools']
    assert d.get('/api/v1/state').status_code==403
    assert d.get('/api/v1/stream').status_code==403
    assert d.post('/api/v1/operator',json={'operator_id':'kiosk-operator-0001'}).status_code==403
    assert state(env)['pools']==before
    d.headers['X-Premier-Table']=first['id']
    assert d.get('/api/v1/state').status_code==200
    assert state(d)['tables'][0]['id']==first['id']

def test_mode_switch_preserves_financial_state_and_round(env):
    t=table(env);r=bets(env,t,[1,3]);before=state(env)
    switched=ok(env,'mode',{'table_id':t['id'],'mode':'baccarat'})
    assert switched['mode']=='baccarat'
    assert state(env)['pools']==before['pools']
    assert state(env)['rounds']==before['rounds']
    assert state(env)['claims']==before['claims']
    assert switched['round_id']==r['id']
    assert cmd(env,'mode',{'table_id':t['id'],'mode':'uninstalled'}).status_code==409
    assert cmd(env,'table_update',{'table_id':t['id'],'modes':[{}]}).status_code==422
    assert cmd(env,'table_update',{'table_id':t['id'],'modes':['progressive']}).status_code==409
    ok(env,'mode',{'table_id':t['id'],'mode':'progressive'})
    ok(env,'table_update',{'table_id':t['id'],'modes':['progressive']})
    assert cmd(env,'mode',{'table_id':t['id'],'mode':'baccarat'}).status_code==409
    assert state(env)['pools']==before['pools']
    assert state(env)['rounds']==before['rounds']

def test_non_jackpot_pool_reporting_and_reversal(env):
    a=table(env);b=table(env,'2');r=bets(env,a,[1,2]);bets(env,b,[1])
    day=state(env)['business_date'];url='/api/v1/reports?start='+day+'&end='+day
    whole=env.get(url).json()
    assert whole['non_jackpot_pool']=={'casino_opening':0,'casino_closing':13500,'allocated':13500,'reversed':0,'net':13500}
    only=env.get(url+'&table_id='+a['id']).json()
    assert only['totals']['boxes']==2 and only['totals']['bets_net']==2
    assert only['non_jackpot_pool']['net']==9000
    assert only['non_jackpot_pool']['casino_closing']==13500
    ok(env,'reverse',{'table_id':a['id'],'round_id':r['id'],'reason':'Test cancellation'})
    report=env.get(url).json()
    assert report['totals']['bets_net']==1
    assert report['totals']['bets_reversed']==2
    assert report['non_jackpot_pool']=={'casino_opening':0,'casino_closing':4500,'allocated':13500,'reversed':9000,'net':4500}
    assert 'non_jackpot_pool.net,4500' in env.get(url+'&format=csv').text

def test_multiple_boxes_atomic_claim_and_highest_only(env):
    t=table(env);r=bets(env,t,[1,2,3]);wins=ok(env,'claims',{'table_id':t['id'],'round_id':r['id'],'boxes':[2,1],'tier':1,'type':'fixed'})['claims']
    assert [x['box'] for x in wins]==[1,2] and all(x['status']=='approved' for x in wins)
    before=state(env)
    assert cmd(env,'claim',{'table_id':t['id'],'round_id':r['id'],'box':1,'tier':5,'type':'progressive'}).status_code==409
    assert cmd(env,'claims',{'table_id':t['id'],'round_id':r['id'],'boxes':[3,4],'tier':2,'type':'fixed'}).status_code==409
    assert state(env)['claims']==before['claims'] and state(env)['pools']==before['pools']
    third=claim(env,t,r,2,box=3)
    assert third['status']=='approved'
    assert len(state(env)['claims'])==3

def test_pit_can_confirm_upper_win_at_current_pool(env):
    t=table(env);r=bets(env,t);x=claim(env,t,r,5,kind='progressive')
    ok(env,'principal_create',{'name':'pit','role':'pit','password':'unique-pit-password'})
    pit=env.post('/api/v1/login',json={'name':'pit','password':'unique-pit-password'}).json()
    p=TestClient(app,base_url='https://testserver',headers={'Authorization':'Bearer '+pit['token']})
    other=table(env,'2');bets(env,other)
    assert ok(p,'approve',{'claim_id':x['id']})['amount']==12500440

def test_baccarat_server_history_limits_and_isolation(env):
    a=table(env);b=table(env,'2');before=state(env)['pools']
    ok(env,'mode',{'table_id':a['id'],'mode':'baccarat'})
    ok(env,'table_update',{'table_id':a['id'],'minimum':5000,'maximum':100000})
    pair=ok(env,'baccarat_pair',{'table_id':a['id'],'revision':0,'side':'P'})
    win=ok(env,'baccarat_result',{'table_id':a['id'],'revision':pair['revision'],'outcome':'P'})
    assert win['hands'][0]['playerPair'] and win['hands'][0]['limits']['minimum']==5000
    old_version=win['hands'][0]['limits']['version']
    ok(env,'table_update',{'table_id':a['id'],'minimum':10000})
    nextwin=ok(env,'baccarat_result',{'table_id':a['id'],'revision':win['revision'],'outcome':'B','special':'dragon7'})
    assert nextwin['hands'][0]['limits']['minimum']==5000
    assert nextwin['hands'][1]['limits']['minimum']==10000
    assert nextwin['hands'][1]['limits']['version']>old_version
    assert cmd(env,'baccarat_result',{'table_id':a['id'],'revision':win['revision'],'outcome':'B'}).status_code==409
    shoe=ok(env,'baccarat_shoe',{'table_id':a['id'],'revision':nextwin['revision']})
    assert shoe['shoe']==2 and not shoe['hands'] and len(shoe['history'][0]['hands'])==2
    assert state(env)['pools']==before
    assert next(t for t in state(env)['tables'] if t['id']==b['id'])['baccarat']['hands']==[]
    with TestClient(app,base_url='https://testserver',headers=dict(env.headers)) as restart:
        assert next(t for t in state(restart)['tables'] if t['id']==a['id'])['baccarat']==shoe

def test_baccarat_command_idempotency_and_undo_journal(env):
    t=table(env);ok(env,'mode',{'table_id':t['id'],'mode':'baccarat'})
    payload={'table_id':t['id'],'revision':0,'outcome':'B','special':'dragon7'};cid=str(uuid.uuid4())
    first=ok(env,'baccarat_result',payload,cid);assert ok(env,'baccarat_result',payload,cid)==first
    assert len(first['hands'])==1
    removed=ok(env,'baccarat_undo',{'table_id':t['id'],'revision':first['revision']})
    assert not removed['hands']
    day=state(env)['business_date'];report=env.get('/api/v1/reports',params={'start':day,'end':day,'table_id':t['id']}).json()
    assert report['baccarat']=={'recorded':1,'undone':1,'net':0,'player':0,'banker':0,'tie':0,'player_pairs':0,'banker_pairs':0}
    events=env.get('/api/v1/events').json()
    recorded=[e for e in events if e['kind']=='baccarat_result'];assert len(recorded)==1
    assert recorded[0]['payload']['last_hand']['special']=='dragon7'
    assert any(e['kind']=='baccarat_undo' for e in events)
    assert cmd(env,'baccarat_settings',{'table_id':t['id'],'revision':removed['revision'],'settings':{'minimum':1}}).status_code==422

def test_owner_policy_upgrade_preserves_existing_snapshots(env):
    from app.apply_owner_decisions import apply
    config=copy.deepcopy(state(env)['config']);config.pop('version');config.pop('engine')
    for tier in config['tiers']:
        if tier['code']>=3:tier['approval']='admin'
    ok(env,'config_update',{'config':config,'reason':'Legacy policy fixture'})
    t=table(env);bets(env,t);before=state(env)
    assert apply(dry_run=True)['existing_rounds_and_pools_preserved']
    assert state(env)['config']==before['config']
    assert apply()['changed_tiers']==[3,4,5]
    after=state(env)
    assert after['rounds']==before['rounds'] and after['pools']==before['pools']
    assert all(tier['approval']=='pit' for tier in after['config']['tiers'] if tier['code']>=3)
    assert apply()['changed'] is False

def test_baccarat_separate_table_cannot_accept_progressive_stakes(env):
    before=state(env)['pools'];t=ok(env,'table_register',{'number':'B1','name':'Baccarat','game':'baccarat'})
    assert t['mode']=='baccarat'
    assert cmd(env,'confirm',{'table_id':t['id'],'round_id':t['next_round_id'],'boxes':[1]}).status_code==409
    assert state(env)['pools']==before
    assert cmd(env,'table_update',{'table_id':t['id'],'game':'poker'}).status_code==409
    assert ok(env,'baccarat_result',{'table_id':t['id'],'revision':0,'outcome':'T'})['hands'][0]['outcome']=='T'
