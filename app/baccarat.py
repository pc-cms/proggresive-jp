"""Per-table Baccarat result history. No wager settlement or jackpot mutations."""
import copy
from .security import fail,now,uid

def empty():return {'revision':0,'shoe':1,'hands':[],'history':[],'pending':{'P':False,'B':False},'settings':{}}

def mutate(table,op,p,actor):
    from .engine import integer,text
    live=table.setdefault('baccarat',empty())
    if integer(p.get('revision'))!=live['revision']:fail(409,'Baccarat revision changed; review server state')
    if op=='baccarat_result':
        outcome=p.get('outcome');special=p.get('special')
        if outcome not in ('P','B','T'):fail(422,'Invalid Baccarat outcome')
        sides={'super6':'B','dragon7':'B','panda8':'P','bigTiger':'B','smallTiger':'B'}
        if special is not None and sides.get(special)!=outcome:fail(422,'Special result does not match outcome')
        mode=live['settings'].get('mode','ultimate')
        allowed={'ultimate':tuple(sides),'classic':(),'ez':('dragon7','panda8'),'super6':('super6',),'tiger':('bigTiger','smallTiger')}
        if special and special not in allowed[mode]:fail(409,'Special not offered in this display profile')
        live['hands'].append({'id':uid(),'outcome':outcome,'special':special,'playerPair':live['pending']['P'],'bankerPair':live['pending']['B'],'ts':now().isoformat(),'actor':actor,'limits':{'minimum':table['minimum'],'maximum':table['maximum'],'version':table.get('limits_version',1)}})
        live['pending']={'P':False,'B':False}
    elif op=='baccarat_pair':
        side=p.get('side')
        if side not in ('P','B'):fail(422,'Invalid pair side')
        live['pending'][side]=not live['pending'][side]
    elif op=='baccarat_undo':
        if not live['hands']:fail(409,'No hand to undo')
        live['hands'].pop()
    elif op=='baccarat_shoe':
        if live['hands']:live['history'].insert(0,{'shoe':live['shoe'],'hands':copy.deepcopy(live['hands']),'endedAt':now().isoformat()})
        live['hands']=[];live['pending']={'P':False,'B':False};live['shoe']+=1
    elif op=='baccarat_settings':
        settings=p.get('settings')
        allowed={'brand','announcement','lang','mode','quality','sound','logoData'}
        if not isinstance(settings,dict) or set(settings)-allowed:fail(422,'Use admin table settings for identity and limits')
        for k,v in settings.items():
            if not isinstance(v,str) or len(v)>(2000000 if k=='logoData' else 200):fail(422,'Invalid display setting')
        for k,values in {'lang':('en','zh'),'mode':('ultimate','classic','ez','super6','tiger'),'quality':('max','balanced','quiet'),'sound':('on','off')}.items():
            if k in settings and settings[k] not in values:fail(422,'Invalid display profile')
        if settings.get('logoData') and not settings['logoData'].startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,')):fail(422,'Unsupported logo')
        live['settings'].update(settings)
    else:fail(404,'Unknown Baccarat command')
    live['revision']+=1
    return copy.deepcopy(live)
