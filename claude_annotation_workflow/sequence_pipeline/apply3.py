"""Fold additions3.py into work26/drugs.json (third lexicon pass)."""
import json, sys
sys.path.insert(0,'/projects/btl/ezhang/final_ctg_lookup/ctg_api_out/sequence_pipeline')
import cfg
from additions3 import NEW_DRUGS3, NEW_EXCLUDE3, ALIAS_ADD5
D = json.load(open(cfg.WORK + '/drugs.json'))
drugs, alias = D['drugs'], D['alias']
def addal(a, k):
    alias.setdefault(a, [])
    if k not in alias[a]: alias[a] = sorted(set(alias[a]) | {k})
for k, (als, seq, src, conf) in NEW_DRUGS3.items():
    drugs[k] = {'key': k, 'names': [k], 'gsrs': None, 'chembl': None,
                'override': {'seq': seq, 'src': src, 'conf': conf, 'note': ''}}
    for a in set(als) | {k}: addal(a, k)
for k, (als, why) in NEW_EXCLUDE3.items():
    drugs[k] = {'key': k, 'names': [k], 'gsrs': None, 'chembl': None, 'nosequence': why}
    for a in set(als) | {k}: addal(a, k)
for k, als in ALIAS_ADD5.items():
    assert k in drugs, k
    for a in als: addal(a, k)
json.dump({'drugs': drugs, 'alias': alias}, open(cfg.WORK + '/drugs.json', 'w'))
print('drugs', len(drugs), 'alias', len(alias))
