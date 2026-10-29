#!/usr/bin/env python3
"""Registry posted results for trials that have them (methodology S3 src 4, S6).

Primary-outcome analyses (p-values), serious-AE and death group totals,
limitations-and-caveats text. Cached by NCT id in work/detail.json.
"""
import json, os, sys, time, urllib.parse, urllib.request

WORK = os.environ.get("OUTCOME_WORK", "outcome_pipeline/work")
CACHE = os.path.join(WORK, "detail.json")
API = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = ("OutcomeMeasureTitle,OutcomeMeasureType,OutcomeAnalysisPValue,"
          "OutcomeAnalysisStatisticalMethod,OutcomeAnalysisPValueComment,"
          "EventGroupSeriousNumAffected,EventGroupSeriousNumAtRisk,"
          "EventGroupDeathsNumAffected,EventGroupDeathsNumAtRisk,EventGroupTitle,"
          "LimitationsAndCaveatsDescription,NCTId")
BATCH = 20


def load(path, default):
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return default


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                print(f"  FAIL {e}", file=sys.stderr)
                return None
            time.sleep(2 * (i + 1))


def flat(s):
    nct = s.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "")
    rs = s.get("resultsSection", {}) or {}
    oms = rs.get("outcomeMeasuresModule", {}).get("outcomeMeasures", []) or []
    out_m = []
    for om in oms:
        pv = []
        for a in om.get("analyses", []) or []:
            if a.get("pValue"):
                pv.append({"p": str(a.get("pValue")),
                           "method": a.get("statisticalMethod", ""),
                           "comment": (a.get("pValueComment", "") or "")[:200]})
        out_m.append({"type": om.get("type", ""), "title": (om.get("title", "") or "")[:300],
                      "pvalues": pv})
    groups = []
    for g in rs.get("adverseEventsModule", {}).get("eventGroups", []) or []:
        groups.append({"title": (g.get("title", "") or "")[:120],
                       "ser": g.get("seriousNumAffected"), "ser_at": g.get("seriousNumAtRisk"),
                       "dead": g.get("deathsNumAffected"), "dead_at": g.get("deathsNumAtRisk")})
    return {"nct": nct, "outcomes": out_m, "ae_groups": groups,
            "caveats": (rs.get("moreInfoModule", {})
                        .get("limitationsAndCaveats", {}).get("description", "") or "")[:600]}


def main():
    status = load(os.path.join(WORK, "status.json"), {})
    lit = load(os.path.join(WORK, "lit.json"), [])
    # only trials the method can still need: has posted results and status is not decisive
    undecided = {"COMPLETED", "UNKNOWN"}
    want = [t["nct"] for t in lit
            if status.get(t["nct"], {}).get("has_results")
            and status.get(t["nct"], {}).get("status") in undecided]
    cache = load(CACHE, {})
    todo = [n for n in want if n not in cache]
    print(f"with_results_and_undecided={len(want)} cached={len(cache)} to_fetch={len(todo)}")

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
        for n in batch:
            cache.setdefault(n, {"nct": n, "outcomes": [], "ae_groups": [], "caveats": ""})
        if (i // BATCH) % 20 == 0:
            with open(CACHE, "w") as fh:
                json.dump(cache, fh)
            print(f"  {i + len(batch)}/{len(todo)}", flush=True)

    with open(CACHE, "w") as fh:
        json.dump(cache, fh)
    n_p = sum(1 for n in want if any(o["pvalues"] for o in cache[n]["outcomes"]
                                     if o["type"] == "PRIMARY"))
    n_ae = sum(1 for n in want if cache[n]["ae_groups"])
    print(f"primary_with_pvalues={n_p}  with_ae_groups={n_ae}")


if __name__ == "__main__":
    main()
