"""Per-trial bundle '## Literature' text, keyed by NCT id."""
import glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

REC = re.compile(r"^# (NCT\d+)\s*$", re.M)
PAPER = re.compile(r"^### (.*?)\s*(?:\((\d{4})\))?\s*(?:\[(\d+)\])?\s*$")

def records(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    hits = list(REC.finditer(txt))
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(txt)
        yield m.group(1), txt[m.end():end]

def lit_section(body):
    m = re.search(r"^## Literature.*?$", body, re.M)
    if not m:
        return ""
    nxt = re.search(r"^## ", body[m.end():], re.M)
    return body[m.end(): m.end() + nxt.start()] if nxt else body[m.end():]

def papers(sec):
    out, cur = [], None
    for line in sec.splitlines():
        h = PAPER.match(line)
        if h:
            if cur:
                out.append(cur)
            cur = {"title": h.group(1).strip(), "year": h.group(2) or "",
                   "pmid": h.group(3) or "", "abstract": ""}
        elif cur is not None and line.strip():
            cur["abstract"] += (" " if cur["abstract"] else "") + line.strip()
    if cur:
        out.append(cur)
    return out

def main():
    n = 0
    with open(sys.argv[1], "w") as out:
        for path in sorted(glob.glob(config.CORPUS_GLOB)):
            for nct, body in records(path):
                out.write(json.dumps({"nct_id": nct, "papers": papers(lit_section(body))}) + "\n")
                n += 1
    print("records:", n)

if __name__ == "__main__":
    main()
