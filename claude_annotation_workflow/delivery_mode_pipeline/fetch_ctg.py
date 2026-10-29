#!/usr/bin/env python3
"""Fetch CTG v2 trial text for the NCT ids in work/ncts.txt -> work/ctg_raw.jsonl.
Resumable: skips ids already present. Methodology section 4."""
import json, os, time, urllib.request, urllib.error, urllib.parse, sys

WORK = os.environ.get("DM_WORK", "work")
NCTS = os.path.join(WORK, "ncts.txt")
OUT  = os.path.join(WORK, "ctg_raw.jsonl")
FIELDS = ("NCTId,BriefTitle,OfficialTitle,InterventionType,InterventionName,"
          "InterventionOtherName,InterventionDescription,ArmGroupLabel,"
          "ArmGroupDescription,ArmGroupInterventionName,BriefSummary,DetailedDescription")

def load_done():
    done = set()
    if os.path.exists(OUT):
        with open(OUT) as f:
            for line in f:
                try: done.add(json.loads(line)["nct"])
                except Exception: pass
    return done

def shape(st):
    ps = st.get("protocolSection", {})
    idm = ps.get("identificationModule", {})
    arms = ps.get("armsInterventionsModule", {})
    desc = ps.get("descriptionModule", {})
    return {
        "nct": idm.get("nctId", ""),
        "brief": idm.get("briefTitle", "") or "",
        "official": idm.get("officialTitle", "") or "",
        "interventions": [{"type": i.get("type", ""), "name": i.get("name", "") or "",
                           "description": i.get("description", "") or "",
                           "otherNames": i.get("otherNames", []) or []}
                          for i in arms.get("interventions", []) or []],
        "arms": [{"label": a.get("label", "") or "",
                  "description": a.get("description", "") or "",
                  "interventionNames": a.get("interventionNames", []) or []}
                 for a in arms.get("armGroups", []) or []],
        "summary": desc.get("briefSummary", "") or "",
        "detail": desc.get("detailedDescription", "") or "",
    }

def fetch(batch):
    url = ("https://clinicaltrials.gov/api/v2/studies?"
           + urllib.parse.urlencode({"filter.ids": ",".join(batch),
                                     "fields": FIELDS, "pageSize": 100}))
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.loads(r.read().decode()).get("studies", []) or []
        except Exception as e:
            if attempt == 3:
                print("FAIL", batch[0], e, file=sys.stderr); return None
            time.sleep(2 ** attempt * 2)

ids = [l.strip() for l in open(NCTS) if l.strip()]
done = load_done()
todo = [i for i in ids if i not in done]
print(f"{len(ids)} ids, {len(done)} done, {len(todo)} to fetch", flush=True)
with open(OUT, "a") as out:
    for k in range(0, len(todo), 50):
        batch = todo[k:k + 50]
        studies = fetch(batch)
        if studies is None: continue
        got = set()
        for st in studies:
            rec = shape(st)
            if rec["nct"]:
                out.write(json.dumps(rec) + "\n"); got.add(rec["nct"])
        for miss in set(batch) - got:
            out.write(json.dumps({"nct": miss, "missing": True}) + "\n")
        out.flush()
        if k % 1000 == 0: print(f"  {k + len(batch)}/{len(todo)}", flush=True)
print("done", flush=True)
