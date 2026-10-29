# Step 1d / 2b.2: resolve candidate names in NCATS GSRS.
import sys, os, json, time, gzip, urllib.request, urllib.parse
sys.path.insert(0,'/projects/btl/ezhang/final_ctg_lookup/ctg_api_out/sequence_pipeline')
import cfg
NAMES = [l.strip() for l in open(sys.argv[1]) if l.strip()]
C = cfg.WORK + '/gsrs26.json'
gs = json.load(open(C)) if os.path.exists(C) else {}
def g(u):
    r = urllib.request.Request(u, headers={'User-Agent':'research/1.0','Accept-Encoding':'gzip'})
    with urllib.request.urlopen(r, timeout=120) as f:
        d = f.read()
        if f.headers.get('Content-Encoding') == 'gzip': d = gzip.decompress(d)
    return json.loads(d)
todo = [n for n in dict.fromkeys(NAMES) if n not in gs]
print('queries', len(todo), file=sys.stderr, flush=True)
for i, q in enumerate(todo):
    u = 'https://gsrs.ncats.nih.gov/api/v1/substances/search?q=%s&top=12&view=full' % urllib.parse.quote('"%s"' % q)
    d = None
    for a in range(4):
        try: d = g(u); break
        except Exception as e:
            if a == 3: print('FAIL', q, e, file=sys.stderr, flush=True)
            else: time.sleep(2*(a+1))
    out = []
    if d:
        for c in d.get('content', []):
            prot = c.get('protein') or {}
            su = [(s.get('subunitIndex'), s.get('sequence')) for s in (prot.get('subunits') or [])]
            out.append({'name': c.get('_name'), 'unii': c.get('approvalID'), 'cls': c.get('substanceClass'),
                        'ptype': prot.get('proteinType'),
                        'names': [n.get('name') for n in (c.get('names') or [])][:25],
                        'subunits': su,
                        'mods': [{'t': m.get('modificationType'), 'g': m.get('modificationGroup'),
                                  'frag': ((m.get('molecularFragment') or {}) or {}).get('refPname'),
                                  'res': m.get('residueModified'), 'sites': m.get('sites')}
                                 for m in ((c.get('modifications') or {}) or {}).get('structuralModifications') or []]})
    gs[q] = out
    time.sleep(0.05)
json.dump(gs, open(C,'w'))
print('resolved', sum(1 for q in NAMES if gs.get(q)), 'of', len(set(NAMES)))
