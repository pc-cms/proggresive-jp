"""Apply approved PIT-or-Admin policy to FUTURE test rounds, preserving snapshots."""
import argparse,copy
from .db import connection,lock,state,save
from .engine import journal

def apply(dry_run=False):
    with connection() as c:
        lock(c);s=state(c)
        if s['environment']!='test':raise RuntimeError('This helper is restricted to the TEST installation')
        config=copy.deepcopy(s['config'])
        changed=[t['code'] for t in config['tiers'] if t['code']>=3 and t['approval']!='pit']
        if not changed:return {'changed':False,'config_version':config['version']}
        for tier in config['tiers']:
            if tier['code']>=3:tier['approval']='pit'
        config['version']+=1
        if not dry_run:
            s['config']=config
            journal(c,'config_update','system:owner-decisions-2026-10-08',s,{'config':config,'reason':'Owner confirmed PIT or Admin for upper categories; existing round snapshots preserved'})
            save(c,s)
        return {'dry_run':dry_run,'changed_tiers':changed,'new_config_version':config['version'],'existing_rounds_and_pools_preserved':True}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true');args=parser.parse_args();print(apply(args.dry_run))
