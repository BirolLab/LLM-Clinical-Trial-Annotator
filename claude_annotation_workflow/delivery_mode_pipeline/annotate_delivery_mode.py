#!/usr/bin/env python3
"""Delivery-mode annotation. Methodology section 5 (tiers 0-12), with the
proximity guard of 10.2 and the ordering refinements of 9.3/10.2."""
import csv, json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lex

DATA = os.environ.get("DM_DATA", ".")
WORK = os.environ.get("DM_WORK", "work")
OUT  = os.environ.get("DM_OUT", "delivery_mode_out.csv")
PIPE = os.path.dirname(os.path.abspath(__file__))
csv.field_size_limit(10**8)
SLACK = 10      # chars of slack the peptide gets before a nearer rival wins (10.2)
ADJACENT = 15   # a peptide token this close to the route word always wins

def ws(s):
    return " ".join((s or "").split())

# ------------------------------------------------------------------- inputs
trials = {}
with open(os.path.join(WORK, "trials_drugs.tsv")) as f:
    next(f)
    for line in f:
        p = line.rstrip("\n").split("\t")
        if len(p) >= 3:
            trials[p[0]] = {"drugs": [d.strip() for d in p[1].split("|") if d.strip()],
                            "ivnames": [x.strip() for x in p[2].split(" | ") if x.strip()]}

ctg = {}
with open(os.path.join(WORK, "ctg_raw.jsonl")) as f:
    for line in f:
        r = json.loads(line)
        ctg[r["nct"]] = r

abstracts = {}
ap = os.path.join(WORK, "abstracts_by_nct.tsv")
if os.path.exists(ap):
    for line in open(ap):
        k, _, v = line.rstrip("\n").partition("\t")
        abstracts[k] = v

# The bundles' only drug-identity evidence: the ChEMBL molecules the corpus search
# matched per trial, with their molecule_type.  Used to resolve the peptide/protein
# drug for trials the identification run never covered (methodology 8.4 / 14.1).
bundle_mol = {}
bp = os.path.join(WORK, "bundle_molecules.tsv")
if os.path.exists(bp):
    with open(bp) as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3:
                bundle_mol[p[0]] = {
                    "proteins": [x.strip() for x in p[1].split("|") if x.strip()],
                    "types": set(x for x in p[2].split(";") if x)}

# pref_names that are not a drug the trial gives (reagents, blood products, test
# controls, sterilisation indicators), or are too generic to pin an intervention on.
PREF_STOP = re.compile(
    r"blood grouping|blood, whole|blood cells|schick test|biological indicator|"
    r"sterilizat|test strip|test antigen|silver protein|^protein hydrolysate$|"
    r"^angiotensin|^insulin$|^peptide|serum, anti|^globulin serum|non-protein|"
    r"unchecked|^gene$|^cell$|, rat$|, horse$|, bovine$|, porcine$", re.I)

def pref_keys(name):
    """Normalised match keys for a ChEMBL pref_name."""
    n = lex.norm(re.sub(r"\(.*?\)", " ", name).split(",")[0])
    if not n or len(n) < 4:
        return []
    toks = n.split()
    keys = [n]
    if len(toks) > 1:
        keys.append(" ".join(toks[:2]))
    keys.append(toks[0])
    return [k for k in dict.fromkeys(keys) if len(k) >= 5]


def load_table(fn, keycol=0, normalise=False):
    out = {}
    path = os.path.join(PIPE, fn)
    if not os.path.exists(path):
        return out
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        p = line.rstrip("\n").split("\t")
        if len(p) >= 4:
            k = p[keycol].strip()
            k = lex.norm(k) if normalise else k.lower()
            out[k] = {"mode": p[1].strip(), "phrase": p[2].strip(),
                                              "source": p[3].strip(),
                                              "quality": (p[4].strip() if len(p) > 4 else "i")}
    return out

drug_routes  = load_table("drug_routes.tsv", normalise=True)
trial_routes = load_table("trial_routes.tsv")

chembl = {}
cp = os.path.join(WORK, "chembl_terms.tsv")
if os.path.exists(cp):
    with open(cp) as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 4:
                chembl[p[0]] = (p[1], p[2], p[3])

# Tokens that are the class half of a canonical drug name, never the half that
# identifies it.  Matching on these would make any insulin "the" insulin of the
# trial and any protein the peptide (run 8).
DRUG_CLASS_TOK = {
    "insulin", "human", "humanized", "recombinant", "peptide", "peptides",
    "protein", "hormone", "analogue", "analog", "vaccine", "acetate", "sodium",
    "chloride", "sulfate", "sulphate", "hydrochloride", "phosphate", "citrate",
    "tartrate", "mesylate", "succinate", "diacetate", "trifluoroacetate",
    "unspecified", "product", "solution", "injection", "infusion", "tablet",
    "capsule", "release", "acting", "factor", "growth", "stimulating", "colony",
    "releasing", "receptor", "antagonist", "agonist", "inhibitor", "alpha",
    "beta", "gamma", "delta", "complex", "conjugate", "derivative", "purified",
}

