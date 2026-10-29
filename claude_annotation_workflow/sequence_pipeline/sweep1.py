# Step 1d/1f over ALL trials: bundle-ChEMBL records named by a research code or -tide name
# that appears in the trial's own text, and that are not already in the drug table.
import csv, json, re, collections
D=json.load(open('work/drugs.json')); alias=D['alias']; keys=set(D['drugs'])
def norm(s):
    s=(s or '').lower(); s=re.sub(r'[‐-―−]','-',s)
    s=s.replace('.',' ').replace(',',' ').replace('(',' ').replace(')',' ')
    s=re.sub(r'[^a-z0-9\- ]',' ',s); return re.sub(r'\s+',' ',s).strip()
CODE=re.compile(r'^[a-z]{1,5}[- ]?\d{2,6}[a-z]?$')
TIDE=re.compile(r'(tide|relin|pressin|tocin|glutide|cortin|motide|pepimut|rsen|kinra)$')
toks=collections.defaultdict(set)
for l in open('work/ctg.jsonl'):
    d=json.loads(l)
    txt=[iv.get('name','') for iv in d.get('ivs',[])]
    for iv in d.get('ivs',[]): txt += (iv.get('otherNames') or [])
    txt += [d.get('bt',''), d.get('ot','')]
    for nm in txt:
        t=norm(nm)
        for w in t.split(' '):
            if len(w)>=4 and (CODE.match(w) or TIDE.search(w)):
                toks[d['nct']].add(w); toks[d['nct']].add(w.replace('-',''))
res=collections.defaultdict(lambda: {'ncts':set(),'codes':set(),'seq':'','mt':'','syn':set()})
for l in open('/projects/btl/ezhang/ctg_lookup/ctg_api_out/by_source/chembl.jsonl'):
    d=json.loads(l)
    n=d.get('nct_id'); pref=d.get('pref_name') or ''
    if n not in toks or not pref: continue
    k=norm(pref)
    if k in keys or k in alias: continue
    syn={norm(v) for kk,v in d.items() if (kk.endswith('.molecule_synonym') or kk.endswith('.synonyms')) and v}|{k}
    syn|={s.replace('-','') for s in syn}
    m=syn & toks[n]
    if not m: continue
    seq=[]
    for i in range(16):
        s=d.get('biotherapeutic.biocomponents[%d].sequence'%i)
        if s: seq.append(s)
    e=res[k]; e['ncts'].add(n); e['codes']|=m; e['mt']=d.get('molecule_type') or ''
    e['syn']|= {s for s in syn if len(s)>=4}
    if seq and not e['seq']: e['seq']='|'.join(seq)
print('new candidate drugs:', len(res))
for k,e in sorted(res.items(), key=lambda x:-len(x[1]['ncts'])):
    if e['mt'] in ('Small molecule','Oligonucleotide','Antibody','Oligosaccharide','Cell','Gene','Enzyme'): continue
    print('%-26s n=%-3d %-10s codes=%-28s seq=%s' % (k[:26], len(e['ncts']), e['mt'], ';'.join(sorted(e['codes']))[:28], (e['seq'][:80] or '-')))
json.dump({k:{'ncts':sorted(v['ncts']),'codes':sorted(v['codes']),'seq':v['seq'],'mt':v['mt'],'syn':sorted(v['syn'])} for k,v in res.items()}, open('work/sweep1.json','w'))
