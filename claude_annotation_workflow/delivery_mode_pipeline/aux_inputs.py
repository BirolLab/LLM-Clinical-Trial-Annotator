#!/usr/bin/env python3
"""work/abstracts_by_nct.tsv (tier 9) and work/chembl_terms.tsv (tier 11)."""
import csv, json, os, collections
DATA = os.environ.get("DM_DATA", ".")
WORK = os.environ.get("DM_WORK", "work")
csv.field_size_limit(10**8)

abs_by = collections.defaultdict(list)
with open(os.path.join(DATA, "abstracts.csv"), newline="") as f:
    for r in csv.DictReader(f):
        nct = (r.get("nct_id") or "").strip().upper()
        txt = ((r.get("title") or "") + " " + (r.get("abstract") or "")).strip()
        if nct.startswith("NCT") and txt:
            abs_by[nct].append(txt)
with open(os.path.join(WORK, "abstracts_by_nct.tsv"), "w") as out:
    for nct, txts in abs_by.items():
        blob = " ".join(txts)
        out.write(nct + "\t" + " ".join(blob.split())[:20000] + "\n")
print("abstracts:", len(abs_by), "trials")

# per (drug query) ChEMBL route flags; keep only drugs where flags are consistent
agg = collections.defaultdict(lambda: {"oral": set(), "parenteral": set(), "topical": set(),
                                       "molecule_type": set(), "pref_name": set()})
with open(os.path.join(DATA, "by_source", "chembl.jsonl")) as f:
    for line in f:
        try: r = json.loads(line)
        except Exception: continue
        q = (r.get("query") or "").strip().lower()
        if not q: continue
        a = agg[q]
        for k in ("oral", "parenteral", "topical"):
            v = r.get(k)
            if v not in (None, ""): a[k].add(str(v))
        for k in ("molecule_type", "pref_name"):
            v = r.get(k)
            if v: a[k].add(str(v))
with open(os.path.join(WORK, "chembl_terms.tsv"), "w") as out:
    out.write("drug\toral\tparenteral\ttopical\tmolecule_type\tpref_name\n")
    for q, a in sorted(agg.items()):
        def flag(k):
            s = a[k]
            return "1" if "True" in s or "1" in s else ("0" if s else "")
        out.write("\t".join([q, flag("oral"), flag("parenteral"), flag("topical"),
                             ";".join(sorted(a["molecule_type"]))[:60],
                             ";".join(sorted(a["pref_name"]))[:80]]) + "\n")
print("chembl drug terms:", len(agg))