# ------------------------------------------------- peptide identification
def resolve_peptide_ivs(nct, rec, drugs, ivnames):
    """Which CTG interventions are the peptide? Returns (list, resolved_flag).

    Order matters. `ivnames` (the `interventions:` column of trials_drugs.tsv)
    lists *every* intervention of the trial, not only the peptide's, so matching
    on it alone makes nivolumab, salbutamol or imiquimod "the peptide" and their
    routes get read for it. It is therefore a last resort, used only when the
    drug name and peptide morphology both fail to single anything out.
    """
    ivs = rec.get("interventions", []) or []
    want = {lex.norm(n) for n in ivnames if n}
    blocked, candidates = [], []
    dnorm = []
    for d in drugs:
        n = lex.norm(d)
        n = re.sub(r"\bunspecified\b", " ", n).strip()
        if n:
            dnorm.append(n)
    for iv in ivs:
        if lex.is_not_a_drug(iv.get("name", "")):
            continue
        if lex.is_receptor_blocker(iv.get("name", ""), iv.get("description", "")):
            blocked.append(iv)
            continue
        if lex.norm(iv.get("name", "")):
            candidates.append(iv)

    def named(iv):
        blob = (lex.norm(iv.get("name", "")) + " " +
                " ".join(lex.norm(o) for o in iv.get("otherNames", [])))
        for d in dnorm:
            for part in re.split(r"\s*/\s*", d):
                part = part.strip()
                if len(part) >= 4 and part in blob:
                    return True
                # 3-letter drug names (GIP, VIP, PTH, ANP) need a word boundary,
                # not a substring test, or they never match at all
                if len(part) == 3 and re.search(r"\b" + re.escape(part) + r"\b", blob):
                    return True
                # The record names the intervention by the DISTINCTIVE half of
                # the canonical drug name and nothing else -- drug
                # "insulin lispro" against interventions "Lispro", "Degludec",
                # "Glargine", "Aspart".  The substring test above only works in
                # the other direction, so these trials fell through every stage
                # and were annotated from all interventions at Low (run 8).
                # Only a long, distinctive, alphabetic token qualifies: the
                # class halves ("insulin", "human", "recombinant") would match
                # any insulin or any protein in the trial.
                for tok in part.split():
                    if (len(tok) >= 6 and tok.isalpha() and tok not in DRUG_CLASS_TOK
                            and tok not in lex.ROUTE_WORDS
                            and re.search(r"\b" + re.escape(tok) + r"\b", blob)):
                        return True
        return False

    method = "name"
    hits = [iv for iv in candidates if named(iv)]
    if not hits:
        # Keep only the best peptide rank present: a peptide outranks a
        # recombinant protein hormone, which outranks an antibody or Fc-fusion
        # protein.  Without that, rituximab's or belatacept's IV route is read
        # for a trial whose peptide is oral cyclosporine (11.2 / 13.2).
        method = "morphology"
        # Rank on the intervention's own NAME first.  CTG `otherNames` carry
        # mechanism blurbs and sometimes a different agent entirely -- prednisone
        # with otherNames ["oral antidiabetic agents", "insulin"], metformin XR
        # with "Biguanide-insulin sensitizer" -- so they turn non-peptides into
        # the trial's peptide.  They are consulted only when no name ranks.
        ranked = [(lex.peptide_rank(iv.get("name", "")), iv) for iv in candidates]
        ranked = [(r, iv) for r, iv in ranked if r]
        if not ranked:
            ranked = [(lex.peptide_rank(iv.get("name", ""),
                                        " ".join(iv.get("otherNames", []) or [])), iv)
                      for iv in candidates if lex.opaque_name(iv.get("name", ""))]
            ranked = [(r, iv) for r, iv in ranked if r]
        if ranked:
            best = min(r for r, _ in ranked)
            hits = [iv for r, iv in ranked if r == best]
            for iv in hits:
                iv["_rank"] = best
        else:
            hits = []
    if not hits:
        # The product name can be opaque while its own description says what it
        # is ("Purastat Arm" / "an aqueous self-assembling peptide solution of
        # 2.5% concentration RADA16"). Same test as the name stage, over the
        # description, and only when it singles out a strict subset -- otherwise
        # every intervention of a peptide trial qualifies.
        # Same gate as the otherNames stage: a description that happens to name a
        # peptide ("...in combination with 177Lu-DOTA-Octreotate") must not make
        # a small molecule the trial's peptide.  PuraStat-style opaque product
        # names ("Purastat Arm") are exactly the case this stage exists for.
        method = "description"
        ranked = [(lex.peptide_rank(iv.get("name", ""), iv.get("description", "")), iv)
                  for iv in candidates if lex.opaque_name(iv.get("name", ""))]
        ranked = [(r, iv) for r, iv in ranked if r]
        hits = []
        if ranked:
            best = min(r for r, _ in ranked)
            hits = [iv for r, iv in ranked if r == best]
        if len(hits) == len(candidates) and len(candidates) > 1:
            hits = []
    if not hits:
        # The bundle's ChEMBL block names the molecules the corpus matched, typed
        # Protein / Antibody / Enzyme.  Intersecting those names with the trial's
        # own interventions identifies the biologic for trials the identification
        # run never covered (cytokines, CSFs, growth factors, gonadotropins), and
        # it is the corpus's own statement of why the trial is in scope.
        method = "chembl"
        bm = bundle_mol.get(nct) or {}
        keys = []
        for pn in bm.get("proteins", []):
            if PREF_STOP.search(pn) or len(pn) > 60:
                continue
            keys.extend(pref_keys(pn))
        keys = list(dict.fromkeys(keys))
        if keys:
            hits = []
            for iv in candidates:
                blob = (lex.norm(iv.get("name", "")) + " " +
                        " ".join(lex.norm(o) for o in iv.get("otherNames", [])))
                if any(re.search(r"\b" + re.escape(k) + r"\b", blob) for k in keys):
                    hits.append(iv)
            if len(hits) == len(candidates) and len(candidates) > 1:
                hits = []
    if not hits and dnorm:
        method = "ivnames"
        # Last resort: the identification run's intervention list.  Only usable
        # when that run actually named a drug for this trial -- where it did not,
        # build_index.py falls back to writing *every* intervention into the
        # column, so it carries no peptide link at all and selecting from it
        # makes enalapril or a breakfast tray "the peptide" (12.1, again).
        hits = [iv for iv in candidates
                if lex.norm(iv.get("name", "")) in want
                or any(w and (w in lex.norm(iv.get("name", "")) or
                              lex.norm(iv.get("name", "")) in w) for w in want)]
        # it only distinguishes anything when it does not select everything
        if len(hits) == len(candidates) and len(candidates) > 1:
            hits = []
    if hits:
        for iv in hits:
            iv["_match"] = method
        return hits, True
    if blocked and not candidates:
        return [], "no-peptide"
    # fallback: annotate from all interventions as a whole, capped at Low
    return candidates, False

# --------------------------------------------------- route word extraction
def find_routes(text, case_text=None):
    """-> {label: [(match_string, position)]} over masked text."""
    if not text:
        return {}
    m = lex.mask(text)
    out = collections.defaultdict(list)
    for label, pats in lex.FAMILIES.items():
        for rx in pats:
            for mo in rx.finditer(m):
                frag = text[mo.start():mo.end()]
                if frag.strip():
                    out[label].append((frag, mo.start()))
    return dict(out)

def pick(found, drugs_label):
    """Resolve competing families: count, then PRIORITY. Returns (label, note, downgrade)."""
    if not found:
        return None, "", False
    if "injection/infusion" in found and "Other" in found:
        inj_words = " ".join(f for f, _ in found["injection/infusion"]).lower()
        oth_words = " ".join(f for f, _ in found["Other"]).lower()
        if "depot" in inj_words and "implant" in oth_words:
            found = {k: v for k, v in found.items() if k != "Other"}
    counts = {k: len(v) for k, v in found.items()}
    best = max(counts.values())
    tied = [k for k in lex.PRIORITY if counts.get(k, 0) == best]
    label = tied[0]
    others = [k for k in counts if k != label]
    note = ""
    down = False
    if others:
        note = " [competing: " + ", ".join(
            f"{k} (\"{found[k][0][0]}\")" for k in others) + "]"
        down = True
    return label, note, down

# ------------------------------------------------------ proximity guard 10.2
GENERIC_PEP = {"peptide", "peptides", "product", "products", "unidentified",
               "unspecified", "vaccine", "analogue", "analog", "hormone",
               "acid", "acetate", "human", "recombinant"}
# Class and housekeeping words that appear in intervention names and otherNames
# but do not name a competing agent. Left in the rival set they sit on top of
# the peptide's own route word ("Polymyxin B in Normal Saline" / ["Antibiotic"]
# out-competing the peptide for "irrigation").
GENERIC_CLASS = {"antibiotic", "antibiotics", "antibacterial", "antimicrobial",
                 "antifungal", "antiviral", "chemotherapy", "drug", "drugs",
                 "agent", "agents", "therapy", "treatment", "standard", "care",
                 "usual", "control", "comparator", "active", "study", "trial",
                 "group", "groups", "arm", "arms", "dose", "doses", "dosing",
                 "intervention", "experimental", "routine", "conventional"}
# Saline, water and placebo are deliberately NOT in that set: they are things
# actually given, and a route word next to them is theirs ("40 microgram nasal
# desmopressin ... and 1cc Normal Saline intravenous").

def rival_tokens(rec, peptide_ivs, field_text, pep_tok):
    rivals = set()
    # The peptide's OWN interventions are never rivals. Without this a product
    # code the drug label does not carry ("GB001", "VEGFR2-169") out-competes the
    # peptide for its own route word, because pep_tok only holds the canonical
    # drug name.
    own = {t for iv in peptide_ivs
           for t in (lex.norm(iv.get("name", "")) + " " +
                     " ".join(lex.norm(o) for o in iv.get("otherNames", []))).split()}
    # Only when the intervention was identified as the peptide on its own merits
    # (drug name or peptide morphology) AND the canonical drug name is nowhere in
    # it. Otherwise the exemption would clear a genuine co-drug that shares the
    # intervention name ("teriparatide and raloxifene") or a name picked up by
    # the ivnames fallback ("Anti-Androgen Therapy: Bicalutamide").
    methods = {iv.get("_match") for iv in peptide_ivs}
    specific = {t for t in pep_tok if t not in GENERIC_PEP}
    if methods - {"name", "morphology"} or (specific & own):
        own = set()
    pep_ids = {id(iv) for iv in peptide_ivs}
    for iv in rec.get("interventions", []) or []:
        # A co-intervention's otherNames identify the same rival agent its name
        # does, and are often the only place that agent is actually named
        # ("Standard Care Arm" / otherNames ["Sucralfate enemas - ..."]). Never
        # for the peptide's own interventions: its trade name sits on top of its
        # own route word ("Ciclosporin" / "CicloMulsion", "Polymyxin B in Normal
        # Saline" / "Antibiotic").
        blob = lex.norm(iv.get("name", ""))
        if id(iv) not in pep_ids:
            blob += " " + " ".join(lex.norm(o) for o in (iv.get("otherNames", []) or []))
        for t in blob.split():
            if len(t) > 3 and t not in lex.ROUTE_WORDS and t not in pep_tok and t not in own:
                rivals.add(t)
    low = (field_text or "").lower()
    for d in lex.CO_DRUGS:
        if d in low and d not in pep_tok:
            rivals.add(d)
    rivals -= lex.ROUTE_WORDS
    rivals -= pep_tok
    # salt and class words carried by the peptide's own name ("leuprorelin
    # acetate") are not a rival drug, and sit right on top of its route word
    rivals -= GENERIC_PEP
    rivals -= GENERIC_CLASS
    return rivals

