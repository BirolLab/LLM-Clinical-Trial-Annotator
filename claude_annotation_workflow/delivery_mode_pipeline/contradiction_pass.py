#!/usr/bin/env python3
"""Methodology 11.2/11.3, 'CTG record states a route the drug does not have'.

Narrow by design. A row is corrected only when ALL hold:
  * the label came from the intervention DESCRIPTION or lower (never the
    intervention NAME -- a named product form such as "Leuprolide Oral Tablet"
    is real evidence and must survive);
  * the trial resolves to exactly one peptide drug;
  * that drug has a v-quality injection/infusion route in drug_routes.tsv;
  * the row is labelled Oral, and the quoted snippet is a bare dose/route phrase
    carrying no dosage-form noun other than the contradicted one.
Corrections cite the retrieved table entry verbatim and keep the superseded wording.
"""
import csv, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lex

csv.field_size_limit(10**8)
SRC, DST = sys.argv[1], sys.argv[2]
PIPE = os.path.dirname(os.path.abspath(__file__))

routes = {}
for line in open(os.path.join(PIPE, "drug_routes.tsv")):
    if line.startswith("#") or not line.strip():
        continue
    p = line.rstrip("\n").split("\t")
    if len(p) >= 5:
        routes[lex.norm(p[0])] = (p[1].strip(), p[2].strip(), p[3].strip(), p[4].strip())

TIER_OK = re.compile(r"\| intervention description |\| description of arm |"
                     r"\| (?:brief|official) title: |\| (?:summary|detail) sentence ")
FORM = re.compile(r"\b(?:tablets?|capsules?|caplets?|pills?|sachets?|syrup|gumm\w+|"
                  r"solution|suspension|powder|granules?|drops?|lozenges?|film)\b", re.I)

# `names_itself` only looks at wording ORALW can see, so a form of oral wording
# missing here makes the pass correct a row it should have left alone
# ("Ingested Interferon Alpha" -> injection; oral interferon is the study drug).
ORALW = re.compile(r"\boral(?:ly)?\b|\btablets?\b|\bcapsules?\b|\bp\.?o\.?\b|"
                   r"\bby mouth\b|\bper os\b|\bingest(?:ed|ion|s|ing)?\b|"
                   r"\bswallow\w*\b|\bsachets?\b|\bgumm(?:y|ies)\b|\bpills?\b|"
                   r"\bdrink\w*\b|\benteral\w*\b|\bsyrup\b|\blozenges?\b", re.I)
# the route word belongs to whichever agent shares its clause
CLAUSE = re.compile(r"\band\b|\bplus\b|\bvs\.?\b|\bversus\b|\bcompared (?:to|with)\b|"
                    r"[;+]|\bfollowed by\b|\bwhereas\b|\bwhile\b", re.I)

def clause_of(low, pos):
    """The run of text around `pos` bounded by the nearest clause separators."""
    start, end = 0, len(low)
    for mo in CLAUSE.finditer(low):
        if mo.end() <= pos:
            start = mo.end()
        elif mo.start() > pos:
            end = mo.start()
            break
    return low[start:end], start
NEAR = 30

def _nearest(low, toks, pos):
    best = None
    for t in toks:
        for tm in re.finditer(r"\b" + re.escape(t), low):
            d = abs(tm.start() - pos)
            if best is None or d < best:
                best = d
    return best

def names_itself(snip, drug):
    """Does the oral wording belong to the peptide rather than to a co-drug?

    True when a token of the peptide's own name sits within NEAR chars of the
    oral wording AND no known co-administered non-peptide agent sits closer
    ("Alogliptin 12.5 mg, tablets, orally, once daily and insulin": the tablets
    are alogliptin's). Run 5 added the co-drug comparison; the bare proximity
    test let that whole class through.
    """
    toks = [t for t in lex.norm(drug).split()
            if len(t) > 3 and t not in lex.ROUTE_WORDS and t != "unspecified"]
    toks += [t for t in lex.PEP_ALIAS.get(lex.norm(drug), ())]
    if not toks:
        return False
    low = snip.lower()
    rivals = [d for d in lex.CO_DRUGS if d in low and d not in toks]
    for mo in ORALW.finditer(low):
        clause, off = clause_of(low, mo.start())
        in_clause = any(re.search(r"\b" + re.escape(t), clause) for t in toks)
        rival_in_clause = any(re.search(r"\b" + re.escape(r), clause) for r in rivals)
        if rival_in_clause and not in_clause:
            continue                      # the route word is the co-drug's
        dp = _nearest(low, toks, mo.start())
        if dp is None or dp > NEAR:
            continue
        dr = _nearest(low, rivals, mo.start())
        if dr is None or dr >= dp or in_clause:
            return True
    return False

