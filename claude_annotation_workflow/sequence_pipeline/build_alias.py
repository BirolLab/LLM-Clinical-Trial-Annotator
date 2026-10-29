# Rebuild the drug->alias lexicon for the 232 drug keys in drug_sequences.tsv.
# Alias sources: local bundle ChEMBL synonyms (by_source/chembl.jsonl), NCATS GSRS name
# records, and the curated lexicon in curated.py.
import json, re, sys, csv, collections, os, urllib.request, urllib.parse, gzip, time
sys.path.insert(0, '.')
from curated import EXCLUDE, GENERIC, SUPP, OVERRIDE, GENERIC_ALIAS, MERGE, ALIAS_ADD

SALT = r'(acetate|mesylate|pamoate|hydrochloride|hcl|citrate|sodium|diacetate|trifluoroacetate|' \
       r'triflutate|hexaacetate|pentahydrochloride|tetrahydrate|hydrate|succinate|tartrate|maleate|' \
       r'sulfate|sulphate|chloride|implant|injection|depot|anhydrous|monohydrate|diaspartate|' \
       r'embonate|besylate|dihydrochloride|zinc|protamine|rdna|recombinant|acetat)'
SRC_SUFFIX = ('hsdb','usan','usp','inn','jan','mi','mart','who-dd','orange book','vandf','ema',
 'fda','atc','bnf','merck index','jecfa','ep','bp','nf','iso','inci','ban','dcf','jp','ph eur',
 'martindale','green book','ndf-rt','mesh','cas','unii','rxnorm','wikipedia','nci thesaurus')
def clean_name(s):
    t = (s or ''); low = t.lower()
    for p in ('alternative definition for ', 'alternate definition for ', 'definition for '):
        if low.startswith(p): t = t[len(p):]; low = t.lower()
    for suf in SRC_SUFFIX:
        if low.endswith(' ' + suf): t = t[:-(len(suf)+1)]; low = t.lower()
    return t.strip()