# Clause separators (12.2). "or" is included here but NOT in the
# contradiction pass: "cultured gut microbiota rectally or oral vancomycin"
# puts each agent in its own clause, and distance alone keeps the wrong one.
_COMBO = re.compile(r"\s+(?:plus|and|with|\+|&)\s+", re.I)

CLAUSE_SEP = re.compile(r"\band\b|\bor\b|\bplus\b|\bvs\.?\b|\bversus\b|"
                        r"\bcompared (?:to|with)\b|[;+]|\bfollowed by\b|"
                        r"\bwhereas\b|\bwhile\b|\. |"
                        # records bullet a regimen rather than punctuating it:
                        # "* Bicalutamide is administered orally on a daily
                        # basis * GnRH Agonist as prescribed" is two clauses
                        r"(?:^|\s)[*\u2022\u00b7]\s*|\n", re.I)

def _clause(low, pos):
    """The run of text around `pos` bounded by the nearest clause separators."""
    start, end = 0, len(low)
    for mo in CLAUSE_SEP.finditer(low):
        if mo.end() <= pos:
            start = mo.end()
        elif mo.start() > pos:
            end = mo.start()
            break
    return low[start:end]

def guard_ok(field_text, pos, pep_tok, rivals):
    """A route word is kept only if the peptide is not out-competed by a rival."""
    if not field_text:
        return True
    low = field_text.lower()
    # Clause-level attribution (12.2) runs first: once two agents are within a
    # few characters of each other distance is the wrong instrument. A route
    # word whose own clause names a rival and not the peptide is not the
    # peptide's, however close the peptide sits in the next clause.
    cl = _clause(low, pos)
    cl_r = any(re.search(r"\b" + re.escape(t), cl) for t in rivals)
    cl_p = any(re.search(r"\b" + re.escape(t), cl) for t in pep_tok)
    if cl_r and not cl_p:
        return False
    def nearest(toks):
        best = None
        for t in toks:
            for mo in re.finditer(r"\b" + re.escape(t), low):
                d = abs(mo.start() - pos)
                if best is None or d < best:
                    best = d
        return best
    dp = nearest(pep_tok)
    dr = nearest(rivals)
    if dr is None:
        return True
    if dp is None:
        return False
    if dp <= ADJACENT:
        return True
    return dr + SLACK >= dp

# Generic ways the peptide's own intervention text refers to itself ("one mg of
# each peptide will be administered by subcutaneous injection"). Used only inside
# that intervention's own description, where the referent is unambiguous.
SELF_REF = {"peptide", "peptides", "vaccine", "vaccines", "immunotherapy",
            "study drug", "investigational"}

NEAR = 30

def route_adjacent_to_peptide(text, hits, pep_tok):
    """Does the route word sit right next to the peptide's own name? Then the text
    is asserting that peptide's route and weaker tiers must not override it."""
    low = (text or "").lower()
    for _, pos in hits:
        for t in pep_tok:
            for tm in re.finditer(r"\b" + re.escape(t), low):
                if abs(tm.start() - pos) <= NEAR:
                    return True
    return False

SWITCH = re.compile(r"\b(?:convert(?:ed|ing)?|switch(?:ed|ing)?|chang(?:ed|ing)|"
                    r"transition(?:ed|ing)?|step(?:ped)? (?:down|up)|"
                    r"rolled over|roll over)\s+to\b"
                    r"[^.;]{0,30}?", re.I)

def switch_route(text, found, pep_tok):
    """A description that gives one route first and then switches to another for
    the rest of the course ("CsA 2 mg/kg IV ... then converted to oral ... until
    day+80") is a single-label trial whose label is the maintenance route."""
    if not text or len(found) < 2:
        return None
    low = text.lower()
    pep_at = [m.start() for t in pep_tok for m in re.finditer(r"\b" + re.escape(t), low)]
    best = None
    for mo in SWITCH.finditer(text):
        # the switch must be part of the peptide's own course, not a successor
        # agent's ("followed by oral administration of anti-resorptive drug")
        if pep_at and min(abs(mo.start() - x) for x in pep_at) > 120:
            continue
        after = mo.end()
        for label, hits in found.items():
            for _, pos in hits:
                if 0 <= pos - after <= 25 and (best is None or pos < best[1]):
                    best = (label, pos)
    return best[0] if best else None

def names_any(field_text, toks):
    low = field_text.lower()
    return any(re.search(r"\b" + re.escape(t), low) for t in toks)


def form_enumeration(name):
    """Is this name a product label's list of dosage forms rather than a route?

    Three or more route words from two or more families, strung together with
    "or"/"and", is how a marketing authorisation names itself.
    """
    if not name or " or " not in name.lower():
        return False
    fams, n = set(), 0
    for fam in ("INJ", "ORAL", "TOP", "OTH"):
        for pat in getattr(lex, fam):
            for _ in re.finditer(pat, name, re.I):
                fams.add(fam)
                n += 1
    return n >= 3 and len(fams) >= 2


def name_rivals(name, rivals):
    """Rivals that may out-compete the peptide inside its own intervention name.

    rival_tokens adds every intervention's name tokens, and clears the
    peptide's own only when it was identified on its name or morphology
    (12.1).  So a peptide resolved through otherNames carries its own name
    words into the rival set: "basal" from "Basal Bolus" sat in the same
    clause as "Bolus" and discarded it.  Inside this field, a token of this
    very name counts only if it is independently known to be a drug -- in
    CO_DRUGS, a retrieved route-table key, or peptide-ranked.  "glucophage",
    "propranolol" and "betamethasone" qualify; "basal" does not.
    """
    own = {t for t in lex.norm(name).split() if len(t) > 3}
    keep = {t for t in own
            if t in lex.CO_DRUGS or t in drug_routes or lex.peptide_rank(t)}
    return (rivals - own) | (rivals & keep)


def clause_guarded(found, field_text, pep_tok, rivals):
    """Keep only route words whose own clause is not owned by a rival drug."""
    low = (field_text or "").lower()
    out = {}
    for label, hits in (found or {}).items():
        keep = []
        for h in hits:
            cl = _clause(low, h[1])
            cl_r = any(re.search(r"\b" + re.escape(t), cl) for t in rivals)
            cl_p = any(re.search(r"\b" + re.escape(t), cl) for t in pep_tok)
            if not (cl_r and not cl_p):
                keep.append(h)
        if keep:
            out[label] = keep
    return out


def guarded(found, field_text, pep_tok, rivals):
    out = {}
    for label, hits in (found or {}).items():
        keep = [h for h in hits if guard_ok(field_text, h[1], pep_tok, rivals)]
        if keep:
            out[label] = keep
    return out

# ------------------------------------------------------ context classes 5.5
DENTAL = re.compile(r"enamel|white[\s-]?spot|cari(?:es|ous)|tooth|teeth|varnish|"
                    r"periodont\w+|remineralis\w+|remineraliz\w+|dentin|gingiv\w+|"
                    r"cpp[\s-]?acp|fluoride", re.I)
FOOD = re.compile(r"supplement|gumm(?:y|ies)|smoothie|pasta|enteral|infant formula|"
                  r"beverage|dietary|nutrition(?:al)? (?:drink|product|formula)|"
                  r"milk|dairy|soy|hemp|silk|surimi|whey|casein|collagen hydroly\w+|"
                  r"hydroly[sz]ed (?:casein|collagen|whey|protein)|food|meal replacement",
                  re.I)
