#!/usr/bin/env python3
"""Registry status, whyStopped, phases, hasResults, references (methodology S3 src 1).

Batched (S11: tens of IDs per request), cached by NCT id in work/status.json so a
re-run after an interruption re-requests nothing.
"""
import json, os, sys, time, urllib.parse, urllib.request

WORK = os.environ.get("OUTCOME_WORK", "outcome_pipeline/work")
CACHE = os.path.join(WORK, "status.json")
API = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = "NCTId,OverallStatus,WhyStopped,Phase,HasResults,ReferencePMID,ReferenceType,ReferenceCitation,StartDate,CompletionDate,BriefTitle,DesignPrimaryPurpose"
BATCH = 40


def load(path, default):
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return default


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                print(f"  FAIL {e}", file=sys.stderr)
                return None
            time.sleep(2 * (i + 1))


def flat(s):
    p = s.get("protocolSection", {})
    ident = p.get("identificationModule", {})
    st = p.get("statusModule", {})
    refs = p.get("referencesModule", {}).get("references", []) or []
    return {
        "nct": ident.get("nctId", ""),
        "title": ident.get("briefTitle", ""),
        "status": st.get("overallStatus", ""),
        # StartDate was in FIELDS but was being dropped here, so the chronology
        # guard (S5.2) had nothing to work with.
        "start_date": (st.get("startDateStruct", {}) or {}).get("date", ""),
        "completion_date": (st.get("completionDateStruct", {}) or {}).get("date", ""),
        "why_stopped": st.get("whyStopped", "") or "",
        "phases": p.get("designModule", {}).get("phases", []) or [],
        "purpose": p.get("designModule", {}).get("designInfo", {}).get("primaryPurpose", ""),
        "has_results": bool(s.get("hasResults")),
        "refs": [{"pmid": r.get("pmid", ""), "type": r.get("type", ""),
                  "citation": (r.get("citation", "") or "")[:300]} for r in refs],
    }


def main():
    lit = load(os.path.join(WORK, "lit.json"), [])
    ncts = [t["nct"] for t in lit]
    cache = load(CACHE, {})
    todo = [n for n in ncts if n not in cache]
    print(f"total={len(ncts)} cached={len(cache)} to_fetch={len(todo)}")

    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        url = (f"{API}?filter.ids={urllib.parse.quote(','.join(batch))}"
               f"&fields={urllib.parse.quote(FIELDS)}&pageSize={BATCH}&format=json")
        d = get(url)
        if d:
            for s in d.get("studies", []):
                f = flat(s)
                if f["nct"]:
                    cache[f["nct"]] = f
        for n in batch:                     # record misses so we never re-request
            cache.setdefault(n, {"nct": n, "status": "NOT_IN_REGISTRY", "why_stopped": "",
                                 "phases": [], "purpose": "", "has_results": False,
                                 "refs": [], "title": ""})
        if (i // BATCH) % 10 == 0:
            with open(CACHE, "w") as fh:
                json.dump(cache, fh)
            print(f"  {i + len(batch)}/{len(todo)}", flush=True)

    with open(CACHE, "w") as fh:
        json.dump(cache, fh)

    from collections import Counter
    c = Counter(cache[n]["status"] for n in ncts)
    print("--- status distribution ---")
    for k, v in c.most_common():
        print(f"{v:6d}  {k}")
    print(f"hasResults={sum(1 for n in ncts if cache[n]['has_results'])}  "
          f"with_refs={sum(1 for n in ncts if cache[n]['refs'])}")


if __name__ == "__main__":
    main()
