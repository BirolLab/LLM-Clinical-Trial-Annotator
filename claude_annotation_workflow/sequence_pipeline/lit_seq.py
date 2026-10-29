import re, json, glob
SRC = "/projects/btl/ezhang/ctg_lookup/ctg_api_out/bundles_chunks"
WORDS = set(w.strip().upper() for w in open('/usr/share/dict/words') if len(w.strip()) >= 5)
hdr = re.compile(r'(?m)^# (NCT\d+)\s*$')
AA = 'ACDEFGHIKLMNPQRSTVWY'
pat = re.compile(r'(?<![A-Za-z0-9.=])[' + AA + r']{8,40}(?![A-Za-z0-9])')
KW = re.compile(r'(?i)peptide|sequence|epitope|amino acid|analog|residue')
out = {}
for p in sorted(glob.glob(SRC + "/*.md")):
    t = open(p).read()
    parts = hdr.split(t)
    for i in range(1, len(parts), 2):
        nct = parts[i]; body = parts[i+1]
        hits = {}
        for ln in body.split("\n"):
            if 'sequence.value=' in ln or 'molecule_name=' in ln or 'title=' in ln.lower()[:40]: 
                ln = re.sub(r'sequence\.value=[A-Z]+', '', ln)
            for m in pat.finditer(ln):
                s = m.group(0)
                if s in WORDS: continue
                lo = max(0, m.start()-120); ctx = ln[lo:m.end()+60]
                if KW.search(ctx): hits.setdefault(s, ctx.strip()[:220])
        if hits: out[nct] = hits
json.dump(out, open("work/lit_seq.json", "w"))
print(len(out), sum(len(v) for v in out.values()))