GRAFT = re.compile(r"bone graft|ceramic granul\w+|scaffold|spinal fusion|"
                   r"surgically (?:placed|implanted)|putty|bone substitute|"
                   r"adhesive|haemostatic|hemostatic", re.I)
VACC = re.compile(r"vaccin\w+|immuni[sz]ation|immunogenic\w*|immuni[sz]ed|"
                  r"montanide|incomplete freund|"
                  r"\bgm[\s-]?csf\b|poly[\s-]?iclc|adjuvant\w*|immunogen", re.I)
CELLPROD = re.compile(r"dendritic cells?|\bnk cells?\b|t[\s-]?cell (?:product|infusion|"
                      r"therapy|transfer)|pulsed with|peptide[\s-]?pulsed|car[\s-]?t|"
                      r"tumou?r[\s-]?infiltrating lymphocytes|\btils?\b|exosomes?|peptide[\s-]?coupled|(?:coupled|conjugated|loaded) (?:to |with )?(?:autologous )?(?:red blood cells?|rbcs?|erythrocytes?)", re.I)
ASSAY_ONLY = re.compile(
    r"\b(?:assess\w*|measur\w*|determin\w*|estimat\w*|quantif\w*|"
    r"detect\w*|analys\w*|analyz\w*|level\w*|concentration\w*)\b"
    r"[^.;]{0,60}\b(?:sera|serum|plasma|blood|saliva|urine|csf|tissue)\b"
    r"|\b(?:eli[sz]a|immunoassay)\b"
    # "baseline hormonal assay (day 3 FSH, LH, TSH ...) will be done for all
    # women" names no specimen; the no-dose/no-administration-verb condition
    # below is what keeps a real dosing description out of this branch.
    r"|\bassay(?:s|ed)?\b", re.I)
INVITRO = re.compile(r"\bin vitro\b|culture medium|cell culture|laborator\w+ assay", re.I)
DOSEWORD = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|ug|g|iu|units?|ml|"
                      r"mg/kg|mcg/kg|u/kg)\b|administer|dosing|dose|treatment with|"
                      r"receive[sd]?\b|given\b|inject|infus|oral|topical|inhal", re.I)
BIOMARKER = re.compile(r"\b(?:measur\w+|assay\w*|level\w*|concentration\w*|"
                       r"biomarker\w*|polymorphism\w*|genotyp\w+|express\w+)\b", re.I)

def table_names_a_product(rec):
    """Does some intervention name/otherName match a retrieved route-table key?

    Run 8.  The route tables are the methodology's record of products that were
    web-verified to be peptide drugs (5.4), and ~40 of them are code names with
    no morphology at all -- DGX-001, terlipressin spelled "Terlipressinum",
    GI heptapeptide.  A trial whose only intervention is one of those IS a
    peptide trial on retrieved evidence, which is stronger than morphology, so
    the identification gate has to see it.  Same matching rule as tier 7, kept
    here so the two cannot drift apart.
    """
    if rec.get("nct", "").lower() in trial_routes:
        return True
    keys = []
    for iv in (rec.get("interventions", []) or []):
        keys.append(lex.norm(iv.get("name", "")))
        for o in iv.get("otherNames", []) or []:
            keys.append(lex.norm(o))
    for k in [k for k in keys if k]:
        for dk in drug_routes:
            if dk and (dk == k or (len(dk) >= 5
                                   and re.search(r"\b" + re.escape(dk) + r"(?![0-9])", k))):
                return True
    return False


# The record frames the trial as peptide vaccination even though no
# intervention name carries any peptide morphology ("PCLUS 3-18 MN",
# "Tyrosinase, MAGE-3, GnTV").  12.3 added this as the last branch of
# context_class; run 8's identification gate needs the same signal, so it lives
# here and both read it.
RECORD_PEPTIDE_VACC = re.compile(
    r"peptide vaccin\w*|vaccination with[^.;]{0,40}peptide|"
    r"peptide[\s-]?based (?:vaccin\w*|immunotherap\w*)|"
    r"multi[\s-]?epitope|epitope peptide|synthetic long peptide", re.I)

# Run 8, second pass.  The gate's first version looked only at intervention
# text, so it fired ahead of 5.5's record-level context classes and blanked
# peptide-pulsed dendritic-cell vaccines, "Vaccines made from peptides",
# virosome-formulated peptides, an altered peptide ligand and milk-derived
# peptides -- all of which the record describes as products that are given.
# This is the record-level half of the same test: peptide wording in an
# ADMINISTRATION context.  The veto is what makes it usable, because most
# records that say "peptide" mean a measurement: C-peptide, NT-proBNP and the
# natriuretic peptides, CSF amyloid-beta, "gut peptides" as an outcome.  5.5's
# other classes are deliberately NOT accepted here -- dental, graft and the
# generic food/supplement triggers are not peptide-specific, and accepting them
# would put a label back on fluoride-varnish, pea-protein and chocolate-milk
# trials, which is what the gate exists to stop.
RECORD_PEPTIDE_PRODUCT = re.compile(
    r"peptide[\s-]?(?:vaccin\w*|puls\w+|load\w+|based|ligand|hydrolysate\w*|"
    r"conjugat\w+|immunotherap\w+|immunogen\w*|analogu?e|mimetic\w*)|"
    r"vaccin\w*[^.;]{0,30}\bpeptide|\bpeptide[^.;]{0,20}vaccin\w*|"
    r"altered peptide ligand|synthetic[^.;]{0,20}peptide|"
    r"peptides? derived from|derived peptides?|"
    r"(?:puls\w+|load\w+|immuni[sz]\w+|stimulat\w+|incubat\w+)[^.;]{0,30}"
    r"with[^.;]{0,25}peptide|"
    r"(?:administer\w*|infus\w+|inject\w+|dos\w+|given|receives?|received|"
    r"treated with|treatment with|ingest\w*|consum\w+|swallow\w*|suppl\w+ with)"
    r"[^.;]{0,30}\bpeptides?\b|"
    # dietary peptide products: the source food names the peptide, and the
    # intervention is called "Collagen", which is not an opaque name, so the
    # name-scoped test cannot see "ingest 15 grams of collagen peptides"
    r"(?:collagen|casein|whey|milk|soy|pea|fish|egg|rice|hemp|marine|bovine|"
    r"silk|surimi|potato|wheat|maize)[\s-]?(?:derived[\s-]?)?"
    r"(?:hydrolysate\w*|peptides?)|"
    r"\bpeptides?\b[^.;]{0,25}(?:administer\w*|infusion|injection|"
    r"subcutaneous\w*|intravenous\w*|intradermal\w*|orally|topical\w*)|"
    r"(?:di|tri|tetra|oligo|poly|lipo|glyco|cyclo)[\s-]?peptide", re.I)
PEPTIDE_MEASURED = re.compile(
    r"\bc[\s-]?peptide|natriuretic peptide|pro[\s-]?bnp|\bbnp\b|"
    r"amyloid[\s-]?beta[\s-]?peptide|\bab4[02]\b|gut peptides?|"
    r"peptides?[\s-]?(?:level|concentration|secretion|expression|quantitation|"
    r"measurement|profil|assay|response|release)", re.I)


SELF_DEFINES_PEPTIDE = re.compile(
    r"(?:\bis\b|\bare\b|consists? of|comprises?|contains?|incorporat\w+|"
    r"formulated|composed of|made (?:of|from)|based on|derived from)"
    r"[^.;]{0,70}?(?:peptid|polypeptid|protein\b)", re.I)


