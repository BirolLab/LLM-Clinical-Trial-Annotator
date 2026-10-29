"""Section 6.4: abstracts for the registry-listed references of unresolved trials,
from Europe PMC.  RESULT -> DERIVED -> BACKGROUND."""
import json, os, sys, time, urllib.parse, urllib.request
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
ORDER = {"RESULT": 0, "DERIVED": 1, "BACKGROUND": 2}

def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(2 * (i + 1))

def fetch(pmids):
    """Up to ~20 pmids per query."""
    q = " OR ".join(f"EXT_ID:{p}" for p in pmids)
    url = EPMC + "?" + urllib.parse.urlencode(
        {"query": q, "resultType": "core", "format": "json", "pageSize": str(len(pmids))})
    d = get(url) or {}
    out = {}
    for r in (d.get("resultList", {}) or {}).get("result", []) or []:
        pid = r.get("pmid") or r.get("id")
        if pid:
            out[str(pid)] = {"title": r.get("title", "") or "",
                             "year": str(r.get("pubYear", "") or ""),
                             "abstract": r.get("abstractText", "") or "",
                             "pmid": str(pid)}
    return out

def main():
    base = {}
    for l in open(sys.argv[1]):
        d = json.loads(l); base[d["nct_id"]] = d
    want = [l.strip() for l in open(sys.argv[2]) if l.strip()]
    need = {}
    for n in want:
        for r in base.get(n, {}).get("refs", []):
            if r.get("pmid"):
                need.setdefault(r["pmid"], []).append(n)
    pmids = sorted(need)
    print(f"{len(want)} trials -> {len(pmids)} distinct pmids", flush=True)
    got = {}
    for i in range(0, len(pmids), 20):
        got.update(fetch(pmids[i:i + 20]))
        if (i // 20) % 5 == 0:
            print(f"  {i+20}/{len(pmids)} -> {len(got)}", flush=True)
    out = open(sys.argv[3], "w")
    for n in want:
        papers = []
        for r in sorted(base.get(n, {}).get("refs", []),
                        key=lambda x: ORDER.get((x.get("type") or "").upper(), 3)):
            p = got.get(r.get("pmid", ""))
            if p and p["abstract"].strip():
                q = dict(p); q["reftype"] = (r.get("type") or "").upper()
                papers.append(q)
        out.write(json.dumps({"nct_id": n, "papers": papers}) + "\n")
    out.close()
    print(f"DONE: {sum(1 for l in open(sys.argv[3]) if json.loads(l)['papers'])} trials with >=1 abstract",
          flush=True)

if __name__ == "__main__":
    main()
