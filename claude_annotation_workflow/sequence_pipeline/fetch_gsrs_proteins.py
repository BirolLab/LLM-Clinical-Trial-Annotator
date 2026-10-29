import urllib.request, json, urllib.parse, gzip, time, os, sys
SP = "/tmp/claude-2520/-projects-btl-ezhang-ctg-lookup-ctg-api-out/bc1399bb-d176-4f43-a2a8-673663cbc912/scratchpad"
def g(u):
    req = urllib.request.Request(u, headers={'User-Agent': 'research/1.0', 'Accept-Encoding': 'gzip'})
    with urllib.request.urlopen(req, timeout=240) as r:
        d = r.read()
        if r.headers.get('Content-Encoding') == 'gzip': d = gzip.decompress(d)
    return json.loads(d)
out = SP + "/work/gsrs_proteins.jsonl"
have = 0
if os.path.exists(out): have = sum(1 for _ in open(out))
f = open(out, "a")
Q = urllib.parse.quote('root_substanceClass:protein')
TOP = 50
skip = (have // TOP) * TOP
total = 10**9
while skip < total:
    u = f'https://gsrs.ncats.nih.gov/api/v1/substances/search?q={Q}&top={TOP}&skip={skip}&view=full'
    d = None
    for a in range(5):
        try: d = g(u); break
        except Exception as e:
            if a == 4: print("FAIL", skip, e, file=sys.stderr)
            else: time.sleep(3 * (a + 1))
    if d is None: skip += TOP; continue
    total = d.get('total', 0)
    for c in d.get('content', []):
        rec = {"uuid": c.get("uuid"), "name": c.get("_name"), "unii": c.get("approvalID"),
               "names": [n.get("name") for n in (c.get("names") or [])],
               "codes": [(x.get("codeSystem"), x.get("code")) for x in (c.get("codes") or [])],
               "subunits": [(s.get("subunitIndex"), s.get("sequence")) for s in ((c.get("protein") or {}).get("subunits") or [])],
               "glyco": (c.get("protein") or {}).get("glycosylation"),
               "disulf": [(d2.get("sites")) for d2 in ((c.get("protein") or {}).get("disulfideLinks") or [])],
               "mods": [{"t": m.get("modificationType"), "g": m.get("modificationGroup"),
                         "frag": ((m.get("molecularFragment") or {}) or {}).get("refPname"),
                         "res": m.get("residueModified"), "ext": m.get("extent"),
                         "sites": m.get("sites"), "role": m.get("modificationRole"),
                         "loc": m.get("locationType")}
                        for m in ((c.get("modifications") or {}) or {}).get("structuralModifications") or []],
               "aminomods": [{"t": m.get("modificationType"), "res": m.get("residueModified"), "sites": m.get("sites")}
                             for m in ((c.get("modifications") or {}) or {}).get("agentModifications") or []],
               "status": c.get("status"), "deprecated": c.get("deprecated"),
               "proteinType": (c.get("protein") or {}).get("proteinType"),
               "proteinSubType": (c.get("protein") or {}).get("proteinSubType"),
               "seqOrigin": (c.get("protein") or {}).get("sequenceOrigin"),
               "rel": [{"type": r.get("type"), "to": ((r.get("relatedSubstance") or {}) or {}).get("refPname")} for r in (c.get("relationships") or [])][:40],
               }
        f.write(json.dumps(rec) + "\n")
    f.flush()
    skip += TOP
    time.sleep(0.1)
f.close()
print("done", skip, total)
