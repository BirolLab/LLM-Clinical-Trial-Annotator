import sys; sys.path.insert(0,'/projects/btl/ezhang/final_ctg_lookup/ctg_api_out/sequence_pipeline'); import cfg
import json, re, csv, collections
csv.field_size_limit(10**9)
D = json.load(open(cfg.WORK+'/drugs.json')); drugs = D['drugs']; alias = D['alias']

# --- glued-token matching -------------------------------------------------------------
# Radioligand and salt names glue the peptide to a prefix with hyphens
# ("68Ga-NODAGA-exendin-4", "Lu-177-DOTA-Octreotide", "Cyclosporine-A"), and the n-gram
# matcher only splits on spaces, so the peptide name inside the token is never seen.
# A hyphen-delimited sub-run of such a token may name a drug, under three guards.
# 1. A family/class alias never matches this way: inside a compound word it is almost
#    always part of a longer entity name, and gonadorelin's family synonyms are the
#    pipeline's worst false-positive source (step 1c).
GLUE_BLOCK_RX = re.compile(r'gonadotrop|luteini[sz]ing|lh releasing|lh-rh|gnrh|'
                           r'^insulin$|^glucagon$|^angiotensin$|^calcitonin$|^somatostatin$|'
                           r'^relaxin$|^secretin$|^glutathione$|^gsh$|^thymosin$|^amylin$|'
                           r'^apelin$|^kisspeptin$|^ghrelin$|^hepcidin$|^xenin$')
# 2. The hyphen-part that follows must not be a word that turns the alias into a different
#    entity: "glucagon-like" is GLP-1 not glucagon, "angiotensin-converting" is an enzyme,
#    "calcitonin-gene" is CGRP, "luteinizing-hormone" is a class phrase.
GLUE_CONT = {'like', 'converting', 'gene', 'related', 'releasing', 'receptor', 'binding',
             'stimulating', 'inhibiting', 'inhibitor', 'antagonist', 'agonist', 'analog',
             'analogue', 'deficient', 'dependent', 'resistant', 'sparing', 'free', 'naive',
             'treated', 'induced', 'associated', 'mediated', 'derived', 'based', 'pump',
             'sensitive', 'secreting', 'producing', 'positive', 'negative'}
# 3. The alias must be at least 5 characters, so single letters and short codes do not fire,
#    and it must contain a run of >=4 letters, so a research or protocol code never matches
#    this way: "FP-001-IM" is the study code of a parathyroid-hormone trial, and the lexicon
#    happens to carry fp-001 as a leuprolide code.  Whole-token codes still match normally
#    in the n-gram pass; only extraction from inside a compound token is restricted.
GLUE_MINLEN = 5
GLUE_WORD_RX = re.compile(r'[a-z]{4}')
def glue_find(words, used):
    """-> {dkey: set(matched alias)} for aliases hidden inside hyphen-glued tokens"""
    out = {}
    for wi, tok in enumerate(words):
        if used[wi] or '-' not in tok: continue
        parts = tok.split('-')
        for i in range(len(parts)):
            for j in range(i + 1, min(i + 5, len(parts)) + 1):
                sub = '-'.join(parts[i:j])
                if len(sub) < GLUE_MINLEN or sub not in alias: continue
                if not GLUE_WORD_RX.search(sub): continue
                if i == 0 and j == len(parts): continue      # the whole token: the n-gram pass saw it
                if GLUE_BLOCK_RX.search(sub): continue
                nxt = parts[j] if j < len(parts) else ''
                if nxt in GLUE_CONT: continue
                for dk in alias[sub]: out.setdefault(dk, set()).add(sub)
    return out
