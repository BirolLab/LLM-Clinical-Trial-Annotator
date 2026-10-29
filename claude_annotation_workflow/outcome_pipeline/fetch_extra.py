#!/usr/bin/env python3
"""Abstracts for registry-listed RESULT/DERIVED references (methodology S3 src 3).

Driven off the unresolved set from the previous classify pass, so it touches a
strictly smaller set than the corpus (S11). Abstracts cached by PMID in
work/pmid_abs.json; the per-trial view is written to work/extra_papers.json.
"""
import json, os, sys, time, urllib.parse, urllib.request

WORK = os.environ.get("OUTCOME_WORK", "outcome_pipeline/work")
ABS = os.path.join(WORK, "pmid_abs.json")
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
BATCH = 25


def load(p, d):
    return json.load(open(p)) if os.path.exists(p) else d


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


def main():
    st = load(os.path.join(WORK, "status.json"), {})
    lit = {t["nct"]: t for t in load(os.path.join(WORK, "lit.json"), [])}
    unres = set(load(os.path.join(WORK, "unresolved.json"), []))
    have = {n: {p for pa in lit[n]["papers"] for p in pa["pmids"]} for n in lit}

    # Fetching stays driven off the unresolved set (S11 cost discipline), but the
    # per-trial VIEW is rebuilt from scratch each run, so it must cover every trial
    # with registry refs -- not just this run's unresolved set. Restricting the view
    # silently drops the RESULT/DERIVED papers of trials an earlier pass resolved,
    # and those decisions fall through to the S7 convention instead.
    all_refs = {}
    for n in lit:
        new = [(r["pmid"], r["type"]) for r in st.get(n, {}).get("refs", [])
               if r["pmid"] and r["pmid"] not in have.get(n, set())]
        if new:
            all_refs[n] = new

    by_nct = {n: v for n, v in all_refs.items() if n in unres}
    want = {p for v in by_nct.values() for p, _ in v}

    cache = load(ABS, {})
    todo = sorted(want - set(cache))
    print(f"trials={len(by_nct)} pmids_wanted={len(want)} cached={len(cache)} to_fetch={len(todo)}")

    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        q = " OR ".join(f"EXT_ID:{p}" for p in batch)
        url = (f"{EPMC}?query={urllib.parse.quote(q)}&resultType=core&pageSize={BATCH}"
               f"&format=json")
        d = get(url)
        if d:
            for r in d.get("resultList", {}).get("result", []):
                pm = str(r.get("pmid") or r.get("id") or "")
                if pm:
                    cache[pm] = {"title": r.get("title", "") or "",
                                 "abstract": (r.get("abstractText", "") or "")[:9000],
                                 "year": str(r.get("pubYear", "") or ""),
                                 "journal": (r.get("journalInfo", {}) or {})
                                            .get("journal", {}).get("title", "")}
        for p in batch:
            cache.setdefault(p, {"title": "", "abstract": "", "year": "", "journal": ""})
        if (i // BATCH) % 20 == 0:
            json.dump(cache, open(ABS, "w"))
            print(f"  {i + len(batch)}/{len(todo)}", flush=True)
    json.dump(cache, open(ABS, "w"))

    extra = {}
    for n, refs in all_refs.items():
        ps = []
        for pm, typ in refs:
            a = cache.get(pm) or {}
            if len(a.get("abstract", "")) >= 120:
                ps.append({"title": a["title"], "year": a["year"], "pmids": [pm],
                           "abstract": a["abstract"], "source": "registry_ref",
                           "reftype": typ})
        if ps:
            extra[n] = ps
    json.dump(extra, open(os.path.join(WORK, "extra_papers.json"), "w"))
    got = sum(1 for p in want if len(cache.get(p, {}).get("abstract", "")) >= 120)
    print(f"abstracts_retrieved={got}/{len(want)}  trials_gaining_papers={len(extra)}"
          f"  (fetch_set={len(by_nct)} view_set={len(all_refs)})")


if __name__ == "__main__":
    main()
