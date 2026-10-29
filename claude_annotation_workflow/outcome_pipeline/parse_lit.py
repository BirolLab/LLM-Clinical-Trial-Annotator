#!/usr/bin/env python3
"""Pull the ## Literature sections out of bundles_chunks/chunk_*.md (methodology S2-S3).

Molecular evidence is parsed out and discarded: it describes the compound, never
the trial. Emits work/lit.json = [{nct, order, papers:[{title,year,pmids,abstract}]}]
in source order, one entry per '# NCT...' heading.
"""
import glob, json, os, re, sys

BUNDLES = os.environ.get("BUNDLES", "bundles_chunks")
WORK = os.environ.get("OUTCOME_WORK", "outcome_pipeline/work")

# '### Title. (YYYY) [pmid pmid]'  -- year and pmid list are both optional
PAPER_RE = re.compile(r"^###\s+(.*?)\s*(?:\((\d{4}|n\.?d\.?)\))?\s*(?:\[([0-9 ]+)\])?\s*$")


def chunk_sort_key(p):
    m = re.search(r"(\d+)", os.path.basename(p))
    return (int(m.group(1)) if m else 0, p)


def main():
    files = sorted(glob.glob(os.path.join(BUNDLES, "chunk_*.md")), key=chunk_sort_key)
    if not files:
        sys.exit(f"no chunk_*.md under {BUNDLES}")

    out, order = [], 0
    cur = None          # current trial record
    section = None      # 'lit' | 'mol' | None
    paper = None        # current paper dict
    buf = []            # abstract lines for the current paper

    def close_paper():
        nonlocal paper, buf
        if paper is not None:
            paper["abstract"] = re.sub(r"\s+", " ", " ".join(buf)).strip()
            if paper["title"] or paper["abstract"]:
                cur["papers"].append(paper)
        paper, buf = None, []

    for fp in files:
        with open(fp, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line.startswith("# NCT"):
                    close_paper()
                    nct = line[2:].strip()
                    order += 1
                    cur = {"nct": nct, "order": order, "chunk": os.path.basename(fp),
                           "papers": []}
                    out.append(cur)
                    section = None
                    continue
                if cur is None:
                    continue
                if line.startswith("## "):
                    close_paper()
                    low = line.lower()
                    section = "lit" if low.startswith("## literature") else "mol"
                    continue
                if section != "lit":
                    continue
                if line.startswith("### "):
                    close_paper()
                    m = PAPER_RE.match(line)
                    title = (m.group(1) if m else line[4:]).strip()
                    year = m.group(2) if m and m.group(2) else ""
                    pmids = (m.group(3) or "").split() if m else []
                    paper = {"title": title, "year": year, "pmids": pmids,
                             "source": "bundle"}
                    buf = []
                    continue
                if paper is not None:
                    if line.strip() and line.strip() != "---":
                        buf.append(line.strip())
    close_paper()

    os.makedirs(WORK, exist_ok=True)
    with open(os.path.join(WORK, "lit.json"), "w") as fh:
        json.dump(out, fh)

    n_pap = sum(len(t["papers"]) for t in out)
    n_with = sum(1 for t in out if t["papers"])
    n_abs = sum(1 for t in out for p in t["papers"] if len(p["abstract"]) >= 120)
    print(f"trials={len(out)} unique={len({t['nct'] for t in out})} "
          f"papers={n_pap} trials_with_papers={n_with} papers_with_real_abstract={n_abs}")


if __name__ == "__main__":
    main()
