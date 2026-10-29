#!/usr/bin/env python3
"""Write the output CSV and assert the S9.4 invariants before shipping."""
import csv, json, os, re, sys

WORK = os.environ.get("OUTCOME_WORK", "outcome_pipeline/work")
OUT = os.environ.get("OUTCOME_CSV", "outcome_10_26_2026.csv")

# S1 vocabulary: the three registry-stop kinds are separate labels and a reported
# failure on a trial that was not stopped early is "Failed - completed trial".
OUTCOMES = {"Positive", "Failed - completed trial", "Terminated", "Suspended",
            "Withdrawn", "Active", "Unknown"}
CONFS = {"High", "Medium", "Low"}
NCT_RE = re.compile(r"^NCT\d{8}$")


def main():
    calls = json.load(open(os.path.join(WORK, "calls.json")))
    lit = json.load(open(os.path.join(WORK, "lit.json")))

    # --- S9.4: exactly one row per '# NCT...' heading, in source order
    order = [t["nct"] for t in lit]
    assert len(calls) == len(order), f"{len(calls)} calls vs {len(order)} headings"
    assert [c["nct"] for c in calls] == order, "rows are not in corpus source order"
    assert len(set(order)) == len(order), "duplicate NCT ids in the corpus"

    errs = []
    for c in calls:
        if not NCT_RE.match(c["nct"]):
            errs.append(f"{c['nct']}: malformed NCT id")
        if c["outcome"] not in OUTCOMES:
            errs.append(f"{c['nct']}: outcome '{c['outcome']}' outside vocabulary")
        if c["confidence"] not in CONFS:
            errs.append(f"{c['nct']}: confidence '{c['confidence']}' outside vocabulary")
        for k in ("nct", "outcome", "confidence", "evidence"):
            if not str(c.get(k, "")).strip():
                errs.append(f"{c['nct']}: empty {k}")
        if c["confidence"] == "Low" and not c["evidence"].startswith("LOW CONFIDENCE:"):
            errs.append(f"{c['nct']}: Low row missing the LOW CONFIDENCE: prefix")
        if c["confidence"] != "Low" and c["evidence"].startswith("LOW CONFIDENCE:"):
            errs.append(f"{c['nct']}: non-Low row carries the LOW CONFIDENCE: prefix")
        # S9.4: the stop labels and the reported-failure label are mutually exclusive,
        # and a stop label must quote the status it came from.
        if c["outcome"] in ("Terminated", "Suspended", "Withdrawn"):
            if c["source"] != "status-stopped":
                errs.append(f"{c['nct']}: stop label from source '{c['source']}'")
            if f"registry status: {c['outcome']}" not in c["evidence"]:
                errs.append(f"{c['nct']}: stop label does not quote its registry status")
        if c["outcome"] == "Failed - completed trial" and c["source"] == "status-stopped":
            errs.append(f"{c['nct']}: reported-failure label on a stopped trial")
        if c["outcome"] != "Unknown":
            if not re.search(r"registry|bundle|literature|Europe PMC|posted results|convention",
                             c["evidence"], re.I):
                errs.append(f"{c['nct']}: non-Unknown evidence names no source")
    if errs:
        print(f"INVARIANT FAILURES ({len(errs)}):", file=sys.stderr)
        for e in errs[:40]:
            print("  " + e, file=sys.stderr)
        sys.exit(1)

    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        w.writerow(["NCT Number", "Outcome", "Confidence", "Evidence"])
        for c in calls:
            ev = re.sub(r"\s+", " ", c["evidence"]).strip()
            w.writerow([c["nct"], c["outcome"], c["confidence"], ev])

    print(f"wrote {OUT}: {len(calls)} rows; all S9.4 invariants pass")


if __name__ == "__main__":
    main()
