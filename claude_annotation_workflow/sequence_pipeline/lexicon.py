import json, re, collections
WORDS = set(w.strip().lower() for w in open('/usr/share/dict/words'))
def norm(s):
    s = s.lower()
    s = re.sub(r'[‐-―−]', '-', s)
    s = s.replace('.', ' ').replace(',', ' ').replace('(', ' ').replace(')', ' ')
    s = re.sub(r'[^a-z0-9\- ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s
STOP = set('''insulin human protein peptide hormone factor collagen albumin gelatin
casein keratin globulin complex vaccine toxin antigen allergen extract concentrate serum
gluten soy whey milk water sodium acetate chloride solution placebo saline standard'''.split())
recs = []
alias = collections.defaultdict(list)
for l in open('work/gsrs_proteins.jsonl'):
    d = json.loads(l)
    su = [(i, s) for i, s in d['subunits'] if s]
    tot = sum(len(s) for _, s in su)
    d['tot'] = tot; d['nsub'] = len(su)
    idx = len(recs); recs.append(d)
    for nm in set([d['name'] or ''] + d['names']):
        k = norm(nm)
        if len(k) < 5: continue
        if k in WORDS: continue
        if k in STOP: continue
        alias[k].append(idx)
json.dump({'n': len(recs)}, open('work/lex_stat.json', 'w'))
print('recs', len(recs), 'aliases', len(alias))
import pickle
pickle.dump({'recs': recs, 'alias': dict(alias)}, open('work/lex.pkl', 'wb'))
