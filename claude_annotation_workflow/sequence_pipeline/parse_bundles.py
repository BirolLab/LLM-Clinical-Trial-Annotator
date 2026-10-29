import re, json, glob, os
SRC = "/projects/btl/ezhang/ctg_lookup/ctg_api_out/bundles_chunks"
out = open("work/bundle_parsed.jsonl", "w")
hdr = re.compile(r'(?m)^# (NCT\d+)\s*$')
for p in sorted(glob.glob(SRC + "/*.md")):
    t = open(p).read()
    parts = hdr.split(t)
    for i in range(1, len(parts), 2):
        nct = parts[i]; body = parts[i+1]
        sec = None
        chembl = []; uni = []; lit = []; feats = []
        for ln in body.split("\n"):
            if ln.startswith("### "):
                sec = ln[4:].strip(); continue
            if not ln.startswith("- "): continue
            if sec == "chembl":
                pref = re.search(r'pref_name=([^;]*)$', ln)
                mt = re.search(r'molecule_type=([^;]*);', ln)
                syn = sorted(set(re.findall(r'synonyms=([^;]*)', ln)))
                cid = re.search(r'\[(CHEMBL\d+)\]', ln)
                chembl.append({"id": cid.group(1) if cid else "", "pref": (pref.group(1).strip() if pref else ""),
                               "type": (mt.group(1).strip() if mt else ""), "syn": syn})
            elif sec == "uniprot":
                acc = re.search(r'primaryAccession=([A-Z0-9]+)', ln)
                nm = re.search(r'fullName\.value=([^;]*);', ln)
                sq = re.search(r'sequence\.value=([A-Z]+)', ln)
                sp = re.search(r'scientificName=([^;]*);', ln)
                if acc: uni.append({"acc": acc.group(1), "name": nm.group(1).strip() if nm else "",
                                    "sp": sp.group(1).strip() if sp else "", "seq": sq.group(1) if sq else ""})
            elif sec == "ebi_proteins_features":
                feats.append(ln[2:400])
            elif sec and ("[" in sec and "]" in sec and re.search(r'\(\d{4}\)', sec)):
                lit.append(ln[2:])
        out.write(json.dumps({"nct": nct, "chembl": chembl, "uni": uni, "feats": feats[:0], "lit_n": len(lit)}) + "\n")
out.close()
print("ok")
