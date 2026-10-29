#!/usr/bin/env python3
"""Literature full-text search on the NCT id (methodology S3 src 5).

Catches result papers that cite the registration number in the body rather than
the abstract. Expect very low yield -- under 1% of rows in the reference corpus
-- so it is driven off the unresolved set only (S11) and cached per NCT id.
"""
import json, os, sys, time, urllib.parse, urllib.request

WORK = os.environ.get("OUTCOME_WORK", "outcome_pipeline/work")
CACHE = os.path.join(WORK, "epmc_ft.json")
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
BY = set(filter(None, os.environ.get("EPMC_BY", "unknown").split(",")))


def load(p, d):
    return json.load(open(p)) if os.path.exists(p) else d


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                return None
            time.sleep(2 * (i + 1))


def main():
    calls = {c["nct"]: c for c in load(os.path.join(WORK, "calls.json"), [])}
    lit = {t["nct"]: t for t in load(os.path.join(WORK, "lit.json"), [])}
    targets = [n for n, c in calls.items() if c["source"] in BY]
    cache = load(CACHE, {})
    todo = [n for n in targets if n not in cache]
    print(f"decision sources re-searched={sorted(BY)}  targets={len(targets)}  "
          f"cached={len(cache)}  to_fetch={len(todo)}")

    for i, nct in enumerate(todo):
        have = {p for pa in lit.get(nct, {}).get("papers", []) for p in pa["pmids"]}
        q = f'"{nct}"'
        url = (f"{EPMC}?query={urllib.parse.quote(q)}&resultType=core&pageSize=6"
               f"&format=json")
        d = get(url)
        ps = []
        if d:
            for r in d.get("resultList", {}).get("result", []):
                pm = str(r.get("pmid") or "")
                ab = (r.get("abstractText", "") or "")[:9000]
                if pm and pm not in have and len(ab) >= 120:
                    ps.append({"title": r.get("title", "") or "", "pmids": [pm],
                               "year": str(r.get("pubYear", "") or ""),
                               "abstract": ab, "source": "epmc_ft"})
        cache[nct] = ps
        if i % 200 == 0:
            json.dump(cache, open(CACHE, "w"))
            print(f"  {i}/{len(todo)}", flush=True)
    json.dump(cache, open(CACHE, "w"))

    # merge into extra_papers.json so classify picks it up alongside registry refs
    ex = load(os.path.join(WORK, "extra_papers.json"), {})
    added = 0
    for nct, ps in cache.items():
        if ps:
            ex.setdefault(nct, [])
            known = {p["pmids"][0] for p in ex[nct] if p.get("pmids")}
            for p in ps:
                if p["pmids"][0] not in known:
                    ex[nct].append(p)
                    added += 1
    json.dump(ex, open(os.path.join(WORK, "extra_papers.json"), "w"))
    print(f"full-text abstracts added={added}  "
          f"trials with any full-text hit={sum(1 for v in cache.values() if v)}")


if __name__ == "__main__":
    main()