def description_calls_itself_a_peptide(iv):
    """Run 8.  14.2's gate -- consult a description only for an opaque name --
    is right for deciding WHICH intervention is the peptide: a sitagliptin arm
    whose description mentions insulin must not become the trial's peptide.  It
    is too strict for deciding WHETHER a peptide is given, because the records
    routinely define a plainly-named product in its own description:
    "Dalargin is a synthetic analog of the endogenous opioid peptide
    leucine-enkephalin", "a novel cross-linked HA hydrogel incorporating
    proline-rich peptides".  Both were blanked by the name-only test.

    The discriminator is self-reference: the peptide word has to sit in a
    defining clause about *this* intervention -- its own name (or a placeholder
    for it) followed by is/consists of/contains/incorporating within a short
    window.  Sitagliptin's description never says sitagliptin is a peptide, so
    it stays out.
    """
    desc = ws(iv.get("description", "") or "")
    if not desc:
        return False
    subj = [w for w in lex.norm(iv.get("name", "")).split() if len(w) > 3]
    subj += ["it", "this", "the study drug", "the study product", "the product",
             "the agent", "the drug", "the formulation", "the vaccine"]
    for w in subj:
        for mo in re.finditer(r"\b" + re.escape(w) + r"\b", desc, re.I):
            tail = desc[mo.end():mo.end() + 110]
            if SELF_DEFINES_PEPTIDE.match(tail.lstrip()) or \
               SELF_DEFINES_PEPTIDE.search(tail[:40] + tail[40:110]):
                if PEPTIDE_MEASURED.search(desc[max(0, mo.start() - 40):mo.end() + 110]):
                    continue
                return True
    return False


def record_names_a_peptide_product(whole):
    """Run 8: peptide wording in an administration context, minus measurement."""
    for mo in RECORD_PEPTIDE_PRODUCT.finditer(whole):
        ctx = whole[max(0, mo.start() - 60):mo.end() + 60]
        if not PEPTIDE_MEASURED.search(ctx):
            return True
    return False


def context_class(rec, peptide_ivs, pep_scope, whole):
    """(label, trigger) or (None, None). Vaccine/cell classes before food (9.3)."""
    if CELLPROD.search(pep_scope):
        return "injection/infusion", "cell product (ex-vivo peptide loading)"
    if VACC.search(pep_scope):
        return "injection/infusion", "peptide vaccine/immunisation context class"
    if DENTAL.search(whole):
        return "Topical", "dental/enamel context class"
    if GRAFT.search(whole):
        return "Other", "graft/scaffold context class"
    name_scope = " ".join(iv.get("name", "") for iv in peptide_ivs)
    if re.search(r"supplement|diet|formula", name_scope, re.I):
        return "Oral", "food/supplement context class (intervention name)"
    if FOOD.search(whole) and not lex.INJECTED_PROTEIN.search(lex.norm(pep_scope)):
        return "Oral", "food/supplement context class"
    if INVITRO.search(pep_scope):
        return "Other", "in-vitro use context class"
    # Last resort only (the tier-10 call passes `whole`): a trial whose record
    # frames it as peptide vaccination but whose intervention names are bare
    # epitope codes ("PCLUS 3-18 MN", "Tyrosinase, MAGE-3, GnTV"). Scoped to the
    # peptide's own text everywhere else, per 10.2.
    pep_names = " ".join(iv.get("name", "") for iv in peptide_ivs)
    if whole and (
            RECORD_PEPTIDE_VACC.search(whole)
            or (re.search(r"\bvaccin\w*|immuni[sz]ation", whole, re.I)
                # run 8: ...or the record names a peptide product anywhere.
                # "Virosome-formulated Peptides" is a peptide vaccine whose
                # intervention names are bare codes (PEV2A/PEV2B), so neither
                # RECORD_PEPTIDE_VACC's phrasings nor `pep_names` saw it, and
                # the row fell through to tier 12.
                and (re.search(r"peptide", pep_names, re.I)
                     or record_names_a_peptide_product(whole)))):
        return "injection/infusion", "peptide-vaccine trial (record-level context class)"
    return None, None

MONITOR = re.compile(r"ng/m[lL]|pg/m[lL]|trough|target (?:blood )?level|"
                     r"prophylaxis|vaccinat\w+|immuni[sz]\w+|titrat\w+|"
                     r"\bcontinued\b|\bper day\b|\btwice\b|\bonce\b", re.I)

def is_biomarker(pep_scope, peptide_ivs):
    # A peptide listed as a DIAGNOSTIC_TEST and described in measurement terms is
    # being assayed, whatever dosing words the sentence happens to carry.
    # Run 9: the type gate alone is not enough.  A BIOLOGICAL-typed intervention
    # whose own description is nothing but assay wording -- "assessment of
    # interleukin 23 in Sera of patients using ELIZA" (the record's spelling) --
    # is a measurement, and the registry's intervention type is simply wrong.
    # Requires an assayed specimen and no dose, so a real dosing trial is safe.
    if (peptide_ivs and ASSAY_ONLY.search(pep_scope)
            and not DOSEWORD.search(pep_scope)
            and not re.search(r"\b(?:administer\w*|inject\w*|infus\w*|treat\w*with|"
                              r"swallow\w*|appl(?:y|ied)|instill\w*|dose[sd]?)\b",
                              pep_scope, re.I)):
        return True
    if (peptide_ivs
            and all((iv.get("type", "") or "").upper() in ("DIAGNOSTIC_TEST", "OTHER")
                    for iv in peptide_ivs)
            and BIOMARKER.search(pep_scope)
            and not re.search(r"\b(?:administer\w*|inject\w*|infus\w*|"
                              r"swallow\w*|appl(?:y|ied)|instill\w*)\b",
                              pep_scope, re.I)):
        return True
    """Narrow case (10.2): the peptide is measured, never given. Requires that none
    of the peptide's own interventions is an administered-drug type."""
    if any((iv.get("type", "") or "").upper() in
           ("DRUG", "BIOLOGICAL", "DIETARY_SUPPLEMENT", "COMBINATION_PRODUCT")
           for iv in peptide_ivs):
        return False
    if not BIOMARKER.search(pep_scope):
        return False
    return not (DOSEWORD.search(pep_scope) or MONITOR.search(pep_scope))

# ------------------------------------------------------------- sentence scope
def sentences_naming(text, pep_tok):
    if not text:
        return ""
    keep = []
    for s in re.split(r"(?<=[.;])\s+|\n+", text):
        low = s.lower()
        if any(re.search(r"\b" + re.escape(t), low) for t in pep_tok):
            keep.append(s)
    return " ".join(keep)

CONF_ORDER = ["High", "Medium", "Low", "Unknown"]
def knock(conf):
    i = CONF_ORDER.index(conf)
    return CONF_ORDER[min(i + 1, 2)]

