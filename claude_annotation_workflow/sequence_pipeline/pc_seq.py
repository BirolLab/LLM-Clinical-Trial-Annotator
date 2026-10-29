import sys, json, urllib.request, urllib.parse, time
sys.path.insert(0, '.')
from render import render
def g(u):
    r = urllib.request.Request(u, headers={'User-Agent': 'research/1.0'})
    with urllib.request.urlopen(r, timeout=90) as x: return x.read().decode('utf8', 'replace')
def smiles_for(name):
    for prop in ('SMILES', 'IsomericSMILES', 'CanonicalSMILES'):
        try:
            t = g('https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/' + urllib.parse.quote(name)
                  + '/property/%s/JSON' % prop)
            j = json.loads(t)['PropertyTable']['Properties'][0]
            cid = j.get('CID')
            s = j.get(prop) or j.get('SMILES') or j.get('IsomericSMILES')
            if s: return cid, s
        except Exception:
            continue
    return None, None
out = {}
for nm in sys.argv[1:]:
    cid, s = smiles_for(nm)
    if not s:
        print('%-26s NO-SMILES' % nm); continue
    ch, e, meta = render(s)
    if e: print('%-26s cid=%s ERR %s' % (nm, cid, e)); continue
    out[nm] = {'cid': cid, 'seq': '|'.join(ch), 'nres': meta['nres'], 'cov': round(meta['cov'], 3), 'unk': sorted(set(meta['unk']))}
    print('%-26s cid=%-10s n=%-3d cov=%-5s %s %s' % (nm, cid, meta['nres'], round(meta['cov'], 2), '|'.join(ch)[:80], sorted(set(meta['unk']))[:2]))
    time.sleep(0.25)
json.dump(out, open('work/pc_seq_%d.json' % len(sys.argv), 'w'))