def norm(s):
    s = (s or '').lower(); s = re.sub(r'[‐-―−]', '-', s)
    s = s.replace('.', ' ').replace(',', ' ').replace('(', ' ').replace(')', ' ')
    s = re.sub(r'[^a-z0-9\- ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()
RANGE = re.compile(r'(.+?)[\s:]*\(?(\d{1,4}\s*-\s*\d{1,4})\)?\s*$')
def range_variants(nm):
    t = norm(nm); m = RANGE.match(t)
    if not m: return set()
    base, rng = m.group(1).strip(), m.group(2).replace(' ', '')
    out = set()
    for b in {base, re.sub(r'\s*peptide\s*$', '', base).strip()}:
        if not b: continue
        for b2 in {b, b.replace('-', ''), b.replace('-', ' ')}:
            b2 = re.sub(r'\s+', ' ', b2).strip()
            if not b2: continue
            out.add('%s %s' % (b2, rng)); out.add('%s peptide %s' % (b2, rng))
    return out
def dkey(s):
    t = norm(s); prev = None
    while prev != t:
        prev = t
        t = re.sub(r'\s+' + SALT + r'$', '', t)
        t = re.sub(r'\s+salt$', '', t)
    return t

# ---- target key set ---------------------------------------------------------------
KEYS = {}
for r in csv.DictReader(open('drug_sequences.tsv'), delimiter='\t'):
    KEYS[r['drug_key']] = r
from additions import NEW_DRUGS, ALIAS_DROP, ALIAS_ADD2, NEW_EXCLUDE
ALLK = set(KEYS) | set(NEW_DRUGS) | set(NEW_EXCLUDE)
print('keys', len(KEYS), 'new', len(NEW_DRUGS), 'new-excl', len(NEW_EXCLUDE), file=sys.stderr)
def remap(k): return MERGE.get(k, k)

alias = collections.defaultdict(set)
def addal(a, k):
    a = norm(a)
    if len(a) >= 5: alias[a].add(k)

for k in ALLK: addal(k, k)
for k, (als, seq, src, conf) in NEW_DRUGS.items():
    for a in als: addal(a, k)
for k, als in ALIAS_ADD2.items():
    if k in ALLK:
        for a in als: addal(a, k)
for k, als in ALIAS_ADD.items():
    if k in KEYS:
        for a in als: addal(a, k)
for k, (als, seq, src, conf) in SUPP.items():
    if k in KEYS:
        for a in als: addal(a, k)
for src, dst in MERGE.items():
    if dst in KEYS: addal(src, dst)

# ---- ChEMBL synonyms from the bundle files ---------------------------------------
cb = collections.defaultdict(set)
for l in open('/projects/btl/ezhang/ctg_lookup/ctg_api_out/by_source/chembl.jsonl'):
    d = json.loads(l)
    pref = d.get('pref_name') or ''
    k = remap(dkey(clean_name(pref)))
    if k not in ALLK: continue
    names = {pref}
    for key, v in d.items():
        if key.endswith('.molecule_synonym') or key.endswith('.synonyms'):
            if v: names.add(v)
    for nm in names:
        for v in {nm, clean_name(nm)}:
            cb[k].add(v)
            for rv in range_variants(v):
                if len(rv) >= 5: alias[rv].add(k)
for k, ns in cb.items():
    for nm in ns: addal(nm, k)
print('after chembl: aliases', len(alias), 'keys with chembl syn', len(cb), file=sys.stderr)

# ---- GSRS name records -----------------------------------------------------------
CACHE = 'work/gsrs_names.json'
gs = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
def g(u):
    req = urllib.request.Request(u, headers={'User-Agent': 'research/1.0', 'Accept-Encoding': 'gzip'})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = r.read()
        if r.headers.get('Content-Encoding') == 'gzip': d = gzip.decompress(d)
    return json.loads(d)
todo = [k for k in KEYS if k not in gs]
for i, k in enumerate(todo):
    q = urllib.parse.quote('root_names_name:"%s"' % k.upper())
    u = 'https://gsrs.ncats.nih.gov/api/v1/substances/search?q=%s&top=8&view=full' % q
    rec = []
    for a in range(4):
        try:
            d = g(u); break
        except Exception as e:
            d = None
            if a == 3: print('FAIL', k, e, file=sys.stderr)
            else: time.sleep(2 * (a + 1))
    if d:
        for c in d.get('content', []):
            rec.append({'name': c.get('_name'), 'unii': c.get('approvalID'),
                        'names': [n.get('name') for n in (c.get('names') or [])],
                        'subs': [s.get('sequence') for s in ((c.get('protein') or {}).get('subunits') or [])]})
    gs[k] = rec
    if i % 40 == 39:
        json.dump(gs, open(CACHE, 'w')); print('gsrs', i + 1, '/', len(todo), file=sys.stderr)
    time.sleep(0.05)
json.dump(gs, open(CACHE, 'w'))

import os as _os
if _os.path.exists('work/gsrs_names2.json'):
    g2 = json.load(open('work/gsrs_names2.json'))
    for k, recs in g2.items(): gs.setdefault(k, []); gs[k] = gs[k] + recs
ngs = 0
for k, recs in gs.items():
    if k not in ALLK: continue
    for c in recs:
        if remap(dkey(clean_name(c['name'] or ''))) != k: continue
        ngs += 1
        for nm in set([c['name'] or ''] + (c['names'] or [])):
            if not nm: continue
            for v in {nm, clean_name(nm)}:
                addal(v, k)
                for rv in range_variants(v):
                    if len(rv) >= 5: alias[rv].add(k)
print('gsrs records used', ngs, file=sys.stderr)

STOPA = set('''insulin protein peptide hormone factor collagen albumin gelatin elastin casein
keratin globulin complex vaccine toxin antigen allergen extract concentrate serum gluten whey
water sodium acetate chloride solution placebo saline standard normal control glucose sucrose
lactose starch dextran heparin alcohol oxygen nitrogen plasma blood cells tissue enzyme
amylase lipase trypsin pepsin fibrin thrombin histone mucin lectin gliadin'''.split())
alias = {a: sorted(ks) for a, ks in alias.items() if a not in STOPA and a not in ALIAS_DROP}
drugs = {}
for k, r in KEYS.items():
    e = {'key': k, 'names': [k], 'gsrs': None, 'chembl': None}
    if r['sequence']:
        e['override'] = {'seq': r['sequence'], 'src': r['source'], 'conf': r['confidence'], 'note': ''}
    else:
        e['nosequence'] = r['status']
    drugs[k] = e
for k, (als, seq, src, conf) in NEW_DRUGS.items():
    e = {'key': k, 'names': [k], 'gsrs': None, 'chembl': None}
    if seq: e['override'] = {'seq': seq, 'src': src, 'conf': conf, 'note': ''}
    else: e['nosequence'] = src
    drugs[k] = e
for k, why in NEW_EXCLUDE.items():
    drugs[k] = {'key': k, 'names': [k], 'gsrs': None, 'chembl': None, 'nosequence': why}
json.dump({'drugs': drugs, 'alias': alias}, open('work/drugs.json', 'w'))
print('drugs', len(drugs), 'aliases', len(alias))