# ------------------------------------------------------------------ annotate
def annotate(nct):
    rec = ctg.get(nct) or {"nct": nct}
    t = trials.get(nct, {"drugs": [], "ivnames": []})
    drugs = t["drugs"]
    peptide_ivs, resolved = resolve_peptide_ivs(nct, rec, drugs, t["ivnames"])
    if drugs:
        dlabel = " | ".join(drugs)
    elif resolved and resolved != "no-peptide" and peptide_ivs:
        # the identification run never covered this trial; name the drug from the
        # interventions that resolved as the peptide/protein (methodology 14.1)
        seen, nm = set(), []
        for iv in peptide_ivs:
            k = lex.norm(iv.get("name", ""))
            if k and k not in seen:
                seen.add(k)
                nm.append(ws(iv.get("name", "")).lower())
        dlabel = " | ".join(nm[:3]) + (" | …" if len(nm) > 3 else "")
    else:
        dlabel = "unidentified peptide product"
    head = f"peptide drug(s): {dlabel}"
    notes = []
    if resolved == "no-peptide":
        return ("Unknown", "Unknown", ws(
            head + " | no peptide drug is administered in this trial: the only agents are "
            "a small-molecule receptor blocker and/or placebo, and the peptide named is "
            "the endogenous target"))
    if not resolved:
        notes.append("peptide drug not resolvable from record")

    pep_scope = ws(" | ".join(drugs) + " " + " ".join(
        (iv.get("name", "") + " " + iv.get("description", "") + " " +
         " ".join(iv.get("otherNames", []))) for iv in peptide_ivs))
    whole = ws(" ".join([rec.get("brief", ""), rec.get("official", ""),
                         rec.get("summary", ""), rec.get("detail", ""),
                         " ".join(iv.get("name", "") + " " + iv.get("description", "")
                                  for iv in rec.get("interventions", []) or []),
                         " ".join(a.get("label", "") + " " + a.get("description", "")
                                  for a in rec.get("arms", []) or [])]))
    # Run 8.  Methodology 5.1's "annotate from the trial's interventions as a
    # whole" fallback was written for a residue of ~100 trials where a peptide
    # clearly IS given but cannot be named.  On this corpus the residue is
    # 1,840 trials and is dominated by the opposite case: the *angiotensin* /
    # *glucagon* / *insulin* molecular searches pulled in ARB, ACE-inhibitor,
    # gliptin, diet, exercise and procedure trials that administer no peptide at
    # all (14.4 says exactly that of the 314 which reach tier 12).  Those rows
    # then took the route of whatever non-peptide the record happened to
    # describe -- melatonin -> Other, rosuvastatin -> Oral, "36h fasting" and
    # "CEST MRI sequence at 3T" -> injection/infusion.  Whether such a trial
    # ended `Unknown` or carried a label depended only on whether a route word
    # happened to be in the record, which is not a distinction about the peptide
    # at all.
    #
    # So the fallback now requires positive evidence that a peptide product is
    # given: either the record frames the trial as peptide vaccination (12.3's
    # bare-epitope vaccines, whose intervention names carry no morphology), or
    # some intervention must rank under `lex.peptide_rank` over its full text
    # (name + description + otherNames).  The second test is a weaker use of
    # that text than 14.2 forbids -- it decides whether to keep a whole-trial
    # label, never WHICH intervention is the peptide, so a description that
    # merely mentions a peptide cannot put a small molecule's route on the row.
    # Without it the honest answer is `Unknown`, which is what 8.7 asks for:
    # a wrong label costs more than a blank one.
    if (dlabel == "unidentified peptide product" and not resolved
            and not RECORD_PEPTIDE_VACC.search(whole)
            and not record_names_a_peptide_product(whole)
            # 5.1's radiopeptide pattern, not a bare isotope: a formoterol
            # inhalation trial with an 18F sub-study is not a peptide trial
            and not (lex.ISOTOPE.search(lex.norm(whole))
                     and lex.CHELATOR.search(lex.norm(whole)))
            and not table_names_a_product(rec)
            and not any(
                lex.peptide_rank(
                    iv.get("name", ""),
                    # 14.2's gate applies here too: a sitagliptin arm whose
                    # description mentions insulin must not count as peptide
                    # evidence.  The description and otherNames are consulted
                    # only for an opaque product name, which is the case this
                    # test exists for (PB1023, DPX-Survivac, "Purastat Arm").
                    ((iv.get("description", "") or "") + " " +
                     " ".join(iv.get("otherNames", []) or []))
                    if lex.opaque_name(iv.get("name", "")) else "")
                or description_calls_itself_a_peptide(iv)
                for iv in (rec.get("interventions", []) or []))):
        iv_list = "; ".join(ws(iv.get("name", "")) for iv in
                            (rec.get("interventions", []) or [])
                            if ws(iv.get("name", "")))[:200]
        return ("Unknown", "Unknown", ws(
            head + " | no peptide drug is identified among the trial's "
            "interventions" + (f" ({iv_list})" if iv_list else "")))

    pep_tok = set()
    combo_rivals = set()
    for d in drugs:
        # A canonical drug name can itself be a combination the record wrote as
        # one intervention ("Etanercept plus tacrolimus"), and then the
        # non-peptide half sits inside pep_tok, exempt from the rival guard and
        # free to lend the peptide its route -- topical tacrolimus made an
        # etanercept trial Topical/Medium.  Keep only the ranked half; the rest
        # is a rival like any other co-drug.  12.1's GENERIC_PEP strips salt and
        # class words, which is the same problem from the other side.
        parts = [q.strip() for q in re.split(_COMBO, lex.norm(d)) if q.strip()]
        if len(parts) > 1:
            ranked = [q for q in parts if lex.peptide_rank(q)]
            if ranked and len(ranked) < len(parts):
                for q in parts:
                    if q not in ranked:
                        combo_rivals.update(tk for tk in q.split() if len(tk) > 3)
                parts = ranked
        else:
            parts = [lex.norm(d)]
        for q in parts:
            for tk in q.split():
                if len(tk) > 3 and tk not in lex.ROUTE_WORDS:
                    pep_tok.add(tk)
        for tk in lex.PEP_ALIAS.get(lex.norm(d), ()):
            pep_tok.add(tk)
    if not pep_tok:
        # Same split on the fallback, which is where it actually matters: a
        # trial the identification run never named has no `drugs`, so pep_tok
        # comes from the intervention names, and "Etanercept plus tacrolimus"
        # put *tacrolimus* in pep_tok -- exempting topical tacrolimus from the
        # rival guard and making an etanercept trial Topical off its title.
        for iv in peptide_ivs:
            n = lex.norm(iv.get("name", ""))
            parts = [q.strip() for q in re.split(_COMBO, n) if q.strip()]
            if len(parts) > 1:
                ranked = [q for q in parts if lex.peptide_rank(q)]
                if ranked and len(ranked) < len(parts):
                    for q in parts:
                        if q not in ranked:
                            combo_rivals.update(tk for tk in q.split()
                                                if len(tk) > 3)
                    parts = ranked
            for q in parts:
                pep_tok.update(tk for tk in q.split()
                               if len(tk) > 3 and tk not in lex.ROUTE_WORDS)
    pep_tok -= combo_rivals

    def finish(label, conf, ev, down=False):
        if down:
            conf = knock(conf)
        if not resolved and conf == "High":
            conf = "Low"
        elif not resolved and conf == "Medium":
            conf = "Low"
        extra = ("".join(" [" + n + "]" for n in notes)) if notes else ""
        return label, conf, ws(head + " | " + ev + extra)

    # ---- tier 0: trial-level verified route
    if nct.lower() in trial_routes:
        e = trial_routes[nct.lower()]
        return finish(e["mode"], "Medium",
                      f'trial-level verified route: "{e["phrase"]}" (source: {e["source"]})')

    rivals = rival_tokens(rec, peptide_ivs, whole, pep_tok) | combo_rivals

    # ---- tiers 1-3: the peptide intervention's own fields
    for tier, field, conf in (("intervention name", "name", "High"),
                              ("intervention description", "description", "High"),
                              ("other names", "otherNames", "High")):
        per_iv = []
        for iv in peptide_ivs:
            txt = (" ".join(iv.get("otherNames", [])) if field == "otherNames"
                   else iv.get(field, ""))
            txt = ws(txt)
            raw = find_routes(txt)
            found = raw
            if field == "name" and found:
                if form_enumeration(txt):
                    # The name is the marketing authorisation's dosage-form
                    # string, which lists every form the product is sold in
                    # and says nothing about this trial: "Teicoplanin Sandoz
                    # 200 mg powder and solvent for solution for injection or
                    # infusion or oral solution" is an *inhaled* teicoplanin
                    # trial, and its title says so.
                    found = {}
                else:
                    # 9.3 applied the rival guard to tiers 2 and 4-6 on the
                    # assumption that an intervention *name* is the peptide's
                    # own.  A combination name breaks that: "Glucophage
                    # tablets and Victoza" gave liraglutide an Oral/High off
                    # metformin's dosage form.  Clause attribution only --
                    # distance is the wrong instrument in a 4-word name (12.1).
                    found = clause_guarded(found, txt, pep_tok,
                                           name_rivals(txt, rivals - SELF_REF))
            if field == "description":
                found = guarded(found, txt, pep_tok | SELF_REF, rivals - SELF_REF)
                # CTG attaches this description to the peptide intervention, so it
                # describes the peptide by construction.  When the field names no
                # agent at all except a rival ("10mg/kg/24h i.v. ... with/or without
                # rifampin" on a Daptomycin intervention), the guard has nothing to
                # measure the peptide's distance from and discards the route
                # outright -- which drops the trial to a generic tier.  9.3's rule
                # for that case is a *downgrade*, applied below, not a discard.
                # Two limits on that fallback, both measured on the 14 rows the
                # first version moved.  (1) The intervention must be the
                # peptide's own: a description attached to an intervention
                # *named* for another drug ("Laquinimod 0.6") is that drug's.
                # (2) Only a route word standing ahead of every rival mention
                # is the peptide's leading dose phrase; once a rival has been
                # named, the dosing block belongs to it ("Prednisone: 5mg;
                # Oral tablets", "Dapagliflozin oral once daily", "nitroglycerin
                # transdermal"), which distance and clause tests both miss here.
                if (raw and not found
                        and not names_any(txt, pep_tok | SELF_REF)
                        and not names_any(ws(iv.get("name", "")), rivals - SELF_REF)):
                    first_rival = min([m.start() for r in rivals - SELF_REF
                                       for m in re.finditer(r"\b" + re.escape(r),
                                                            txt.lower())] or [len(txt)])
                    kept = {l: [h for h in hits if h[1] < first_rival]
                            for l, hits in raw.items()}
                    found = {l: h for l, h in kept.items() if h}
            if not found:
                continue
            label, note, down = pick(found, dlabel)
            sw = switch_route(txt, raw, pep_tok | SELF_REF)
            if sw and sw != label:
                label = sw
                note += " [route switches mid-course; maintenance route taken]"
            per_iv.append((label, note, down, iv, txt))
        if not per_iv:
            continue
        # a trial giving the same peptide by two routes: dominant route wins and the
        # other arm is recorded in Evidence (methodology 10.3)
        labels = [x[0] for x in per_iv]
        best = [l for l in lex.PRIORITY if l in labels][0]
        # If every disagreeing arm is the SAME canonical peptide, the trial is
        # comparing routes of one drug and its title says which one it is about
        # (NCT02807363 oral leuprolide). With different drugs, priority stands
        # (NCT02470039: the tablet is insulin 338, the peptide of record glargine).
        if len(set(labels)) > 1 and len(drugs) == 1:
            for fld in ("brief", "official"):
                tfound = find_routes(ws(rec.get(fld, "")))
                cand = {l: min(x[1] for x in v) for l, v in tfound.items() if l in labels}
                if cand:
                    # the route named earliest in the title is what the trial is about
                    best = min(cand, key=lambda l: cand[l])
                    break
        label, note, down, iv, txt = next(x for x in per_iv if x[0] == best)
        alt = [x for x in per_iv if x[0] != best]
        if alt:
            note += "".join(f' [trial also includes {x[0]}: "{ws(x[3].get("name",""))}"]'
                            for x in alt)
        dn = down
        if field == "description":
            low = txt.lower()
            names_pep = any(re.search(r"\b" + re.escape(tk), low) for tk in pep_tok)
            rival_named = any(re.search(r"\b" + re.escape(r), low) for r in rivals)
            if rival_named and not names_pep:
                note += " [description names another drug and not the peptide]"
                dn = True
        return finish(label, conf,
                      f'{tier} "{ws(iv.get("name",""))}": "{txt[:300]}"{note}', dn)

    # ---- tier 4: arm description whose interventionNames include the peptide
    pep_names = {ws(iv.get("name", "")).lower() for iv in peptide_ivs}
    for a in rec.get("arms", []) or []:
        anames = {ws(x).lower() for x in a.get("interventionNames", []) or []}
        anames |= {re.sub(r"^(?:drug|biological|device|dietary supplement|other|"
                          r"procedure|radiation|behavioral|combination product|"
                          r"diagnostic test|genetic):\s*", "", x) for x in anames}
        if not (anames & pep_names):
            continue
        lab = ws(a.get("label", "")).lower()
        lab_pep = lab_rival = False
        if lab:
            lab_rival = any(re.search(r"\b" + re.escape(r), lab) for r in rivals)
            lab_pep = any(re.search(r"\b" + re.escape(tk), lab) for tk in pep_tok)
            if lab_rival and not lab_pep:
                continue
        # An arm LABEL that names the peptide and no rival is the arm's own
        # statement of what is given, and often carries the route the
        # description leaves out ("Apraglutide subcutaneous (SC) injections,
        # once weekly" / description "Peptide analogue of GLP-2").
        txt = ws(a.get("description", ""))
        if lab_pep:
            txt = ws(a.get("label", "")) + ". " + txt
        found = guarded(find_routes(txt), txt, pep_tok, rivals)
        if not found:
            continue
        label, note, down = pick(found, dlabel)
        return finish(label, "High",
                      f'description of arm "{ws(a.get("label",""))}": "{txt[:300]}"{note}', down)

    # ---- tier 5: brief/official title
    for fld in ("brief", "official"):
        txt = ws(rec.get(fld, ""))
        found = guarded(find_routes(txt), txt, pep_tok, rivals)
        if found:
            label, note, down = pick(found, dlabel)
            # A title routinely names a COMPARATOR's dosage form ("... in a Tablet
            # Formulation and Insulin Glargine"). A retrieved drug label beats it.
            if len(drugs) == 1 and not route_adjacent_to_peptide(txt, found[label], pep_tok):
                e = drug_routes.get(lex.norm(drugs[0]))
                if (e and e["quality"] == "v" and not e["mode"].startswith("Multiple:")
                        and e["mode"] != label):
                    return finish(e["mode"], "Medium",
                                  f'drug-level route for "{lex.norm(drugs[0])}": '
                                  f'"{e["phrase"]}" (source: {e["source"]}; quality v) '
                                  f'[outranks {fld} title, which names another agent\'s '
                                  f'form: "{txt[:160]}"]')
            return finish(label, "Medium", f'{fld} title: "{txt[:300]}"{note}', down)

    # ---- tier 6: summary/detail sentences naming the peptide
    for fld in ("summary", "detail"):
        txt = ws(rec.get(fld, ""))
        scoped = sentences_naming(txt, pep_tok)
        if not scoped:
            continue
        found = guarded(find_routes(scoped), scoped, pep_tok, rivals)
        if found:
            label, note, down = pick(found, dlabel)
            return finish(label, "Medium",
                          f'{fld} sentence naming the peptide: "{scoped[:300]}"{note}', down)

    # ---- vaccine / cell-product context class runs before generic text (9.3)
    # Run 8: 9.3 scopes this to the peptide's own text (10.2), which a trial
    # whose peptide never resolved does not have.  A record that frames itself
    # as peptide vaccination gets the record-level scope here as well, or the
    # generic tiers answer first -- a virosome-formulated peptide vaccine took
    # `Oral` from an abstract about an "orally transmitted virus" (NCT00445419).
    cl, trig = context_class(rec, peptide_ivs, pep_scope, "")
    if not cl and not resolved and record_names_a_peptide_product(whole):
        cl, trig = context_class(rec, peptide_ivs, pep_scope, whole)
    if cl:
        return finish(cl, "Low", f"context class: {trig}")

    # ---- tier 7: drug-level verified route
    # Keys name the *peptide*.  Taking every intervention of the trial let tier 11
    # answer with "total body irradiation" (oral=1) for a filgrastim trial and
    # with darolutamide's flags for an LHRH analogue -- 12.1's lesson, applied to
    # the drug tables instead of the route words.
    keys = [lex.norm(d) for d in drugs]
    for d in drugs:
        for part in re.split(r"\s*/\s*", d):
            keys.append(lex.norm(part))
    for iv in (peptide_ivs if resolved and resolved != "no-peptide"
               else (rec.get("interventions", []) or [])):
        keys.append(lex.norm(iv.get("name", "")))
        for o in iv.get("otherNames", []) or []:
            keys.append(lex.norm(o))
    # 12.1's PEP_ALIAS is the record's own shorthand for the peptide; the route
    # table is keyed on canonical names, so an intervention the record calls
    # only "CsA with steroid minimization" reached no key at all and blanked a
    # trial whose cyclosporine is plainly given.  Alias -> canonical, as a whole
    # word, so the short aliases (csa, gsh, acth) are not substring traps.
    for k in list(keys):
        for canon, aliases in lex.PEP_ALIAS.items():
            if any(re.search(r"\b" + re.escape(a) + r"\b", k) for a in aliases):
                keys.append(lex.norm(canon))
    keys = [k for k in dict.fromkeys(keys) if k]
    extra_keys = []
    for k in keys:
        for dk in drug_routes:
            # Word-boundary, not substring: the key "interleukin 1" otherwise
            # answers for interleukin-11, and "il 2" for IL-21.
            # Leading word boundary, and no digit may follow: the key
            # "interleukin 1" otherwise answers for interleukin-11 and "il 2"
            # for IL-21, while a trailing plural ("...nanofiber hydrogels")
            # must still match.
            if dk and (dk == k or (len(dk) >= 5
                                   and re.search(r"\b" + re.escape(dk) + r"(?![0-9])",
                                                 k))):
                extra_keys.append(dk)
    cls_keys = []
    if VACC.search(lex.norm(pep_scope) or lex.norm(whole)):
        cls_keys.append("peptide vaccine (unspecified)")
    if lex.ISOTOPE.search(lex.norm(whole)):
        cls_keys.append("radiolabelled peptide tracer")
    for k in extra_keys + cls_keys:
        e = drug_routes.get(k)
        if not e:
            continue
        mode = e["mode"]
        multi = mode.startswith("Multiple:")
        if multi:
            opts = mode.split(":", 1)[1].split("|")
            dtitle = ws(rec.get("brief", "") + " " + rec.get("official", ""))
            dscope = " ~ ".join(
                whole[max(0, mo.start() - 250): mo.end() + 250]
                for mo in re.finditer(re.escape(k.split("/")[0].strip()), whole, re.I))
            mode = resolve_multi(k, opts, whole, dtitle, dscope or whole)
        conf = "Medium" if (e["quality"] == "v" and not multi) else "Low"
        return finish(mode, conf,
                      f'drug-level route for "{k}": "{e["phrase"]}" (source: {e["source"]}'
                      f'; quality {e["quality"]}{"; multi-route resolved by indication" if multi else ""})')

    # ---- biomarker: whether a peptide is given at all is an identification
    # question (15.1), so it is settled before the tiers that are not specific
    # to the drug.  Tiers 1-7 come first and keep their precedence: a trial that
    # really doses the peptide says so in the peptide's own text or has a
    # retrieved route, and a measured peptide never does.  Behind tier 8 this
    # check was unreachable for any biomarker trial whose study description
    # happened to carry a route word -- a day-3 FSH/LH/TSH panel in a PCOS
    # ovulation-induction trial was labelled Other off the detail text.
    # 10.2's caution is about *scope*: pep_scope is the peptide's own text, and
    # the dose/monitoring guards in is_biomarker are what protect a real
    # Thymosin-alpha-1 dosing trial.
    if peptide_ivs and resolved and is_biomarker(pep_scope, peptide_ivs):
        return finish("Unknown", "Unknown",
                      f'peptide measured as a biomarker, not administered: "{pep_scope[:160]}"')

    # ---- tier 8: anywhere in the study description (not drug-specific)
    for fld in ("summary", "detail"):
        txt = ws(rec.get(fld, ""))
        found = find_routes(txt)
        if found:
            label, note, down = pick(found, dlabel)
            return finish(label, "Low",
                          f'generic study description ({fld}): "{txt[:250]}"{note}', down)

    # ---- tier 9: bundled publication abstract
    ab = abstracts.get(nct, "")
    if ab:
        found = find_routes(ab)
        if found:
            label, note, down = pick(found, dlabel)
            sn = found[label][0]
            s0 = max(0, sn[1] - 90)
            return finish(label, "Low",
                          f'bundled publication abstract: "...{ab[s0:sn[1]+110]}..."{note}', down)

    # ---- tier 10: context class (full record)
    cl, trig = context_class(rec, peptide_ivs, pep_scope, whole)
    if cl:
        return finish(cl, "Low", f"context class: {trig}")

    # ---- tier 11: ChEMBL flags, only if exactly one of three is set
    for k in keys:
        f = chembl.get(k)
        if not f:
            continue
        o, par, top = (x == "1" for x in f)
        if sum((o, par, top)) == 1:
            m = "Oral" if o else ("injection/infusion" if par else "Topical")
            return finish(m, "Medium",
                          f'ChEMBL route flags for "{k}": oral={f[0]} parenteral={f[1]} topical={f[2]}')

    # ---- tier 12
    iv_list = "; ".join(ws(iv.get("name", "")) for iv in
                        (rec.get("interventions", []) or [])
                        if ws(iv.get("name", "")))[:200]
    return finish("Unknown", "Unknown",
                  ("no peptide drug is identified among the trial's interventions"
                   + (f' ({iv_list})' if iv_list else "")
             if dlabel == "unidentified peptide product" and not resolved
             else "no delivery wording in the trial record and no external route "
                  "established"))

