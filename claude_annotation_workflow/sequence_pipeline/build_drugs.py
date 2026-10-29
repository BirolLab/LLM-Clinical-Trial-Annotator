import json, re, sys, collections
sys.path.insert(0, '.')
from gsrs_render import render_gsrs
from render import render

SALT = r'(acetate|mesylate|pamoate|hydrochloride|hcl|citrate|sodium|diacetate|trifluoroacetate|' \
       r'triflutate|hexaacetate|pentahydrochloride|tetrahydrate|hydrate|succinate|tartrate|maleate|' \
       r'sulfate|sulphate|chloride|implant|injection|depot|anhydrous|monohydrate|diaspartate|' \
       r'embonate|besylate|dihydrochloride|zinc|protamine|rdna|recombinant|acetat)'
SRC_SUFFIX = ('hsdb','usan','usp','inn','jan','mi','mart','who-dd','orange book','vandf','ema',
 'fda','atc','bnf','merck index','jecfa','ep','bp','nf','iso','inci','ban','dcf','jp','ph eur',
 'martindale','green book','ndf-rt','mesh','cas','unii','rxnorm','wikipedia','nci thesaurus')
def clean_name(s):
    t = (s or '')
    low = t.lower()
    for p in ('alternative definition for ', 'alternate definition for ', 'definition for '):
        if low.startswith(p):
            t = t[len(p):]; low = t.lower()
    for suf in SRC_SUFFIX:
        if low.endswith(' ' + suf):
            t = t[:-(len(suf) + 1)]; low = t.lower()
    return t.strip()

def norm(s):
    s = (s or '').lower()
    s = re.sub(r'[‐-―−]', '-', s)
    s = s.replace('.', ' ').replace(',', ' ').replace('(', ' ').replace(')', ' ')
    s = re.sub(r'[^a-z0-9\- ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()
RANGE = re.compile(r'(.+?)[\s:]*\(?(\d{1,4}\s*-\s*\d{1,4})\)?\s*$')
def range_variants(nm):
    """'GP-100 peptide (209-217)' -> {'gp-100 209-217','gp100 209-217','gp-100 peptide 209-217',...}"""
    t = norm(nm)
    m = RANGE.match(t)
    if not m: return set()
    base, rng = m.group(1).strip(), m.group(2).replace(' ', '')
    out = set()
    for b in {base, re.sub(r'\s*peptide\s*$', '', base).strip()}:
        if not b: continue
        for b2 in {b, b.replace('-', ''), b.replace('-', ' ')}:
            b2 = re.sub(r'\s+', ' ', b2).strip()
            if not b2: continue
            out.add('%s %s' % (b2, rng))
            out.add('%s peptide %s' % (b2, rng))
    return out

def dkey(s):
    t = norm(s)
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r'\s+' + SALT + r'$', '', t)
        t = re.sub(r'\s+salt$', '', t)
    return t

drugs = {}   # dkey -> entry
def add(key, name, src, seq, meta):
    e = drugs.setdefault(key, {'key': key, 'names': set(), 'gsrs': None, 'chembl': None})
    e['names'].add(name)
    if src == 'gsrs' and (e['gsrs'] is None or meta.get('tot', 0) > 0 and e['gsrs']['meta'].get('tot', 0) == 0):
        e['gsrs'] = {'name': name, 'seq': seq, 'meta': meta}
    if src == 'chembl' and e['chembl'] is None:
        e['chembl'] = {'name': name, 'seq': seq, 'meta': meta}

# GSRS peptide candidates
gs_alias = collections.defaultdict(set)
for l in open('work/gsrs_proteins.jsonl'):
    d = json.loads(l)
    su = [(i, s) for i, s in d['subunits'] if s]
    tot = sum(len(s) for _, s in su)
    if tot == 0 or tot > 120: continue
    seq, notes, unm = render_gsrs(d)
    k = dkey(clean_name(d['name']))
    add(k, d['name'], 'gsrs', seq, {'tot': tot, 'nsub': len(su), 'notes': notes, 'unmapped': unm,
                                    'unii': d['unii'], 'ptype': d.get('proteinType') or ''})
    for nm in set([d['name'] or ''] + d['names']):
        for v in {nm, clean_name(nm)}:
            a = norm(v)
            if len(a) >= 5: gs_alias[a].add(k)
            for rv in range_variants(v):
                if len(rv) >= 5: gs_alias[rv].add(k)

