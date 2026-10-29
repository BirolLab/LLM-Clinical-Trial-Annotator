#!/usr/bin/env python3
"""work/trials_drugs.tsv  <- bundles_chunks/ctg-studies-peptide-seqs.csv  (methodology 9.1)
Columns: nct_id, peptide drugs ('|'-joined), interventions the drugs were read from."""
import csv, os, re, sys
DATA = os.environ.get("DM_DATA", ".")
WORK = os.environ.get("DM_WORK", "work")
src = os.path.join(DATA, "bundles_chunks", "ctg-studies-peptide-seqs.csv")
csv.field_size_limit(10**8)
rows = []
with open(src, newline="") as f:
    for r in csv.DictReader(f):
        nct = (r.get("nct_id") or "").strip().upper()
        if not nct.startswith("NCT"):
            continue
        drugs = (r.get("peptide_drug(s)") or "").strip()
        ivs = re.findall(r"\[interventions:\s*([^\]]*)\]", r.get("Evidence") or "")
        iv_names = []
        for blob in ivs:
            for nm in blob.split(","):
                nm = nm.strip()
                if nm and nm not in iv_names:
                    iv_names.append(nm)
        if not iv_names:
            iv_names = [x.strip() for x in (r.get("interventions") or "").split("|") if x.strip()]
        rows.append((nct, drugs, " | ".join(iv_names)))
os.makedirs(WORK, exist_ok=True)
with open(os.path.join(WORK, "trials_drugs.tsv"), "w") as out:
    out.write("nct_id\tpeptide_drugs\tinterventions\n")
    for r in rows:
        out.write("\t".join(x.replace("\t", " ") for x in r) + "\n")
print(len(rows), "trials;", sum(1 for r in rows if r[1]), "with a named peptide drug")
