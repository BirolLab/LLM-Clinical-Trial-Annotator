"""Score the deliverable against a labelled subset (methodology section 10.5).

Prints coverage BEFORE accuracy, pins the category set, accounts for every dropped
row by id, and splits the evidence-backed and residual halves.
"""
import csv, os, sys, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

VOCAB = ["business reason", "recruitment issues", "ineffective for purpose",
         "toxic/unsafe", "due to covid", "na_value"]          # pinned: q = 6 always
NORM = {"business reasons": "business reason", "due to covid-19 pandemic": "due to covid",
        "unknown": "na_value", "": "na_value", "nan": "na_value"}

def norm(x):
    v = (x or "").strip().lower()
    return NORM.get(v, v or "na_value")

def ac1(a, b, cats=VOCAB):
    """Gwet's AC1 over a FIXED category list, so pe is comparable across pairings."""
    N = len(a)
    if N == 0:
        return float("nan")
    q = len(cats)
    pa = sum(1 for x, y in zip(a, b) if x == y) / N
    pe = sum((lambda pi: pi * (1 - pi))(((a.count(k) / N) + (b.count(k) / N)) / 2)
             for k in cats) / (q - 1)
    return (pa - pe) / (1 - pe)

def boot_diff(a, b1, b2, n_boot=5000, seed=42):
    rng = np.random.default_rng(seed)
    a, b1, b2 = np.array(a), np.array(b1), np.array(b2)
    N = len(a)
    d = []
    for _ in range(n_boot):
        i = rng.integers(0, N, N)
        d.append(ac1(list(a[i]), list(b1[i])) - ac1(list(a[i]), list(b2[i])))
    d = np.array(d)
    d = d[~np.isnan(d)]
    obs = ac1(list(a), list(b1)) - ac1(list(a), list(b2))
    lo, hi = np.percentile(d, [2.5, 97.5])
    p = float(np.mean(np.abs(d - obs) >= np.abs(obs)))
    return obs, lo, hi, p

def main(label_path):
    gold = list(csv.DictReader(open(label_path)))
    mine = {r["NCT Number"]: r for r in csv.DictReader(open(config.OUT_CSV))}
    side = {r["NCT Number"]: r for r in csv.DictReader(open(config.SIDECAR_CSV))}
    oc = {r[config.OUTCOME_ID_COL].strip().upper(): r[config.OUTCOME_COL].strip()
          for r in csv.DictReader(open(config.OUTCOME_CSV))}

    # ---- COVERAGE FIRST (section 13). Account for every row by id.
    tot = len(gold)
    ids = [r["nct_id"].strip().upper() for r in gold]          # case-normalised join
    present = [i for i in ids if i in mine]
    absent = [i for i in ids if i not in mine]
    g_reason = {i: norm(r["Reason for Failure_ann1"]) for i, r in zip(ids, gold)}
    g_reason2 = {i: norm(r["Reason for Failure_ann2"]) for i, r in zip(ids, gold)}
    labelled = [i for i in ids if g_reason[i] != "na_value"]
    reachable = [i for i in labelled if i in mine]
    reached = [i for i in reachable if norm(mine[i]["Reason for Failure"]) != "na_value"]

    print(f"=== COVERAGE (read this before any accuracy figure) ===")
    print(f"  label file rows                      : {tot}")
    print(f"  present in the deliverable           : {len(present)}")
    print(f"  ABSENT from the deliverable's corpus : {len(absent)}  <- never scoreable")
    print(f"  ann1 gave a reason on                : {len(labelled)}")
    print(f"  ...of those, in the deliverable      : {len(reachable)}")
    print(f"  ...of those, we name a reason        : {len(reached)}"
          f"  => coverage {len(reached)}/{len(reachable)} = {100*len(reached)/max(1,len(reachable)):.1f}%")
    if len(reached) < len(reachable):
        print(f"  coverage < 1.0 means a SCOPE problem; no rule change touches it (section 10.5):")
        for i in reachable:
            if norm(mine[i]["Reason for Failure"]) == "na_value":
                print(f"      {i}  ann1={g_reason[i]:24s} upstream outcome={oc.get(i,'?'):9s}"
                      f" in failure set={side[i]['In Failure Set']}")

    # ---- slices
    slices = {
        "all label rows present in the deliverable": lambda i: True,
        "upstream outcome == Negative": lambda i: oc.get(i) == config.OUTCOME_NEGATIVE,
        "both annotators called the outcome negative":
            lambda i: gold_by[i]["Outcome_ann1"].strip().lower() == "negative"
                  and gold_by[i]["Outcome_ann2"].strip().lower() == "negative",
    }
    gold_by = {i: r for i, r in zip(ids, gold)}
    for lab, pred in slices.items():
        sel = [i for i in present if pred(i)]
        if not sel:
            continue
        a1 = [g_reason[i] for i in sel]
        a2 = [g_reason2[i] for i in sel]
        hl = [norm(mine[i]["Reason for Failure"]) for i in sel]
        print(f"\n=== {lab}   n={len(sel)}   (q={len(VOCAB)} pinned categories) ===")
        print(f"  AC1 mine vs ann1          : {ac1(hl,a1):.3f}")
        print(f"  AC1 mine vs ann2          : {ac1(hl,a2):.3f}")
        print(f"  AC1 ann1 vs ann2 (ceiling): {ac1(a1,a2):.3f}")
        obs, lo, hi, p = boot_diff(a1, a2, hl)
        print(f"  delta (HH - HL) = {obs:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]  p = {p:.4f}")
        # halves: evidence-backed vs residual (section 10.5)
        for half, keep in (("Basis != NONE (located text)", lambda i: not side[i]["Basis"].startswith("NONE")),
                           ("Basis == NONE (nothing on record)", lambda i: side[i]["Basis"].startswith("NONE"))):
            sub = [i for i in sel if keep(i)]
            if sub:
                print(f"    {half:36s} n={len(sub):3d}  AC1 vs ann1 = "
                      f"{ac1([norm(mine[i]['Reason for Failure']) for i in sub],[g_reason[i] for i in sub]):.3f}")
        # miss cross-tab by Basis x registry status
        miss = [i for i in sel if g_reason[i] != norm(mine[i]["Reason for Failure"])]
        if miss:
            print(f"    {len(miss)} disagreements with ann1, by route x status:")
            for k, v in collections.Counter(
                    (side[i]["Basis"].split(" (")[0], side[i]["Registry Status"]) for i in miss).most_common():
                print(f"      {v:3d}  {k[0]} / {k[1]}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(config.ROOT, "train_df.csv"))
