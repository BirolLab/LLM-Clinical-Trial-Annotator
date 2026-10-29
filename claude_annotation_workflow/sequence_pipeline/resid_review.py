import json, re, sys
sys.path.insert(0,'.')
from gsrs_render import render_gsrs
def norm(s):
    s=(s or '').lower(); s=re.sub(r'[‐-―−]','-',s)
    s=s.replace('.',' ').replace(',',' ').replace('(',' ').replace(')',' ')
    s=re.sub(r'[^a-z0-9\- ]',' ',s); return re.sub(r'\s+',' ',s).strip()
G=json.load(open('work/gsrs_resid.json'))
MAXL=int(sys.argv[1]) if len(sys.argv)>1 else 140
for q,recs in sorted(G.items()):
    if not recs: continue
    for c in recs:
        nm=norm(c['name']); nms={norm(x) for x in ([c['name']]+(c['names'] or [])) if x}
        qn=norm(q)
        if qn not in nms and qn.replace('-','') not in {x.replace('-','') for x in nms}: continue
        tot=sum(len(s) for _,s in c['subunits'] if s)
        seq,notes,unm=render_gsrs(c)
        print('%-20s | %-34s | %-30s | tot=%-4d %s' % (q[:20], (c['name'] or '')[:34], (c.get('proteinType') or '')[:30], tot,
              (seq[:120] if seq and tot<=MAXL else ('<%d res>'%tot if seq else 'no-seq'))))
        if notes: print(' '*22,'notes:', '; '.join(notes)[:110])
        if unm: print(' '*22,'unmapped:', '; '.join(unm)[:110])
