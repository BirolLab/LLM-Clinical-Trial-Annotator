# Step 1d/1f sweep over the rows left with no identified peptide drug in this corpus.
# Ranks the intervention names (and their otherNames) that the lexicon did not match,
# so each candidate can be resolved by name in GSRS / ChEMBL / UniProt.
import sys, json, re, csv, collections
sys.path.insert(0,'/projects/btl/ezhang/final_ctg_lookup/ctg_api_out/sequence_pipeline')
import cfg
csv.field_size_limit(10**9)
D=json.load(open(cfg.WORK+'/drugs.json')); alias=D['alias']
R=list(csv.DictReader(open(cfg.WORK+'/trial.csv')))
nod=set(r['NCT Number'] for r in R if not r['Sequence'] and 'no peptide drug identified' in r['Evidence'])
def norm(s):
    s=(s or '').lower(); s=re.sub(r'[‐-―−]','-',s)
    s=s.replace('.',' ').replace(',',' ').replace('(',' ').replace(')',' ')
    s=re.sub(r'[^a-z0-9\- ]',' ',s); return re.sub(r'\s+',' ',s).strip()
DRUGTYPE={'DRUG','BIOLOGICAL','COMBINATION_PRODUCT','DIETARY_SUPPLEMENT'}
names=collections.Counter(); byname=collections.defaultdict(set)
for l in open(cfg.WORK+'/ctg.jsonl'):
    d=json.loads(l)
    if d['nct'] not in nod: continue
    for iv in d.get('ivs',[]):
        if (iv.get('type') or '') not in DRUGTYPE: continue
        for nm in [iv.get('name','')]+(iv.get('otherNames') or []):
            t=norm(nm)
            if not t or t in alias: continue
            names[t]+=1; byname[t].add(d['nct'])
json.dump({k:sorted(v) for k,v in byname.items()}, open(cfg.WORK+'/sweep26_byname.json','w'))
print('distinct unmatched drug/biological intervention names:',len(names))
print('trials with no identified peptide:',len(nod))
for t,c in names.most_common(120):
    print('%4d  %s' % (c, t[:95]))