MULTI_RULES = {
    # 5.4, with the triggers tightened in run 6 after the stratified review:
    # each one must be specific enough to survive being matched against a whole
    # trial record. "colitis"/"diarrhoea" and bare "ocular" were not.
    "cyclosporine": [(r"dry eye|keratoconjunctivitis sicca|eye\s?drops?|ophthalmic|"
                      r"ocular surface|punctal|restasis|ikervis|cequa|verkazia", "Topical"),
                     (r"psoriasis|atopic dermatitis|dermatolog|alopecia|vitiligo|lichen", "Oral"),
                     (r"transplant|gvhd|graft[\s-]?versus|aplastic|nephrotic|colitis|"
                      r"uveitis|myasthenia|arthritis", "Oral")],
    # `c diff` must not match "c differentiation"; a prophylaxis trial that names
    # C. difficile only as an adverse outcome of antibiotics is not an oral-
    # vancomycin trial (NCT02285140, NCT04401553).
    "vancomycin": [(r"clostridi\w*|\bc\.\s?diff\w*|\bcdi\b|\bcdad\b|pseudomembranous|"
                    r"ulcerative colitis|f[ae]cal microbiota|microbiota transplant|"
                    r"intestinal microbiota|gut microbiot\w*", "Oral")],
    # nebulised colistin is the CF/bronchiectasis regimen; VAP and other severe
    # gram-negative infections are treated IV (NCT07004049, NCT07671755).
    "colistin": [(r"cystic fibrosis|bronchiectasis", "Other")],
    "desmopressin": [(r"nocturia|enuresis|nocturnal polyuria", "Oral"),
                     (r"bleeding|von willebrand|vwd|h(?:a)?emophilia|surgery|platelet",
                      "injection/infusion"),
                     (r"diabetes insipidus", "Oral")],
}
# A trigger seen only in this framing is about the trial's safety outcome, not
# about how the peptide is given.
MULTI_VETO = {"vancomycin": re.compile(r"prophyla\w*|surgical site|\bssi\b|perioperative|"
                                       r"post[\s-]?operative infection|prevention of infection|"
                                       r"prevent infection", re.I)}