def norm(s):
    s = (s or '').lower(); s = re.sub(r'[‐-―−]', '-', s)
    s = s.replace('.', ' ').replace(',', ' ').replace('(', ' ').replace(')', ' ')
    s = re.sub(r'[^a-z0-9\- ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()
MAXN = 7
def find(text, glued_out=None):
    """-> {dkey: set(matched alias)}; glued_out collects drugs seen only via glue_find"""
    out = {}
    t = norm(text)
    if not t: return out
    w = t.split(' ')
    used = [False]*len(w)
    for n in range(min(MAXN, len(w)), 0, -1):
        for i in range(0, len(w)-n+1):
            if any(used[i:i+n]): continue
            k = ' '.join(w[i:i+n])
            if k in alias:
                for dk in alias[k]: out.setdefault(dk, set()).add(k)
                for z in range(i, i+n): used[z] = True
    g = glue_find(w, used)
    for dk, al in g.items():
        if glued_out is not None and dk not in out: glued_out.add(dk)
        out.setdefault(dk, set()).update(al)
    return out
EXP = {'EXPERIMENTAL'}
CMP = {'ACTIVE_COMPARATOR', 'PLACEBO_COMPARATOR', 'SHAM_COMPARATOR', 'NO_INTERVENTION'}
tr = {}
for r in csv.DictReader(open(cfg.TRIALS)):
    tr.setdefault(r['nct_id'], r)
res = {}
for l in open(cfg.WORK+'/ctg.jsonl'):
    d = json.loads(l)
    armtype = {a.get('label', ''): (a.get('type') or '') for a in d.get('arms', [])}
    per = {}   # dkey -> {'alias':set,'ivtypes':set,'arms':set,'where':set,'ivnames':set}
    glued = set(); nonglued = set()
    for iv in d.get('ivs', []):
        nm = iv.get('name', ''); on = iv.get('otherNames') or []
        at = set(armtype.get(x, '') for x in (iv.get('armGroupLabels') or []))
        gset = set()
        f = find(' | '.join([nm] + on), gset)
        glued |= gset; nonglued |= (set(f) - gset)
        for dk, al in f.items():
            e = per.setdefault(dk, {'alias': set(), 'ivtypes': set(), 'arms': set(), 'where': set(), 'ivnames': set()})
            e['alias'] |= al; e['ivtypes'].add(iv.get('type') or ''); e['arms'] |= at
            e['where'].add('intervention'); e['ivnames'].add(nm[:60])
        # research-code / descriptions: only to catch sequences later
    for fld, tag in ((d.get('bt', ''), 'title'), (d.get('ot', ''), 'title')):
        gset = set(); ff = find(fld, gset)
        glued |= gset; nonglued |= (set(ff) - gset)
        for dk, al in ff.items():
            e = per.setdefault(dk, {'alias': set(), 'ivtypes': set(), 'arms': set(), 'where': set(), 'ivnames': set()})
            e['alias'] |= al; e['where'].add(tag)
    r = tr.get(d['nct'])
    if r:
        gset = set()
        ff2 = find(' | '.join([(r['interventions'] or ''), (r['search_terms'] or '')]), gset)
        glued |= gset; nonglued |= (set(ff2) - gset)
        for dk, al in ff2.items():
            e = per.setdefault(dk, {'alias': set(), 'ivtypes': set(), 'arms': set(), 'where': set(), 'ivnames': set()})
            e['alias'] |= al; e['where'].add('search_terms')
    if per:
        res[d['nct']] = {k: {'alias': sorted(v['alias']), 'ivtypes': sorted(v['ivtypes']),
                             'arms': sorted(v['arms']), 'where': sorted(v['where']),
                             'ivnames': sorted(v['ivnames']),
                             'glue': 1 if (k in glued and k not in nonglued) else 0}
                         for k, v in per.items()}
json.dump(res, open(cfg.WORK+'/match2.json', 'w'))
cnt = collections.Counter()
for n, f in res.items():
    for k in f: cnt[k] += 1
print('trials', len(res), 'drugs matched', len(cnt))
json.dump(cnt.most_common(), open(cfg.WORK+'/match2_cnt.json', 'w'))