TIER_MARK = re.compile(r"^(?:intervention (?:name|description) |other names |"
                       r"description of arm |(?:brief|official) title: |"
                       r"(?:summary|detail) sentence |drug-level route |"
                       r"trial-level |generic study description|context class:|"
                       r"bundled abstract|chembl |no delivery wording|"
                       r"peptide measured|no peptide drug)", re.I)

def head_drugs(ev):
    """Peptide drug list, stopping at the first evidence-tier marker (11.3).

    Multiple drugs are themselves ' | '-separated, so cutting at the first
    separator silently truncates the list and makes a 3-drug trial look
    single-drug -- which is exactly the gate this pass relies on.
    """
    if not ev.startswith("peptide drug(s): "):
        return []
    out = []
    for seg in ev[len("peptide drug(s): "):].split(" | "):
        if TIER_MARK.match(seg):
            break
        if seg.strip():
            out.append(seg.strip())
    return out

rows = list(csv.DictReader(open(SRC)))
fixed = 0
for r in rows:
    if r["Delivery Mode"] not in ("Oral", "Topical", "Other"):
        continue
    ev = r["Evidence"]
    if not TIER_OK.search(ev) or "intervention name " in ev:
        continue
    drugs = head_drugs(ev)
    if len(drugs) != 1:
        continue
    e = routes.get(lex.norm(drugs[0]))
    if not e or e[0] != "injection/infusion" or e[3] != "v":
        continue
    if r["Delivery Mode"] != "Oral":
        # outside Oral the only safe trigger is clause-level mis-attribution:
        # the route word shares its clause with a co-drug and not the peptide
        m = re.search(r': "(.*?)"(?:\s*\[|$)', ev)
        snip0 = m.group(1) if m else ""
        low0 = snip0.lower()
        toks0 = [t for t in lex.norm(drugs[0]).split()
                 if len(t) > 3 and t not in lex.ROUTE_WORDS and t != "unspecified"]
        toks0 += list(lex.PEP_ALIAS.get(lex.norm(drugs[0]), ()))
        rivals0 = [d for d in lex.CO_DRUGS if d in low0 and d not in toks0]
        if not rivals0 or any(re.search(r"\b" + re.escape(t), low0) for t in toks0):
            continue
    snip = re.search(r': "(.*?)"(?:\s*\[|$)', ev)
    snip = snip.group(1) if snip else ""
    forms = {f.lower() for f in FORM.findall(snip)}
    if len(forms) > 1 or len(snip) > 220:
        continue
    # If the oral wording sits next to the peptide's OWN name, the record is
    # asserting an oral form of that peptide (oral insulin, oral PTH, octreotide
    # tablets) -- that is evidence, not a slip. Only correct when the oral wording
    # is unattached or attached to something else.
    if names_itself(snip, drugs[0]):
        continue
    # an explicit structured route declaration is not a slip
    if re.search(r"route of administration\s*:?\s*oral|pharmaceutical form\s*:",
                 snip, re.I):
        continue
    old_label = r["Delivery Mode"]
    r["Delivery Mode"] = "injection/infusion"
    old_conf = r["Confidence"]
    r["Confidence"] = "Medium"
    r["Evidence"] = (f'peptide drug(s): {drugs[0]} | drug-level route for "{drugs[0]}": '
                     f'"{e[1]}" (source: {e[2]}; quality v) '
                     f'[corrected on review: was {old_label}/{old_conf}; the record states a '
                     f'route this drug does not have, or states a co-drug\'s; '
                     f'superseded wording: "{snip}"]')
    fixed += 1

with open(DST, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["NCT Number", "Delivery Mode", "Confidence", "Evidence"])
    w.writeheader()
    w.writerows(rows)
print(f"corrected {fixed} rows -> {DST}")