def resolve_multi(key, opts, whole, title="", scope=None):
    """5.4: a multi-route drug is resolved per trial from the indication.

    The indication is read from the title first and otherwise from `scope` --
    the text within a few hundred characters of a mention of the drug. Matching
    against the whole record attributes another agent's indication to this one
    (a cardiac-surgery prophylaxis trial that mentions C. difficile as a side
    effect of antibiotics is not an oral-vancomycin trial).
    """
    scope = scope if scope is not None else whole
    for drug, rules in MULTI_RULES.items():
        if drug not in key:
            continue
        veto = MULTI_VETO.get(drug)
        for pat, lab in rules:
            if lab not in opts:
                continue
            if re.search(pat, title, re.I):
                return lab
            if re.search(pat, scope, re.I) and not (veto and veto.search(title)):
                return lab
    return opts[0].strip()

# ----------------------------------------------------------------- run
ncts = [l.strip() for l in open(os.path.join(WORK, "ncts.txt")) if l.strip()]
rows = []
for nct in ncts:
    try:
        label, conf, ev = annotate(nct)
    except Exception as e:
        label, conf, ev = "Unknown", "Unknown", f"annotation error: {type(e).__name__}: {e}"
    rows.append((nct, label, conf, ev))
rows.sort(key=lambda r: r[0])
with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["NCT Number", "Delivery Mode", "Confidence", "Evidence"])
    for r in rows:
        w.writerow(r)
print("wrote", OUT, len(rows), "rows")
print(collections.Counter(r[1] for r in rows).most_common())
print(collections.Counter(r[2] for r in rows).most_common())
