#!/usr/bin/env python3
"""Agreement against a labelled subset, if one exists (methodology S9.5).

Chance-corrected (Gwet's AC1 and Cohen's kappa), joined on the intersection,
annotator-vs-annotator reported first because human-human agreement is the
ceiling, and broken out per decision source.
"""
import csv, json, os, sys
from collections import Counter, defaultdict

WORK = os.environ.get("OUTCOME_WORK", "outcome_pipeline/work")
TRAIN = os.environ.get("OUTCOME_TRAIN", "train_df.csv")

# The output vocabulary is now the labelled subset's own vocabulary (S1), so the map
# is an identity on the labels a labelled file actually carries, case-normalised.
MAP = {"positive": "Positive", "failed - completed trial": "Failed - completed trial",
       "terminated": "Terminated", "suspended": "Suspended", "withdrawn": "Withdrawn",
       "active": "Active", "unknown": "Unknown"}
LABELS = ["Positive", "Failed - completed trial", "Terminated", "Suspended",
          "Withdrawn", "Active", "Unknown"]


def norm(v):
    return MAP.get((v or "").strip().lower())


def ac1(a, b):
    """Gwet's AC1: chance agreement from the mean marginal, robust to a lopsided
    label distribution in a way kappa is not."""
    n = len(a)
    if not n:
        return float("nan")
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    cats = set(a) | set(b)
    pe = 0.0
    for c in cats:
        pi = (a.count(c) + b.count(c)) / (2 * n)
        pe += pi * (1 - pi)
    pe /= max(len(cats) - 1, 1)
    return (po - pe) / (1 - pe) if pe != 1 else float("nan")


def kappa(a, b):
    n = len(a)
    if not n:
        return float("nan")
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[c] / n * cb[c] / n for c in set(a) | set(b))
    return (po - pe) / (1 - pe) if pe != 1 else float("nan")


def report(name, a, b):
    if not a:
        print(f"{name:34s} n=0")
        return
    po = sum(1 for x, y in zip(a, b) if x == y) / len(a)
    print(f"{name:34s} n={len(a):4d}  raw={po:.3f}  AC1={ac1(a,b):+.3f}  kappa={kappa(a,b):+.3f}")


def main():
    calls = {c["nct"]: c for c in json.load(open(os.path.join(WORK, "calls.json")))}
    rows = list(csv.DictReader(open(TRAIN)))
    # the labelled file writes ids lower-case; normalise before joining (S9.5)
    for r in rows:
        r["_id"] = (r.get("nct_id") or "").strip().upper()

    # --- coverage, reported separately (S9.5): ids outside the corpus cannot be
    # labelled by any method applied to it.
    ids = [r["_id"] for r in rows]
    in_corpus = [i for i in ids if i in calls]
    print(f"labelled rows={len(ids)}  in corpus={len(in_corpus)}  "
          f"outside corpus={len(ids) - len(in_corpus)} (excluded from every figure below)\n")

    # --- human vs human first: this is the ceiling
    hh = [(norm(r["Outcome_ann1"]), norm(r["Outcome_ann2"])) for r in rows
          if r["_id"] in calls]
    hh = [(x, y) for x, y in hh if x and y]
    print("=== annotator vs annotator (the ceiling) ===")
    report("ann1 vs ann2", [x for x, _ in hh], [y for _, y in hh])
    dis = Counter((x, y) for x, y in hh if x != y)
    print("  top disagreements (ann1 -> ann2):")
    for (x, y), n in dis.most_common(6):
        print(f"    {n:4d}  {x:9s} -> {y}")

    print("\n=== pipeline vs each annotator ===")
    for ann in ("Outcome_ann1", "Outcome_ann2"):
        pairs = [(calls[r["_id"]]["outcome"], norm(r[ann])) for r in rows
                 if r["_id"] in calls and norm(r[ann])]
        report(f"pipeline vs {ann}", [x for x, _ in pairs], [y for _, y in pairs])

    # --- per decision source (S9.5)
    print("\n=== pipeline vs ann1, per decision source ===")
    by = defaultdict(list)
    for r in rows:
        g = norm(r["Outcome_ann1"])
        if r["_id"] in calls and g:
            c = calls[r["_id"]]
            by[c["source"]].append((c["outcome"], g))
    for src, pairs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        report("  " + src, [x for x, _ in pairs], [y for _, y in pairs])

    print("\n=== pipeline vs ann1, per confidence ===")
    byc = defaultdict(list)
    for r in rows:
        g = norm(r["Outcome_ann1"])
        if r["_id"] in calls and g:
            c = calls[r["_id"]]
            byc[c["confidence"]].append((c["outcome"], g))
    for cf in ("High", "Medium", "Low"):
        if byc[cf]:
            report("  " + cf, [x for x, _ in byc[cf]], [y for _, y in byc[cf]])

    # --- confusion against ann1
    print("\n=== confusion, pipeline (rows) x ann1 (cols) ===")
    cm = Counter()
    for r in rows:
        g = norm(r["Outcome_ann1"])
        if r["_id"] in calls and g:
            cm[(calls[r["_id"]]["outcome"], g)] += 1
    print("            " + "".join(f"{l:>26s}" for l in LABELS))
    for p in LABELS:
        print(f"{p:26s} " + "".join(f"{cm[(p,g)]:26d}" for g in LABELS))

    # --- the S7 convention check: Completed-with-no-trail subset
    print("\n=== S7 re-validation: Completed trials with NO paper trail ===")
    st = json.load(open(os.path.join(WORK, "status.json")))
    nt = []
    for r in rows:
        g = norm(r["Outcome_ann1"])
        n = r["_id"]
        if n in calls and g and st.get(n, {}).get("status") == "COMPLETED":
            s = st[n]
            trail = bool(s.get("refs")) or s.get("has_results")
            if not trail and calls[n]["source"] in ("unknown", "convention"):
                nt.append(g)
    print(f"  n={len(nt)}  gold labels: {dict(Counter(nt))}")
    print("  (extend the convention to no-trail rows only if positives clearly "
          "outnumber unknowns here)")


if __name__ == "__main__":
    main()