# ChEMBL peptides
cb_alias = collections.defaultdict(set)
cp = json.load(open('work/chembl_pep.json'))
for r in cp:
    if r['nres'] < 2: continue
    k = dkey(clean_name(r['pref'] or (r['syn'][0] if r['syn'] else '')))
    if not k: continue
    add(k, r['pref'], 'chembl', r['seq'], {'nres': r['nres'], 'cov': r['cov'], 'nchain': r['nchain'],
                                           'unk': r['unk'], 'id': r['id'], 'type': r['type']})
    for nm in set([r['pref'] or ''] + r['syn']):
        for v in {nm, clean_name(nm)}:
            a = norm(v)
            if len(a) >= 5: cb_alias[a].add(k)

alias = collections.defaultdict(set)
for a, ks in gs_alias.items(): alias[a] |= ks
for a, ks in cb_alias.items(): alias[a] |= ks
STOPA = set('''insulin protein peptide hormone factor collagen albumin gelatin elastin casein
keratin globulin complex vaccine toxin antigen allergen extract concentrate serum gluten whey
water sodium acetate chloride solution placebo saline standard normal control glucose sucrose
lactose starch dextran heparin alcohol oxygen nitrogen plasma blood cells tissue enzyme
amylase lipase trypsin pepsin fibrin thrombin histone mucin lectin gliadin'''.split())
from curated import MERGE, SUPP, EXCLUDE, OVERRIDE, ALIAS_ADD
# fold brand/duplicate keys
for src, dst in MERGE.items():
    if src in drugs:
        e = drugs.pop(src)
        d2 = drugs.setdefault(dst, {'key': dst, 'names': set(), 'gsrs': None, 'chembl': None})
        d2['names'] |= set(e['names'])
        if d2['gsrs'] is None: d2['gsrs'] = e['gsrs']
        if d2['chembl'] is None: d2['chembl'] = e['chembl']
    for a in list(alias):
        if src in alias[a]:
            alias[a] = {dst if x == src else x for x in alias[a]}
for k, als in ALIAS_ADD.items():
    for a in als: alias.setdefault(norm(a), set()).add(k)
# curated supplement
for k, (als, seq, src, conf) in SUPP.items():
    e = drugs.setdefault(k, {'key': k, 'names': set(), 'gsrs': None, 'chembl': None})
    e['names'].add(k); e['supp'] = {'seq': seq, 'src': src, 'conf': conf}
    for a in als:
        alias.setdefault(norm(a), set()).add(k)
# aliases for excluded (identified-but-not-annotatable) drugs, harvested from ChEMBL synonyms
cmall = json.load(open('work/chembl_mols.json'))
for m in cmall:
    k = dkey(clean_name(m['pref'] or ''))
    if k in EXCLUDE:
        e = drugs.setdefault(k, {'key': k, 'names': set(), 'gsrs': None, 'chembl': None})
        e['names'].add(m['pref'])
        for nm in set([m['pref'] or ''] + m['syn']):
            for v in {nm, clean_name(nm)}:
                a = norm(v)
                if len(a) >= 5: alias.setdefault(a, set()).add(k)
for k in EXCLUDE:
    drugs.setdefault(k, {'key': k, 'names': {k}, 'gsrs': None, 'chembl': None})
    alias.setdefault(norm(k), set()).add(k)
for k, (seq, src, conf, note) in OVERRIDE.items():
    if k in drugs: drugs[k]['override'] = {'seq': seq, 'src': src, 'conf': conf, 'note': note}
alias = {a: sorted(ks) for a, ks in alias.items() if a not in STOPA}
for e in drugs.values(): e['names'] = sorted(e['names'])
json.dump({'drugs': drugs, 'alias': alias}, open('work/drugs.json', 'w'))
print('drugs', len(drugs), 'aliases', len(alias))
