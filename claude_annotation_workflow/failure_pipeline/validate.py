"""The invariants of section 10.4, asserted against both inputs by name."""
import csv, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

fails = []
def chk(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{(' -- ' + detail) if detail else ''}")
    if not ok:
        fails.append(name)

out = list(csv.DictReader(open(config.OUT_CSV)))
side = {r["NCT Number"]: r for r in csv.DictReader(open(config.SIDECAR_CSV))}
oc = {r[config.OUTCOME_ID_COL].strip().upper(): r[config.OUTCOME_COL].strip()
      for r in csv.DictReader(open(config.OUTCOME_CSV))}

ids = [r["NCT Number"] for r in out]
chk("row set == outcome-table ids (union evaluation ids; none exist)",
    set(ids) == set(oc), f"{len(ids)} rows vs {len(oc)} ids in {os.path.basename(config.OUTCOME_CSV)}")
chk("no id dropped, none invented", len(ids) == len(oc) == len(set(ids)))
chk("identifiers upper-cased and unique",
    all(re.fullmatch(r"NCT\d{8}", i) for i in ids) and len(set(ids)) == len(ids))
chk("columns are exactly the requested schema",
    list(out[0].keys()) == config.OUT_COLS, ", ".join(out[0].keys()))
chk("bucket values subset of the target vocabulary",
    set(r["Reason for Failure"] for r in out) <= set(config.VOCAB),
    "; ".join(sorted(set(r["Reason for Failure"] for r in out))))
chk("confidence subset of {High, Medium, Low}",
    set(r["Confidence"] for r in out) <= {"High", "Medium", "Low"})
chk("Basis non-empty on every row", all(side[i]["Basis"] for i in ids))
chk("no empty Evidence", all(r["Evidence"].strip() for r in out))
chk("no embedded newlines", not any("\n" in r["Evidence"] or "\r" in r["Evidence"] for r in out))
low = [r for r in out if r["Confidence"] == "Low"]
chk("every Low row's Evidence begins LOW CONFIDENCE:",
    all(r["Evidence"].startswith("LOW CONFIDENCE:") for r in low), f"{len(low)} Low rows")
chk("no non-Low row claims LOW CONFIDENCE",
    not [r for r in out if r["Confidence"] != "Low" and "LOW CONFIDENCE" in r["Evidence"]])
none_rows = [i for i in ids if side[i]["Basis"].startswith("NONE")]
chk("Basis startswith NONE <=> Evidence declares no reason was on record",
    all(side[i]["Evidence"].startswith("LOW CONFIDENCE: no ") for i in none_rows)
    and not [i for i in ids if not side[i]["Basis"].startswith("NONE")
             and side[i]["Evidence"].startswith("LOW CONFIDENCE: no ")],
    f"{len(none_rows)} NONE rows, all greppable on 'LOW CONFIDENCE: no '")
chk("the residual-vs-prior choice is uniform (section 1.2a)",
    all(side[i]["Reason for Failure"] == config.RESIDUAL for i in none_rows)
    and all(side[i]["Status Prior"] for i in ids),
    "residual-filled; the status prior is on every row so either metric is derivable")
fs = [i for i in ids if side[i]["In Failure Set"] == "yes"]
chk("a non-residual reason => outcome negative AND Basis != NONE",
    not [i for i in ids if side[i]["Reason for Failure"] != config.RESIDUAL
         and (side[i]["In Failure Set"] != "yes" or side[i]["Basis"].startswith("NONE"))])
chk("no row names a reason while its Evidence says nothing calls it a failure",
    not [i for i in ids if side[i]["Reason for Failure"] != config.RESIDUAL
         and "no failure is on record" in side[i]["Evidence"]])
chk("every negative-outcome row carries a decision",
    not [i for i in ids if oc[i] == config.OUTCOME_NEGATIVE
         and not side[i]["Reason for Failure"]],
    f"{sum(1 for i in ids if oc[i] == config.OUTCOME_NEGATIVE)} negative-outcome rows")
chk("failure set is recoverable from the deliverable without a re-join",
    not [i for i in ids if (side[i]["In Failure Set"] == "yes")
         != (not out[ids.index(i)]["Evidence"].startswith("LOW CONFIDENCE: no failure is on record"))
         ] if False else
    all((side[i]["In Failure Set"] == "no") ==
        side[i]["Evidence"].startswith("LOW CONFIDENCE: no failure is on record") for i in ids),
    "non-failure rows open 'LOW CONFIDENCE: no failure is on record'")
chk("deliverable and sidecar agree row-for-row",
    all(side[r["NCT Number"]]["Reason for Failure"] == r["Reason for Failure"]
        and side[r["NCT Number"]]["Confidence"] == r["Confidence"]
        and side[r["NCT Number"]]["Evidence"] == r["Evidence"] for r in out))

print(f"\n{'ALL INVARIANTS PASS' if not fails else 'FAILED: ' + '; '.join(fails)}")
sys.exit(1 if fails else 0)
