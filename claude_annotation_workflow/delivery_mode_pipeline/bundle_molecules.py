#!/usr/bin/env python3
"""work/bundle_molecules.tsv  <- bundles_chunks/*.md

The only drug-identity evidence the bundles carry is the ChEMBL block: per trial,
the molecules the corpus search matched, each with a `pref_name` and a
`molecule_type` (Protein / Antibody / Enzyme / Small molecule / ...).  That is the
corpus's own statement of why a trial is in scope, so it is used to resolve the
peptide/protein drug for trials the identification run never covered
(methodology 8.4 on a grown dataset).

Columns: nct_id, protein-ish pref_names ('|'-joined), all molecule types seen.
"""
import glob, os, re, collections

DATA = os.environ.get("DM_DATA", ".")
WORK = os.environ.get("DM_WORK", "work")
# Only ChEMBL's protein-ish classes.  "Unknown" covers excipients, foods and
# unregistered small molecules (METFORMIN GLYCINATE, MALTODEXTRIN, DIANEAL), and
# including it made those the trial's "peptide".
PEPTIDEY = {"Protein", "Antibody", "Enzyme", "Antibody drug conjugate"}

names = collections.defaultdict(list)   # nct -> [(pref_name, type)]
types = collections.defaultdict(set)
nct = None
for fn in sorted(glob.glob(os.path.join(DATA, "bundles_chunks", "*.md"))):
    for line in open(fn, errors="replace"):
        if line.startswith("# NCT"):
            nct = line[2:].strip().split()[0]
            names.setdefault(nct, [])
            continue
        if nct is None or not line.startswith("- ["):
            continue
        mt = re.search(r"molecule_type=([A-Za-z][A-Za-z ]*?)(?:;|$)", line)
        pn = re.search(r"pref_name=([^;\n]+)", line)
        if not mt:
            continue
        t = mt.group(1).strip()
        types[nct].add(t)
        if pn and t in PEPTIDEY:
            p = pn.group(1).strip()
            if p and p.lower() not in ("unchecked", "non-protein target", "none"):
                names[nct].append((p, t))

os.makedirs(WORK, exist_ok=True)
out = open(os.path.join(WORK, "bundle_molecules.tsv"), "w")
out.write("nct_id\tprotein_names\tmolecule_types\n")
n_pep = 0
for k in sorted(names):
    seen, keep = set(), []
    for p, t in names[k]:
        if p.lower() not in seen:
            seen.add(p.lower()); keep.append(p)
    if keep:
        n_pep += 1
    out.write("%s\t%s\t%s\n" % (k, " | ".join(keep), ";".join(sorted(types[k]))))
out.close()
print(len(names), "trials;", n_pep, "with a protein/antibody/enzyme ChEMBL match")
