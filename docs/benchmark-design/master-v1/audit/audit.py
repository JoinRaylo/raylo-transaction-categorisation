import json, sys, hashlib
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
m=Path('/private/tmp/txncat-d2-worktree')
r=Path('/Users/carlosnoblejesus/Repos/raylo-transaction-categorisation')
sys.path.insert(0,str(m/'apps/ob-txn-categoriser/scripts'))
from run_evaluations import inventory_sources,adapt
from raylo_txncat.hashing import canonical_json
b=m/'apps/ob-txn-categoriser/research/waterfall-changes/baseline-2026-09-15/summary.json'
baseline=json.loads(b.read_bytes());general=baseline['general_mapping']
i,s,meta=inventory_sources(m,r,m/'apps/ob-txn-categoriser/scripts/evaluation_inventory.json')
out={'created_at':datetime.now(timezone.utc).isoformat(),'method':'Coverage and existing provenance only. No scoring, locked-file reads or model inference. Unique inputs are signatures, not verified transaction IDs.','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'datasets':{}}
complete=[];all_rows=[]
for name,task in i['tasks'].items():
 rows=adapt(name,task,s[name],s,general); all_rows+=rows
 if task in {'transactions','v4_context_join'}:complete+=rows
 labels=Counter(x['gold_leaf'] for x in rows)
 counts={
 'task':task,'n':len(rows),'source_sha256':meta[name]['registry_entry']['sha256'],
 'unique_input_signatures':len({x['input_hash'] for x in rows}),
 'direction':dict(Counter(x['direction'] for x in rows)),
 'blank_merchant':sum(not x['merchant_raw'].strip() for x in rows),
 'blank_description':sum(not (x['description_raw'] or '').strip() for x in rows),
 'provider':dict(Counter(x['provider'] for x in rows)),
 'leaves_present':len(labels),'leaves_absent':len(general)-len(labels),
 'specific_leaves_present':sum(not k.startswith('unclassified_') for k in labels),
 'leaves_with_1_to_4':sum(1<=v<5 for v in labels.values()),
 'leaves_with_5_to_19':sum(5<=v<20 for v in labels.values()),
 'leaves_with_20_to_49':sum(20<=v<50 for v in labels.values()),
 'leaves_with_50_plus':sum(v>=50 for v in labels.values()),
 'gold_counts':dict(sorted(labels.items())),
 'general_counts':dict(sorted(Counter(general[x['gold_leaf']] for x in rows).items())),
 'credit_gold_counts':dict(Counter(x['gold_leaf'] for x in rows if x['direction']=='credit')),
 'roles':dict(Counter(x.get('role','unspecified') for x in s[name])) if task!='head_validation' else {},
 'source_columns':sorted(s[name][0].keys()),
 'label_provenance':dict(Counter(x['label_provenance'] for x in rows)),
 }
 out['datasets'][name]=counts
out['nominal_all_sets_rows']=len(all_rows)
group=defaultdict(list)
for x in complete:group[x['input_hash']].append(x)
consistent=[v[0] for v in group.values() if len({x['gold_leaf'] for x in v})==1]
counts=Counter(x['gold_leaf'] for x in consistent)
out['complete_transaction_sets']={
 'nominal_rows':len(complete),'unique_input_signatures':len(group),
 'repeated_signature_rows':len(complete)-len(group),
 'conflicting_gold_signature_groups':sum(len({x['gold_leaf'] for x in v})>1 for v in group.values()),
 'consistent_signature_groups':len(consistent),'covered_leaves':len(counts),
 'missing_leaves':sorted(set(general)-set(counts)),
 'leaf_support_unique_consistent':dict(sorted(counts.items())),
 'leaves_under_20_including_missing':sum(counts[k]<20 for k in general),
 'leaves_under_50_including_missing':sum(counts[k]<50 for k in general),
 }
Path('/private/tmp/txncat-dataset-audit-20260915.json').write_text(json.dumps(out,indent=2)+'\n')
for name,d in out['datasets'].items():
 print(name, json.dumps({k:d[k] for k in ['n','direction','blank_merchant','leaves_present','leaves_with_1_to_4','leaves_with_5_to_19','roles']}))
print('UNION',json.dumps({k:v for k,v in out['complete_transaction_sets'].items() if k not in ['missing_leaves','leaf_support_unique_consistent']}))
key=['salary','salary_gig','income_agency_work','refund_received','returned_payment','transfer_own_account','transfer_p2p','benefits_state','pension_received','rent','mortgage','energy','council_tax','groceries','gambling_betting','gambling_casino','gambling_bingo','debt_collection','debt_management_plan','overdraft_unarranged','cash_advance','bnpl','loan_disbursement']
for name in ['gold_pipeline_eval','gold_credit_eval','gold_transactions_risk_t6bound','gold_v2_slm_eval_holdout']:
 print('KEY',name,{k:out['datasets'][name]['gold_counts'].get(k,0) for k in key})
print('FIELDS',out['datasets']['gold_pipeline_eval']['source_columns'])
print('FULLGOLD_PROVENANCE',out['datasets']['gold_transactions']['label_provenance'])
