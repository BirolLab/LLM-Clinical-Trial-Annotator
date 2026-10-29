import json, os, sys, time, gzip, urllib.request, urllib.parse, csv
KEYS=[r['drug_key'] for r in csv.DictReader(open('drug_sequences.tsv'),delimiter='\t')]
C='work/gsrs_names2.json'
gs=json.load(open(C)) if os.path.exists(C) else {}
def g(u):
    r=urllib.request.Request(u, headers={'User-Agent':'research/1.0','Accept-Encoding':'gzip'})
    with urllib.request.urlopen(r, timeout=120) as f:
        d=f.read()
        if f.headers.get('Content-Encoding')=='gzip': d=gzip.decompress(d)
    return json.loads(d)
todo=[k for k in KEYS if k not in gs]
for i,k in enumerate(todo):
    u='https://gsrs.ncats.nih.gov/api/v1/substances/search?q=%s&top=25&view=full'%urllib.parse.quote('"%s"'%k)
    d=None
    for a in range(4):
        try: d=g(u); break
        except Exception as e:
            if a==3: print('FAIL',k,e,file=sys.stderr)
            else: time.sleep(2*(a+1))
    rec=[]
    if d:
        for c in d.get('content',[]):
            rec.append({'name':c.get('_name'),'unii':c.get('approvalID'),
                        'names':[n.get('name') for n in (c.get('names') or [])]})
    gs[k]=rec
    if i%40==39: json.dump(gs,open(C,'w')); print('gsrs2',i+1,'/',len(todo),file=sys.stderr); sys.stderr.flush()
    time.sleep(0.05)
json.dump(gs,open(C,'w'))
print('done',len(gs))
