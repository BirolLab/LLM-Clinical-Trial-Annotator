"""Walks the row set and applies the section 4 tiers in order.  Writes the
deliverable and the sidecar."""
import csv, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, rules
from rules import (classify_text, classify_narrative, classify_dispositions,
                   classify_publication, classify_results, status_prior, norm, POINTER,
                   drug_terms)

W = config.WORK

def load(name, key="nct_id"):
    d = {}
    p = os.path.join(W, name)
    if os.path.exists(p):
        for l in open(p):
            r = json.loads(l)
            d[r[key]] = r
    return d

def one_line(s, cap=320):
    s = re.sub(r"\s+", " ", (s or "").replace("\\", "")).strip()
    return (s[:cap] + "…") if len(s) > cap else s

def manual_overrides():
    p = os.path.join(os.path.dirname(__file__), "manual.json")
    return json.load(open(p)) if os.path.exists(p) else {}

def cascade(nct, base, det, lit, refs, in_failure_set):
    """Section 4 tiers 1-6, in order; stop at the first that yields a bucket."""
    status = base["status"]
    ws = norm(base["why_stopped"])
    first = None

    # tier 1 -- the stated stop reason (5.1 resolves a pointer first)
    if ws:
        if POINTER.match(ws) and det.get(nct, {}).get("detailed", "").strip():
            # 5.1: the pointer says the stop reason IS the detailed description, so
            # substitute it wholesale.  The 4.1 study-as-subject gate exists to filter
            # protocol boilerplate out of a general description and would discard a
            # termination narrative whose subject is the drug programme.
            dd = det[nct]["detailed"].strip()
            d = (classify_text(dd, status, source="whyStopped -> DetailedDescription")
                 if len(dd) <= 1200 else None)
            if not (d and d.get("reason")):
                d = classify_narrative(dd, status, "whyStopped -> DetailedDescription")
            if d and d["reason"]:
                d["note"] = (['the stated reason was a pointer ("%s"), resolved from the detailed '
                              'description (5.1)' % one_line(ws, 60)] + d["note"])
                return d
        else:
            d = classify_text(ws, status)
            if d and d["reason"]:
                return d
            first = d                                     # non-failure / uninformative

    if not in_failure_set:
        return first

    # tier 2 -- other registry narrative fields (4.1)
    r = det.get(nct, {})
    for field, label in (("detailed", "DetailedDescription"),
                         ("limitations", "posted-results Limitations and Caveats"),
                         ("recruitment_details", "participant-flow Recruitment Details")):
        if (r.get(field) or "").strip():
            d = classify_narrative(r[field], status, label)
            if d and d["reason"]:
                return d
    if r.get("dispositions"):
        d = classify_dispositions(r["dispositions"], status)
        if d and d["reason"]:
            return d

    # tiers 3-4 -- bundle literature
    terms = drug_terms(base.get("interventions", ""))
    papers = lit.get(nct, {}).get("papers", [])
    if papers:
        d = classify_publication(papers, status, start_year=(base.get("start_date") or "")[:4],
                                 terms=terms, nct=nct)
        if d and d["reason"]:
            return d

    # tier 5 -- registry-listed references (6.4)
    rp = refs.get(nct, {}).get("papers", [])
    if rp:
        d = classify_publication(rp, status, source="registry-listed reference",
                                 start_year=(base.get("start_date") or "")[:4])
        if d and d["reason"]:
            return d

    # tier 6 -- posted results
    if r.get("outcomes"):
        d = classify_results(r["outcomes"])
        if d:
            return d
    return first


def evidence_for(d, nct, base, outcome, in_failure_set, located):
    status = base["status"] or "unknown"
    if d and d.get("reason"):
        parts = [f'{d["basis"]}: "{one_line(d["quote"])}"']
        if d.get("cite"):
            parts.append("source: " + one_line(d["cite"], 140))
        parts.append("sub-reason: " + (d["sub"] or "n/a"))
        parts.append("arbitration: " + d["rule"])
        parts += [n for n in d.get("note", [])]
        parts.append(f"registry status {status}; upstream outcome {outcome}")
        ev = "; ".join(parts)
        if d["confidence"] == "Low":
            ev = "LOW CONFIDENCE: " + ev
        return ev
    # ---- NONE classes.  Fixed, greppable opening phrases (section 1).
    if not in_failure_set:
        ev = (f"LOW CONFIDENCE: no failure is on record for this trial — the upstream "
              f"outcome determination is {outcome} and registry status is {status}, so no "
              f"reason for failure is owed")
        if located:
            ev += (f'; a statement was located that would read as {located[0]} '
                   f'("{one_line(located[1], 160)}") but it is not adopted, because naming why '
                   f'a trial failed when nothing calls it a failure is incoherent (1.1)')
        return ev + ". Treat this row as not a failure."
    tail = (f" registry status {status}; upstream outcome {outcome}. "
            f"Treat this row as unresolved.")
    if d and d["basis"].startswith("NONE - stated reason describes a non-failure"):
        return ("LOW CONFIDENCE: no reason for failure is on record — the stated stop reason "
                f'describes a non-failure stop ("{one_line(d["quote"])}"), so nothing on record '
                f"says why this trial failed;" + tail)
    if d and d["basis"].startswith("NONE - stated reason carries no reason"):
        return ("LOW CONFIDENCE: no reason for failure is on record — the stated stop reason "
                f'names no cause ("{one_line(d["quote"])}");' + tail)
    return ("LOW CONFIDENCE: no reason for failure is on record — nothing in the stated stop "
            "reason, the other registry narrative fields, the bundle literature or the posted "
            "results states why this trial failed;" + tail)


