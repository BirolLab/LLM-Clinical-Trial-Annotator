# Step 1f/2b.3: gated bundle-ChEMBL resolution for trials with no identified peptide.
# A ChEMBL record may name the drug only when a research code / alias from the trial's own
# text matches one of that record's synonyms.
import csv, json, re, collections, sys
R=list(csv.DictReader(open('work/trial.csv')))
nod=set(r['NCT Number'] for r in R if not r['Sequence'] and 'no peptide drug identified' in r['Evidence'])
D=json.load(open('work/drugs.json')); alias=D['alias']
def norm(s):
    s=(s or '').lower(); s=re.sub(r'[‐-―−]','-',s)
    s=s.replace('.',' ').replace(',',' ').replace('(',' ').replace(')',' ')
    s=re.sub(r'[^a-z0-9\- ]',' ',s); return re.sub(r'\s+',' ',s).strip()
CODE=re.compile(r'^[a-z]{1,5}[- ]?\d{2,6}[a-z]?$')
TIDE=re.compile(r'(tide|relin|pressin|tocin|glutide|cortin|motide|pepimut|rsen)$')
toks=collections.defaultdict(set)   # nct -> tokens
for l in open('work/ctg.jsonl'):
    d=json.loads(l)
    if d['nct'] not in nod: continue
    for iv in d.get('ivs',[]):
        for nm in [iv.get('name','')]+(iv.get('otherNames') or []):
            t=norm(nm)
            if not t or t in alias: continue
            for w in t.split(' '):
                if len(w)>=4 and (CODE.match(w) or TIDE.search(w)) and w not in alias:
                    toks[d['nct']].add(w); toks[d['nct']].add(w.replace('-',''))
hits=collections.defaultdict(set)
for l in open('/projects/btl/ezhang/ctg_lookup/ctg_api_out/by_source/chembl.jsonl'):
    d=json.loads(l)
    n=d.get('nct_id')
    if n not in toks: continue
    syn={norm(v) for k,v in d.items() if (k.endswith('.molecule_synonym') or k.endswith('.synonyms')) and v}
    syn|={norm(d.get('pref_name') or '')}
    syn|={s.replace('-','') for s in syn}
    if not (syn & toks[n]): continue
    seq=[]
    for i in range(12):
        s=d.get('biotherapeutic.biocomponents[%d].sequence'%i)
        if s: seq.append(s)
    hits[n].add((d.get('pref_name') or '', d.get('molecule_type') or '', '|'.join(seq), ';'.join(sorted(syn & toks[n]))[:40]))
print('trials with a gated ChEMBL name:', len(hits))
for n,v in sorted(hits.items()):
    for pref,mt,seq,m in sorted(v):
        print('%s  %-34s %-14s %-24s %s' % (n, pref[:34], mt, m, (seq[:70] or '-')))
