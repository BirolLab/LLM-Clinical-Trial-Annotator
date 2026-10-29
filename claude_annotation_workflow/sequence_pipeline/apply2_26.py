"""Fold additions2.py into work/drugs.json (second lexicon pass)."""
import json, sys
sys.path.insert(0,'/projects/btl/ezhang/final_ctg_lookup/ctg_api_out/sequence_pipeline')
import cfg
from additions2 import NEW_DRUGS2, ALIAS_ADD3, NEW_EXCLUDE2, ALIAS_ADD4
D = json.load(open(cfg.WORK+'/drugs.json'))
drugs, alias = D['drugs'], D['alias']
for k, (als, seq, src, conf) in NEW_DRUGS2.items():
    drugs[k] = {'key': k, 'names': [k], 'gsrs': None, 'chembl': None,
                'override': {'seq': seq, 'src': src, 'conf': conf, 'note': ''}}
    for a in set(als) | {k}:
        alias.setdefault(a, [])
        if k not in alias[a]: alias[a] = sorted(set(alias[a]) | {k})
for k in NEW_EXCLUDE2:
    drugs.setdefault(k, {'key': k, 'names': [k], 'gsrs': None, 'chembl': None})
for k, als in list(ALIAS_ADD3.items()) + list(ALIAS_ADD4.items()):
    assert k in drugs, k
    for a in als:
        alias.setdefault(a, [])
        if k not in alias[a]: alias[a] = sorted(set(alias[a]) | {k})
json.dump({'drugs': drugs, 'alias': alias}, open(cfg.WORK+'/drugs.json', 'w'))
print('drugs', len(drugs), 'alias', len(alias))