def main():
    base = load("ctg_base.jsonl")
    det = load("ctg_detail.jsonl")
    lit = load("lit.jsonl")
    refs = load("refs.jsonl")
    man = manual_overrides()
    oc = {}
    for r in csv.DictReader(open(config.OUTCOME_CSV)):
        oc[r[config.OUTCOME_ID_COL].strip().upper()] = r[config.OUTCOME_COL].strip()
    ids = sorted(oc)                                  # row set = outcome ids (no label set exists)

    out = csv.writer(open(config.OUT_CSV, "w", newline=""))
    out.writerow(config.OUT_COLS)
    side = csv.writer(open(config.SIDECAR_CSV, "w", newline=""))
    side.writerow(config.SIDECAR_COLS)

    import collections
    stats = collections.Counter()
    for nct in ids:
        b = base.get(nct, {"status": "", "why_stopped": "", "has_results": False})
        outcome = oc[nct]
        status = (b.get("status") or "").upper()
        in_fs = (outcome == config.OUTCOME_NEGATIVE or
                 (outcome == config.OUTCOME_NODETERMINATION and status in config.STOPPED_EARLY))
        d = cascade(nct, b, det, lit, refs, in_fs)
        override_ev = None
        located = None
        if not in_fs and d and d.get("reason"):
            located = (d["reason"], d["quote"])
            d = {"reason": None, "confidence": "Low",
                 "basis": "NONE - outcome not negative", "sub": "", "note": [],
                 "quote": d["quote"], "rule": "1.1 reason owed only where the outcome is negative"}
        if nct in man:                                        # section 11 external overrides
            m = man[nct]
            if m.get("reason"):
                d = dict(reason=m["reason"], confidence=m.get("confidence", "Low"),
                         basis="external reference", sub=m.get("sub", ""),
                         note=m.get("note", []), quote=m["evidence"],
                         rule="11 external source")
            else:
                # an external source that establishes there is no failure reason to give:
                # the row keeps the residual and carries the finding verbatim (11, 1.1).
                d = None
                override_ev = m["evidence"]
        reason = (d["reason"] if d and d.get("reason") else None)
        conf = (d["confidence"] if d else "Low")
        basis = (d["basis"] if d else
                 ("NONE - external source: no failure reason to give"
                  if override_ev else "NONE - no reason on record"))
        if reason is None:
            conf = "Low"
            if not (d and d["basis"].startswith("NONE")):
                basis = ("NONE - external source: no failure reason to give"
                         if override_ev else "NONE - no reason on record")
        shown = reason if reason else config.RESIDUAL      # 1.2a: residual-filled
        ev = (override_ev if (nct in man and not man[nct].get("reason"))
              else evidence_for(d, nct, b, outcome, in_fs, located))
        out.writerow([nct, shown, conf, ev])
        side.writerow([nct, shown, conf, basis, b.get("status", ""), outcome,
                       "yes" if in_fs else "no", status_prior(status),
                       (d["sub"] if d else ""), (located[0] if located else ""),
                       (d["rule"] if d else ""), ev])
        stats[("failure-set" if in_fs else "other", basis.split(" - ")[0], shown)] += 1

    print(f"rows written: {len(ids)}")
    print("\n--- failure set, by reason")
    fs = collections.Counter({k[2]: v for k, v in stats.items() if k[0] == "failure-set"})
    tot = 0
    for k, v in collections.Counter(
            {kk[2]: sum(vv for k2, vv in stats.items() if k2[0] == "failure-set" and k2[2] == kk[2])
             for kk in stats if kk[0] == "failure-set"}).most_common():
        print(f"{v:6d}  {k}"); tot += v
    print(f"{tot:6d}  TOTAL in failure set")

if __name__ == "__main__":
    main()
