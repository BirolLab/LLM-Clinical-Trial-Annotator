import json, time, urllib.parse, urllib.request, os, sys
SP = '.'
ncts = [l.strip() for l in open(SP + "/ncts.txt") if l.strip()]
F = "protocolSection.armsInterventionsModule,protocolSection.identificationModule,protocolSection.descriptionModule"
out_path = SP + "/work/ctg.jsonl"
done = set()
if os.path.exists(out_path):
    for l in open(out_path):
        try: done.add(json.loads(l)["nct"])
        except Exception: pass
todo = [n for n in ncts if n not in done]
f = open(out_path, "a")
B = 40
for k in range(0, len(todo), B):
    batch = todo[k:k+B]
    url = ("https://clinicaltrials.gov/api/v2/studies?format=json&pageSize=100&fields="
           + urllib.parse.quote(F) + "&filter.ids=" + urllib.parse.quote(",".join(batch)))
    data = None
    for a in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as r: data = json.load(r)
            break
        except Exception as e:
            if a == 4: print("FAIL", batch[0], e, file=sys.stderr)
            else: time.sleep(2 * (a + 1))
    if not data: continue
    got = set()
    for st in data.get("studies", []):
        ps = st.get("protocolSection", {})
        nid = ps.get("identificationModule", {}).get("nctId")
        if not nid: continue
        got.add(nid)
        idm = ps.get("identificationModule", {}); dm = ps.get("descriptionModule", {}) or {}
        am = ps.get("armsInterventionsModule", {}) or {}
        f.write(json.dumps({"nct": nid, "bt": idm.get("briefTitle",""), "ot": idm.get("officialTitle",""),
                            "bs": dm.get("briefSummary",""), "dd": dm.get("detailedDescription",""),
                            "arms": am.get("armGroups") or [], "ivs": am.get("interventions") or []}) + "\n")
    for n in batch:
        if n not in got: f.write(json.dumps({"nct": n, "missing": 1}) + "\n")
    f.flush()
    time.sleep(0.15)
f.close()
print("done", len(todo))
