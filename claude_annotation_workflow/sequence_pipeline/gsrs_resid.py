# Step 1d / 2b.2: resolve by name in NCATS GSRS the research codes and named peptides that
# the lexicon did not match in any trial.
import json, os, re, sys, time, gzip, csv, collections, urllib.request, urllib.parse
D=json.load(open('work/drugs.json')); alias=D['alias']
R=list(csv.DictReader(open('work/trial.csv')))
nod=set(r['NCT Number'] for r in R if not r['Sequence'] and 'no peptide drug identified' in r['Evidence'])
def norm(s):
    s=(s or '').lower(); s=re.sub(r'[‐-―−]','-',s)
    s=s.replace('.',' ').replace(',',' ').replace('(',' ').replace(')',' ')
    s=re.sub(r'[^a-z0-9\- ]',' ',s); return re.sub(r'\s+',' ',s).strip()
CODE=re.compile(r'^[a-z]{1,5}[- ]?\d{2,6}[a-z]?$')
TIDE=re.compile(r'(tide|relin|pressin|tocin|glutide|cortin|motide|pepimut|rsen)$')
toks=collections.Counter()
for l in open('work/ctg.jsonl'):
    d=json.loads(l)
    if d['nct'] not in nod: continue
    for iv in d.get('ivs',[]):
        for nm in [iv.get('name','')]+(iv.get('otherNames') or []):
            t=norm(nm)
            if not t or t in alias: continue
            for w in t.split(' '):
                if len(w)>=4 and (CODE.match(w) or TIDE.search(w)) and w not in alias:
                    toks[w]+=1
EXTRA=['ny-eso-1','ny-eso-1 peptide','urlc10','kif20a','romiplostim','rindopepimut','albiglutide',
 'efpeglenatide','dulaglutide','fluciclatide','sar425899','disitertide','galinpepimut-s',
 'ombipepimut-s','ingap peptide','pvx-410','ub-312','eli-002','ima950','ima901','tpiv100','tpiv200',
 '6mhp','ae37 peptide','gp2 peptide','supaglutide','enlicitide','p-15 peptide','p144','hsp70 peptide',
 'pp65 peptide','na17','ep2101','dgx-001','cbx-12','vacc-10','vacc-11','vacc-12','vacc-13','pl-18',
 'bcd-201','alt02','hs627','pds0101','drg-0012','sls-001','biib061','peptide t','thymalfasin']
names=[t for t,c in toks.most_common() if t not in ('peptide','polypeptide','multi-peptide','multipeptide','glycopeptide')]+EXTRA
C='work/gsrs_resid.json'
gs=json.load(open(C)) if os.path.exists(C) else {}
def g(u):
    r=urllib.request.Request(u, headers={'User-Agent':'research/1.0','Accept-Encoding':'gzip'})
    with urllib.request.urlopen(r, timeout=120) as f:
        d=f.read()
        if f.headers.get('Content-Encoding')=='gzip': d=gzip.decompress(d)
    return json.loads(d)
todo=[n for n in dict.fromkeys(names) if n not in gs]
print('queries', len(todo), file=sys.stderr, flush=True)
for i,q in enumerate(todo):
    u='https://gsrs.ncats.nih.gov/api/v1/substances/search?q=%s&top=15&view=full'%urllib.parse.quote('"%s"'%q)
    d=None
    for a in range(4):
        try: d=g(u); break
        except Exception as e:
            if a==3: print('FAIL',q,e,file=sys.stderr,flush=True)
            else: time.sleep(2*(a+1))
    out=[]
    if d:
        for c in d.get('content',[]):
            su=[(s.get('subunitIndex'),s.get('sequence')) for s in ((c.get('protein') or {}).get('subunits') or [])]
            if not any(s for _,s in su): continue
            out.append({'uuid':c.get('uuid'),'name':c.get('_name'),'unii':c.get('approvalID'),
              'names':[n.get('name') for n in (c.get('names') or [])],
              'subunits':su,'proteinType':(c.get('protein') or {}).get('proteinType'),
              'mods':[{'t':m.get('modificationType'),'g':m.get('modificationGroup'),
                       'frag':((m.get('molecularFragment') or {}) or {}).get('refPname'),
                       'res':m.get('residueModified'),'ext':m.get('extent'),'sites':m.get('sites'),
                       'role':m.get('modificationRole'),'loc':m.get('locationType')}
                      for m in ((c.get('modifications') or {}) or {}).get('structuralModifications') or []]})
    gs[q]=out
    if i%30==29: json.dump(gs,open(C,'w')); print('resid',i+1,'/',len(todo),file=sys.stderr,flush=True)
    time.sleep(0.05)
json.dump(gs,open(C,'w'))
print('done', sum(1 for v in gs.values() if v), 'of', len(gs), 'names resolved to protein records')
