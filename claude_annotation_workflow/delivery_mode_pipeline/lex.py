#!/usr/bin/env python3
"""Lexicon, route regex families and mask list for delivery-mode annotation.
Implements methodology sections 5.1, 5.2 plus the guards added in 9.3, 10.2 and 11.2."""
import re

GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta",
         "ε": "epsilon", "κ": "kappa", "λ": "lambda", "μ": "mu",
         "ω": "omega", "τ": "tau", "σ": "sigma"}

def norm(s):
    s = (s or "").lower()
    for g, l in GREEK.items():
        s = s.replace(g, " " + l + " ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

# ---------------------------------------------------------------- not a drug
NOT_A_DRUG = [
    "placebo", "saline", "normal saline", "vehicle", "sham", "dummy", "control",
    "no intervention", "standard of care", "usual care", "radiation", "radiotherapy",
    "surgery", "surgical", "exercise", "diet", "dietary counseling", "questionnaire",
    "survey", "imaging", "mri", "ct scan", "pet scan", "ultrasound", "blood draw",
    "specimen collection", "biopsy", "observation", "education", "counseling",
    "physiotherapy", "placebo comparator", "water", "dextrose", "glucose",
    "lactated ringer", "ringer", "air", "oxygen", "none", "best supportive care",
]
_CONNECT = re.compile(r"\b(?:or|vs|versus|and|plus|with)\b")
def is_not_a_drug(name):
    """True when the intervention is a comparator/procedure rather than an agent.

    Narrow exception: "<real agent> or placebo" / "X vs saline" names a real
    agent too, and dropping it costs the trial its only peptide intervention
    (NCT01965509, "PEX168 or placebo"). The agent must come *before* the
    connective -- "Placebo intravaginal ring" is still not a drug.
    """
    n = norm(name)
    if not n:
        return True
    hit = None
    for k in NOT_A_DRUG:
        if n == k:
            return True
        m = re.search(r"\b" + re.escape(k) + r"\b", n)
        if m and (hit is None or m.start() < hit[0]):
            hit = (m.start(), k)
    if hit is None:
        return False
    head = n[:hit[0]].strip()
    tail = n[hit[0] + len(hit[1]):].strip()
    def agent_beside(words, connective_first):
        if not words:
            return False
        link = words[0] if connective_first else words[-1]
        if not _CONNECT.fullmatch(link):
            return False
        rest = words[1:] if connective_first else words[:-1]
        return any(t not in ROUTE_WORDS and len(t) > 2 for t in rest)
    if agent_beside(head.split(), False) or agent_beside(tail.split(), True):
        return False
    return True

# ------------------------------------------------- peptide morphology (5.1.4)
# Run 8: the records write INN stems with the Latin/French endings a sponsor
# registered them under -- "Terlipressinum", "Triptoreline", "Octreotidum" --
# and a trailing `\b` after the bare stem missed every one of them.  A single
# optional inflection (`e`, `a`, `um`, `us`, `o`, `i`, `e[s]`) is allowed after
# the stem, which is enough for those and still cannot reach a different word.
_INFL = r"(?:e|a|o|i|um|us|es|en|ul)?\b"
PEPTIDE_STEMS = re.compile(
    r"(?:[a-z]{2,}tide|[a-z]{2,}relin|[a-z]{2,}relix|[a-z]{2,}actide|[a-z]{2,}pressin|"
    r"[a-z]{2,}tocin|[a-z]{2,}fungin|[a-z]{2,}vancin|[a-z]{2,}kinin|[a-z]{2,}zomib)"
    + _INFL)
PEPTIDE_NEG = re.compile(r"oligonucleotide|polynucleotide|nucleotide|dinucleotide|"
                         r"[a-z]{2,}golix|antisense")
PEPTIDE_CLASS_WORDS = re.compile(
    r"\bpeptid(?:e|es|yl)\b|"
    # run 8: "Polypeptides", "Multiplexed heptapeptides", "oligopeptide",
    # "tripeptide" -- the bare `\bpeptide\b` matched none of them.  PEPTIDE_NEG
    # still vetoes `dipeptidyl peptidase` / DPP-4, and `[a-z]{2,}` keeps this
    # from matching the bare word twice.
    r"\b(?:poly|oligo|di|tri|tetra|penta|hexa|hepta|octa|deca|lipo|glyco|"
    r"cyclo|neuro|multi)[\s-]?peptid(?:e|es)\b|"
    r"gonadotropin[\s-]?releasing hormone|gnrh|lhrh|"
    r"somatostatin analog|growth hormone releasing|parathyroid hormone|"
    r"adrenocorticotropic hormone|corticotropin|vasopressin|oxytocin|insulin|"
    r"calcitonin|glucagon|c[iy]closporin|vancomycin|colistin|polymyxin|bacitracin|"
    r"daptomycin|caspofungin|micafungin|anidulafungin|thymosin|glutathione|"
    r"glatiramer|enfuvirtide|octreotide|bortezomib|carfilzomib|"
    # the records' abbreviations for endogenous peptides given as drugs; without
    # these a 3-letter drug name ("GIP") never matches and a placebo arm's
    # description was read instead (14.2)
    r"\bgip\b|\bglp[\s-]?[12]\b|\bpyy\b|\bghrh\b|\bghrp[\s-]?\d?\b|\bcck\b|"
    r"\bvip\b|\bacth\b|\bpth\b|\bpthrp\b|\bcgrp\b|\bnpy\b|\banp\b|\bcnp\b|"
    r"\bavp\b|\bddavp\b|\btrh\b|\bcrh\b|\bhcrf\b|\balpha[\s-]?msh\b|"
    r"\bxenin\b|\bobestatin\b|\bkisspeptin\b|\bgalanin\b|\borexin\b|\bapelin\b|"
    r"\burocortin\b|\bmotilin\b|\bneurotensin\b|\benkephalin\b|\bendorphin\b|"
    r"\bdynorphin\b|\bnociceptin\b|angiotensin ii\b|\bsubstance p\b|"
    # run 8: spellings and class words the records actually use.  ACTH is
    # written "adrenocorticotrophic" as often as "-tropic"; LHRH is written
    # "luteinizing hormone releasing FACTOR"; gastrin-17 is a gut hormone given
    # subcutaneously (NCT01909245) and ranked 0 until now.
    r"adrenocorticotroph[io]c|luteini[sz]ing hormone[\s-]?releasing|"
    r"\bgastrin\b|\bil[\s-]?1\s?ra\b|interleukin[\s-]?1 receptor antagonist|"
    # Insulin analogues and insulin brands are routinely the ONLY name a CTG
    # intervention carries ("Lispro", "Degludec", "Insulatard", "NovoMix 30"),
    # and none of them contains the word insulin.  They are the commonest
    # peptide drug in this corpus, so ranking them 0 cost 60+ trials their
    # identification.  `aspart` must not catch aspartate/aspartame/asparaginase.
    r"\blispro\b|\baspart(?!ate|ame|ic|yl|ase|hous)\b|\bglulisine\b|\bglargine\b|"
    r"\bdetemir\b|\bdegludec\b|\bicodec\b|\bhumalog\b|\bnovo\s?log\b|"
    r"\bnovo\s?rapid\b|\bhumulin\b|\bnovolin\b|\binsulatard\b|\bprotaphane\b|"
    r"\bnovo\s?mix\b|\bactrapid\b|\bmixtard\b|\bryzodeg\b|\blantus\b|"
    r"\blevemir\b|\btresiba\b|\btoujeo\b|\bapidra\b|\bbasaglar\b|\bfiasp\b|"
    r"\bsemglee\b|\bwosulin\b|\bhypurin\b|\brezvoglar\b|\bafrezza\b|"
    r"\bsyntocinon\b|\bpitocin\b|"
    # products whose names carry no morphology at all, each read off its own
    # record: avotermin/Juvista = recombinant human TGF-beta3 (intradermal),
    # Prevascar = recombinant interleukin-10 (intradermal), gpASIT+TM = grass
    # pollen-derived peptides (entero-coated capsules), Diamyd/rhGAD65 =
    # recombinant GAD65 protein.
    r"\bjuvista\b|\bprevascar\b|\bgpasit\b|\bdiamyd\b|\b(?:rh)?gad\s?65\b")

ISOTOPE = re.compile(
    r"\b(?:68\s?ga|177\s?lu|111\s?in|64\s?cu|90\s?y|99m\s?tc|18\s?f|225\s?ac|213\s?bi|"
    # run 8: the radioiodines were missing, so a di-DTPA-131I peptide trial had
    # no isotope evidence at all (NCT00467506)
    r"12[345]\s?i|131\s?i|iodine[\s-]?12[345]|iodine[\s-]?131|"
    r"gallium[\s-]?68|lutetium[\s-]?177|indium[\s-]?111|copper[\s-]?64|yttrium[\s-]?90|"
    r"technetium[\s-]?99m?|fluorine[\s-]?18|actinium[\s-]?225)\b")
# Run 8: `tate\b` and `toc\b` were bare substrings -- `tate` matched
# ace**tate**, which made a formoterol/nicotinic-acid inhalation trial with an
# 18F sub-study look like a radiopeptide trial.  Scoped to the conjugates they
# were written for, and DTPA added (a standard peptide chelator that was
# missing, so a di-DTPA-131I peptide trial had no radiopeptide evidence).
CHELATOR = re.compile(r"\bdota|nodaga|hynic|nota\b|\bdtpa\b|psma|fap[\s-]?2286|"
                      r"fapi|rm2\b|jr11|exendin|pentixafor|bombesin|octreotate|"
                      r"octreotide|(?:dota|octreo)tate\b|(?:dota|edo)toc\b|"
                      r"minigastrin|rgd\b|somatostatin")
VACCINE_PEP = re.compile(r"peptide vaccin|multi[\s-]?epitope|synthetic long peptide|"
                         r"neoantigen|neo[\s-]?epitope|peptide immunogen|peptide[\s-]?pulsed|"
                         r"peptide antigen|epitope peptide|peptide cocktail")
VACCINE_NEG = re.compile(r"dna vaccin|mrna|plasmid|whole cell|tumor lysate|tumour lysate|"
                         r"lysate|viral vector|adenovir|vaccinia|attenuated")

# ---------------------------------------------- recombinant protein biologics
# Methodology 8.4: peptide/non-peptide is a chemistry call and is made directly.
# This corpus (12,372 trials) is dominated in its newer half by recombinant
# protein and peptide-hormone biologics -- colony-stimulating factors,
# interleukins, interferons, erythropoietins, gonadotropins, somatropins, fusion
# proteins, enzymes and antibodies.  None of them carry an INN peptide stem, so
# PEPTIDE_STEMS never saw them and the route of a chemo partner was read instead.
# The Fc-fusion proteins by name: a generic `-cept` stem also matches the trade
# name CellCept (mycophenolate mofetil), which then outranked the real peptide.
_CEPT = (r"\b(?:etanercept|abatacept|belatacept|alefacept|aflibercept|rilonacept|"
         r"batiraxcept|conbercept|ziv[\s-]?aflibercept)\b")
BIOLOGIC_STEMS = re.compile(
    r"(?:[a-z]{2,}grastim|[a-z]{2,}gramostim|[a-z]{3,}plostim|[a-z]{2,}poetin|"
    r"[a-z]{2,}tropin|[a-z]{2,}leukin|[a-z]{2,}ferons?|[a-z]{3,}mab|" + _CEPT + r"|"
    r"[a-z]{2,}ermin|[a-z]{3,}fusp|[a-z]{3,}glucerase|[a-z]{3,}sidase|[a-z]{3,}sulfase|"
    r"[a-z]{3,}uronidase|[a-z]{3,}plase|[a-z]{3,}kinase|[a-z]{3,}parginase|"
    r"[a-z]{2,}asparaginase|[a-z]{2,}dornase|[a-z]{3,}carpidase|[a-z]{3,}uricase|"
    r"[a-z]{3,}tidase|[a-z]{3,}cerase|[a-z]{3,}lipase|[a-z]{3,}galsidase)\b")
# -kinase also names intracellular targets ("tyrosine kinase inhibitor"): those are
# caught by the negative list below, not by excluding the stem.
BIOLOGIC_NEG = re.compile(
    r"kinase[\s-]?\d*\s*inhibitor|tyrosine kinase|protein kinase|phosphatase|"
    r"receptor[\s-]?associated kinase|"
    r"[a-z]+ase (?:inhibitor|activity|assay|level)|inhibitor of [a-z]+ase|"
    r"dipeptidyl peptidase|\bdpp[\s-]?(?:4|iv)\b|receptor antagonist")
BIOLOGIC_WORDS = re.compile(
    r"\binterleukin\b|\bil[\s-]?(?:1|2|3|4|6|7|10|11|12|15|18|21)\b|"
    r"\binterferon\b|\bifn\b|colony[\s-]?stimulating factor|"
    r"\bg[\s-]?csf\b|\bgm[\s-]?csf\b|\bm[\s-]?csf\b|\bscf\b|"
    r"erythropoietin|\bepo\b|\besa\b|growth hormone|somatomedin|"
    r"growth factor|\bngf\b|\bgdnf\b|\bbdnf\b|\bvegf\b|\bkgf\b|"
    r"gonadotropin|\bfsh\b|\blh\b|\bhcg\b|menotropin|urofollitropin|"
    r"thyrotropin|\btsh\b|prolactin|\bleptin\b|\bghrelin\b|\bamylin\b|"
    r"natriuretic peptide|\bbnp\b|\bantithymocyte globulin\b|"
    r"anti[\s-]?thymocyte globulin|\batg\b|thymoglobulin|lymphocyte immune globulin|"
    r"immune globulin|immunoglobulin|\bivig\b|\bscig\b|gammagard|antivenin|antivenom|"
    r"antitoxin|coagulation factor|\bfactor (?:vii|viii|ix|x|xiii)\b|"
    r"von willebrand factor|fibrinogen concentrate|prothrombin complex|"
    r"albumin \(human\)|serum albumin|protein c concentrate|antithrombin|"
    r"alteplase|tenecteplase|reteplase|urokinase|streptokinase|"
    r"\bbotulinum (?:toxin|neurotoxin)\b|botox|dysport|xeomin|"
    r"collagenase|bromelain|nexobrid|\btrypsin\b|chymotrypsin|papain|"
    r"\bhyaluronidase\b|asparaginase|rasburicase|pegloticase|glucarpidase|"
    r"copolymer 1\b|\bcop[\s-]?1\b|"
    r"protein hydrolysate|hydroly[sz]ed (?:casein|whey|protein|collagen|milk)|"
    r"(?:casein|whey|collagen|soy|pea|milk|egg|fish|marine|rice|lupin|potato)"
    r"[\s-]?(?:protein )?(?:hydroly[sz]ates?|hydroly[sz]ate|peptides?)|"
    r"ovotransferrin|lactoferrin|lactalbumin|lysozyme|\bcasein\b|\bwhey\b|"
    # the records' own shorthand for recombinant proteins
    r"\brh?u?(?:epo|gh|igf|tsh|pth|csf)\b|\bmet\s?hu[a-z]*\b|"
    r"recombinant (?:human|methionyl|murine|bovine|porcine)\b|"
    r"\bpeg(?:ylated)?[\s-]?(?:interferon|ifn)\b|\bfusion protein\b")
BIOLOGIC_NAMES = {
    "anakinra", "kineret", "etanercept", "enbrel", "abatacept", "orencia",
    "belatacept", "nulojix", "aldesleukin", "proleukin", "bempegaldesleukin",
    "denileukin diftitox", "oprelvekin", "neumega", "ancestim", "filgrastim",
    "neupogen", "zarxio", "nivestym", "tevagrastim", "lenograstim", "granocyte",
    "pegfilgrastim", "neulasta", "lipegfilgrastim", "eflapegrastim",
    "sargramostim", "leukine", "molgramostim", "cilmostim", "palifermin",
    "kepivance", "becaplermin", "regranex", "dibotermin alfa", "infuse bone graft",
    "eptotermin alfa", "epoetin", "procrit", "epogen", "eprex", "aranesp",
    "darbepoetin", "mircera", "methoxy polyethylene glycol epoetin beta",
    "somatropin", "genotropin", "norditropin", "humatrope", "omnitrope",
    "saizen", "nutropin", "somatrogon", "somapacitan", "lonapegsomatropin",
    "mecasermin", "increlex", "pegvisomant", "somavert", "metreleptin", "myalept",
    "dornase alfa", "pulmozyme", "taliglucerase", "imiglucerase", "velaglucerase",
    "cerezyme", "elelyso", "vpriv", "agalsidase", "fabrazyme", "replagal",
    "laronidase", "idursulfase", "elosulfase", "galsulfase", "alglucosidase",
    "avalglucosidase", "sebelipase", "asfotase alfa", "strensiq", "cerliponase",
    "pegademase", "elapegademase", "drotrecogin alfa", "xigris",
    "eptacog alfa", "novoseven", "moroctocog", "nonacog", "turoctocog",
    "efmoroctocog", "eftrenonacog", "simoctocog", "susoctocog", "damoctocog",
    "rurioctocog", "lonoctocog", "albutrepenonacog", "emicizumab", "hemlibra",
    "antihemophilic factor", "thymoglobulin", "atgam", "grafalon",
    "teplizumab", "tzield", "basiliximab", "simulect", "daclizumab", "zenapax",
    "romiplostim", "nplate", "burosumab", "asparaginase erwinia", "erwinaze",
    "rylaze", "pegaspargase", "oncaspar", "calaspargase",
    "glatiramer", "copaxone", "copolymer 1", "gammagard", "privigen", "octagam",
    "gamunex", "hizentra", "flebogamma", "rhogam", "winrho", "hyperrab",
    "nexobrid", "santyl", "collagenase clostridium histolyticum", "xiaflex",
    "qwo", "hylenex", "vitrase", "amphadase", "purastat", "tisseel", "evicel",
    "fibrin sealant", "fibrin glue", "artiss", "tachosil", "floseal", "surgiflo",
    "ovotransferrin", "lactoferrin", "serum albumin", "albumin human",
    "aflibercept", "eylea", "ranibizumab", "lucentis", "brolucizumab",
    "pegaptanib", "conbercept", "rilonacept", "arcalyst", "canakinumab", "ilaris",
    "abaloparatide", "sermorelin", "tesamorelin", "nesiritide", "ularitide",
    "carperitide", "urodilatin", "secretin", "chirhostim", "sincalide",
    "kinevac", "pentagastrin", "ceruletide", "aviptadil", "zyesami",
    "thyrotropin alfa", "thyrogen", "menotropins", "urofollitropin", "bravelle",
    "follitropin", "gonal f", "puregon", "follistim", "choriogonadotropin",
    "ovidrel", "pregnyl", "novarel", "lutropin", "luveris", "corifollitropin",
    "elonva", "ganirelix", "cetrotide",
}
_BIO_NAME_RE = re.compile(
    r"\b(?:" + "|".join(sorted((re.escape(n) for n in BIOLOGIC_NAMES), key=len,
                               reverse=True)) + r")\b")

# Antibodies and Fc-fusion proteins are proteins, not peptide drugs, and in
# oncology / transplant regimens they sit beside the trial's actual peptide
# (rituximab + cyclosporine, belatacept + cyclosporine).  Counting them equally
# makes their IV route win over the peptide's -- 11.2's error class.  They are
# therefore ranked *below* peptides and recombinant protein hormones, and are
# only used as the trial's drug when nothing better is present.
ANTIBODY = re.compile(
    r"[a-z]{3,}mab\b|immune globulin|immunoglobulin|\bivig\b|" + _CEPT + r"|"
    r"\bscig\b|antivenin|antivenom|antitoxin|antithymocyte globulin|"
    r"anti[\s-]?thymocyte globulin|\batg\b|thymoglobulin|atgam|grafalon|"
    r"lymphocyte immune globulin|globulin serum|\bfab fragment|"
    r"rhogam|winrho|hyperrab|gammagard|privigen|octagam|gamunex|hizentra|"
    r"flebogamma|\bentanercept\b")

def looks_biologic(blob):
    """True when `blob` (already normalised) names a recombinant protein,
    peptide-hormone or antibody drug rather than a small molecule."""
    if BIOLOGIC_NEG.search(blob):
        return False
    return bool(BIOLOGIC_STEMS.search(blob) or BIOLOGIC_WORDS.search(blob)
                or _BIO_NAME_RE.search(blob))

# Protein drugs that are always given by needle.  The food/supplement context
# class is a record-level last resort, and on these trials the record's "high
# protein diet" or "nutritional supplementation" wording is background, not the
# drug's route (a pegfilgrastim trial was reading as Oral).  Dietary peptide
# products -- hydrolysates, collagen peptides, whey -- are deliberately absent.
INJECTED_PROTEIN = re.compile(
    r"[a-z]{2,}grastim|[a-z]{2,}gramostim|[a-z]{3,}plostim|[a-z]{2,}poetin|"
    r"[a-z]{2,}tropin|[a-z]{2,}leukin|[a-z]{2,}ferons?|[a-z]{3,}mab\b|" + _CEPT + r"|"
    r"\binterleukin\b|\binterferon\b|colony[\s-]?stimulating factor|"
    r"\bg[\s-]?csf\b|\bgm[\s-]?csf\b|erythropoietin|\brh?u?(?:epo|gh|csf)\b|"
    r"growth hormone|gonadotropin|immune globulin|immunoglobulin|"
    r"antithymocyte globulin|anti[\s-]?thymocyte globulin|thymoglobulin|"
    r"coagulation factor|asparaginase|\banakinra\b|\betanercept\b|\babatacept\b")

# CTG `otherNames` are unreliable as peptide evidence: a talazoparib arm lists
# "Combination product: 177Lu-DOTA-Octreotate", a vadadustat arm lists
# "Darbepoetin alfa", a rosiglitazone arm lists "Insulin".  They are only worth
# consulting when the intervention's own name is opaque -- a research code, an
# abbreviation or a placeholder -- which is exactly when they carry the INN
# (hCRF -> corticorelin, SMS995 -> octreotide, CTLA-4 Ig -> abatacept).
_DOSE = re.compile(r"\b\d[\d.,]*\s*(?:mg|mcg|ug|g|ml|l|iu|units?|%|kg|mmol|nmol|"
                   r"mg/kg|mg/m2|million|billion)\b|\b(?:qd|bid|tid|qid|q\dw)\b", re.I)
_PLACEHOLDER = re.compile(
    r"\b(?:monotherap\w*|combination|regimen|background|study drug|study product|"
    r"investigational|arm|group|cohort|dose level|treatment|intervention|"
    r"comparator|experimental|active|standard|conventional|optimi[sz]ed|"
    r"antibiotics?|antimicrobial|chemotherapy|protocol)\b", re.I)

def opaque_name(name):
    raw = (name or "")
    stripped = _DOSE.sub(" ", raw)
    if _PLACEHOLDER.search(stripped):
        return True
    for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9.-]*", stripped):
        if re.search(r"[A-Za-z]", tok) and re.search(r"\d", tok):
            return True          # research code: SMS995, CTLA-4, hLF1-11, p946
        if len(tok) <= 5 and tok.isupper():
            return True          # abbreviation: hCRF -> CRF, IL-1Ra
        letters = [c for c in tok if c.isalpha()]
        if (len(letters) > 1 and any(c.isupper() for c in letters[1:])
                and not (tok.isupper() and len(tok) > 5)):
            return True          # internal capital: PTHrP, hrINF-alpha, rhIL-11
    return False


def peptide_rank(name, extra=""):
    """0 = not a peptide drug, 1 = peptide, 2 = recombinant protein / protein
    hormone / enzyme, 3 = antibody or Fc-fusion protein.  Resolution keeps only
    the best (lowest non-zero) rank present in a trial."""
    n = norm(name) + " " + norm(extra)
    if PEPTIDE_NEG.search(n) and not PEPTIDE_CLASS_WORDS.search(n):
        return 0
    if VERIFIED_PROTEIN_PRODUCTS.search(n):
        return 2
    if VERIFIED_PEPTIDE_PRODUCTS.search(n):
        return 1
    if (ISOTOPE.search(n) and CHELATOR.search(n)) or PEPTIDE_STEMS.search(n) \
       or PEPTIDE_CLASS_WORDS.search(n) \
       or (VACCINE_PEP.search(n) and not VACCINE_NEG.search(n)):
        return 1
    if not looks_biologic(n):
        return 0
    return 3 if ANTIBODY.search(n) else 2


def looks_peptide(name, extra=""):
    n = norm(name) + " " + norm(extra)
    if PEPTIDE_NEG.search(n):
        if not PEPTIDE_CLASS_WORDS.search(n):
            return False
    if ISOTOPE.search(n) and CHELATOR.search(n):
        return True
    if VACCINE_PEP.search(n) and not VACCINE_NEG.search(n):
        return True
    if PEPTIDE_STEMS.search(n):
        return True
    if PEPTIDE_CLASS_WORDS.search(n):
        return True
    if looks_biologic(n):
        return True
    return False

# ------------------------------------------------------------- route families
P = r"[\s-]?"
INJ = [
    r"inject(?:ion|ions|ed|ing|able|or)?\b", r"infus(?:ion|ions|ed|e|ing)\b",
    r"\bsub" + P + r"cutaneous(?:ly)?\b", r"\bsub" + P + r"cut\b", r"\bs\.?c\.?\b(?=\s|$|,)",
    r"\bintra" + P + r"venous(?:ly)?\b", r"\bintra" + P + r"muscular(?:ly)?\b",
    r"\bintra" + P + r"dermal(?:ly)?\b", r"\bintra" + P + r"thecal(?:ly)?\b",
    r"\bintra" + P + r"peritoneal(?:ly)?\b", r"\bintra" + P + r"vitreal(?:ly)?\b",
    r"\bintra" + P + r"tumou?ral(?:ly)?\b", r"\bintra" + P + r"arterial(?:ly)?\b",
    r"\bintra" + P + r"lesional(?:ly)?\b", r"\bintra" + P + r"pleural(?:ly)?\b",
    r"\bintra" + P + r"articular(?:ly)?\b", r"\bintra" + P + r"ventricular(?:ly)?\b",
    r"\bintra" + P + r"cavernosal(?:ly)?\b", r"\bintra" + P + r"osseous\b",
    r"\bintra" + P + r"cameral\b", r"\bepidural(?:ly)?\b", r"\bparenteral(?:ly)?\b",
    r"\bdepot\b", r"\bsyringe\b", r"\bauto" + P + r"injector\b", r"\bpen\b(?=\s*(?:device|injector))",
    r"\bcsii\b", r"\binsulin pump\b", r"\bpump\b", r"\bbolus\b", r"\bperfusion\b",
    r"\bi\.v\.", r"\bi\.m\.", r"\bIV\b", r"\bIM\b", r"\bSC\b", r"\bSQ\b", r"\bID\b",
    r"\bivgtt\b", r"\blocal infiltration\b", r"\bnerve block\b",
]
ORAL = [
    r"\boral(?:ly)?\b", r"\bby mouth\b", r"\bper os\b", r"\bp\.o\.", r"\bPO\b",
    r"\btablets?\b", r"\bcapsules?\b", r"\bcaplets?\b", r"\bpills?\b", r"\bsachets?\b",
    r"\bgumm(?:y|ies)\b", r"\bsyrup\b", r"\boral (?:solution|suspension|powder|spray)\b",
    r"\bswallow(?:ed|ing)?\b", r"\bgavage\b", r"\benteral(?:ly)?\b", r"\bnaso" + P + r"gastric\b",
    r"\bng tube\b", r"\bgastrostomy\b", r"\bjejunostomy\b",
    # a powder taken as a drink: "300 mg of powder form dissolved in one cup
    # of tap water prior to breath test".  Kept narrow -- 10.2 removed bare
    # drink/beverage from this family because they belong to the 5.5 food
    # context class, which is scoped correctly; "dissolved in <liquid>" is
    # explicit administration wording, not a food description.
    # a drinking container is required: "dissolved in one cup of tap water".
    # Without it the pattern reads vaccine *formulation* as administration --
    # "100 ug PD-L2 peptide dissolved in DMSO and water mixed with 500ul
    # montanide" is an emulsion for injection, not a drink.
    r"dissolv\w+ in [^.;]{0,25}\b(?:cups?|glass(?:es)?|tumblers?|mugs?)\b"
    r"[^.;]{0,25}\b(?:water|juice|milk|tea|coffee)\b",
    # run 8: ORALW (contradiction_pass) already had the bare/3rd-person forms;
    # ORAL did not, so "subjects ingest 15 grams of collagen peptides daily"
    # carried no oral wording at all.  14.2's warning runs both ways -- the two
    # families have to stay in step.
    r"\bingest(?:ed|ion|s|ing)?\b",
    r"\bdrinking water\b", r"\bchewable\b", r"\bfeeding tube\b",
    r"\benteral formula\b", r"\bpeptide formula\b",
]
TOP = [
    r"\bmouth[\s-]?wash(?:es)?\b", r"\bmouth[\s-]?rinse\w*\b", r"\boral rinse\w*\b",
    r"\bgargl\w+\b", r"\bswish(?:ed|ing)?\b", r"\bswish and spit\b",
    r"\btopical(?:ly)?\b", r"\bcreams?\b", r"\bointments?\b", r"\blotions?\b",
    r"\bsalve\b", r"\bbalm\b", r"\btrans" + P + r"dermal(?:ly)?\b",
    r"(?<![a-z])(?<!-)cutaneous(?:ly)?\b", r"(?<![a-z])(?<!-)dermal(?:ly)?\b",
    r"\bpatch(?:es)?\b", r"\bgels?\b", r"\beye drops?\b", r"\bophthalmic\b",
    r"\bocular (?:surface|instillation)\b", r"\botic\b", r"\beye ointment\b",
    r"\bapplied (?:to|on) the (?:skin|surface|wound|eye|tooth|teeth|enamel)\b",
    r"\bskin application\b", r"\bvarnish\b", r"\btooth" + P + r"paste\b", r"\bdentifrice\b",
    r"\bmouth" + P + r"rinse\b", r"\birrigat(?:ion|ed|e)\b", r"\bdressing\b",
    r"\binstill(?:ed|ation)[^.]{0,40}drops?\b", r"\bdrops? (?:in|into) the eye\b",
    # local application into a surgical wound (antibiotic powder/paste). Not
    # "powder" alone -- that is a dosage form for inhalers, injections and
    # oral sachets alike.
    r"\bintra" + P + r"wound\b", r"\blocal wound\b",
    r"\bpowder[^.]{0,30}\b(?:applied|placed|packed|sprinkled|poured)\b",
    r"\b(?:applied|placed|packed|sprinkled|poured|instilled)[^.]{0,40}\b(?:wound|surgical (?:bed|site|wound)|fracture site|incision)\b",
    r"\bwound[^.]{0,25}\b(?:packed|filled)\b",
    r"\blocal(?:ly)? (?:administered|applied|delivered)\b",
    r"\badministered locally\b", r"\bapplied locally\b",
]
OTH = [
    r"\binhal(?:ed|ation|er|ing)\b", r"\bnebuli[sz](?:ed|er|ation)\b",
    r"\baerosoli[sz]\w*\b", r"\baerosol\b",
    r"\bdry powder inhaler\b", r"\bintra" + P + r"pulmonary\b", r"\bintra" + P + r"tracheal\b",
    r"\bintra" + P + r"nasal(?:ly)?\b", r"\bnasal spray\b", r"\bnasally\b", r"\bnostril\b",
    r"\bimplants?\b", r"\bimplantation\b", r"\bvaginal(?:ly)?\b", r"\bpessar(?:y|ies)\b",
    r"\bintra" + P + r"vaginal(?:ly)?\b", r"\brectal(?:ly)?\b", r"\bsuppositor(?:y|ies)\b",
    r"\benemas?\b", r"\bsub" + P + r"lingual(?:ly)?\b", r"\bbuccal(?:ly)?\b",
    r"\blozenges?\b", r"\bintra" + P + r"vesical(?:ly)?\b", r"\bbladder instillation\b",
    r"\bscaffold\b", r"\bbone graft\b", r"\bsurgically (?:placed|implanted|applied)\b",
    r"\btrans" + P + r"mucosal\b", r"\btrocar\b",
]
CASE_SENSITIVE = {r"\bIV\b", r"\bIM\b", r"\bSC\b", r"\bSQ\b", r"\bID\b", r"\bPO\b"}

def _compile(pats):
    out = []
    for p in pats:
        out.append(re.compile(p) if p in CASE_SENSITIVE else re.compile(p, re.I))
    return out

FAMILIES = {
    "injection/infusion": _compile(INJ),
    "Oral": _compile(ORAL),
    "Topical": _compile(TOP),
    "Other": _compile(OTH),
}
PRIORITY = ["injection/infusion", "Other", "Topical", "Oral"]

# ------------------------------------------------------------------- masks
# Phrases that look like a route but are not the drug's route. Blanked before
# the family regexes run. Sections 5.2, 9.3, 11.2.
MASK_PATTERNS = [
    # --- oral: tests, background therapy, indications (5.2, 9.3, 11.2)
    r"oral glucose (?:tolerance|solution|load|challenge|drink)",
    r"\bo\.?g\.?t\.?t\b", r"\boglds?\b", r"\boads?\b",
    r"oral anti[\s-]?(?:diabetics?|diabetic (?:drugs?|agents?|medications?|therapy)|"
    r"hyperglycemics?|hyperglycaemics?|hyperglycemic agents?|coagulants?|biotics?)",
    r"oral (?:agents?|medications?|medicines?|drugs?|therapy|treatment|intake|"
    r"contracept\w*|steroids?|hypoglyc\w+|iron|supplementation of|nutrition|feeding|"
    r"health|mucositis|mucitis|candidiasis|lesions?|cavity|care|hygiene|examination|mucosa|"
    r"temperature|cancer|surgery)",
    # "oral" as an anatomical site in abstracts and indications (14.2)
    r"oral (?:and (?:cutaneous|oropharyngeal|maxillofacial)|squamous|carcinoma\w*|"
    r"tumou?rs?|epitheli\w+|keratinocyte\w*|microbio\w+|flora|bacteri\w+|dysbiosis|"
    r"biofilm|plaque|ulcer\w*|aphthous|leukoplakia|dysplasia|graft|implant\w*|"
    r"appliance|cavity|tissues?|soft tissue|tolerance test|food challenge|"
    r"immunotherap\w+|allergy syndrome|contraceptive\w*)",
    r"(?:oral|dental|periodontal) (?:and )?(?:health|hygiene|disease\w*)",
    r"(?:squamous cell|head and neck)[^.;]{0,20}oral",
    r"(?:mouth[\s-]?wash|mouth[\s-]?rinse|oral rinse|gargle)[^.;]{0,15}(?:solution|suspension)",
    r"oralen kontrazeptiva", r"nothing by mouth", r"\bnil per os\b", r"\bnpo\b",
    # Nutrition is its own intervention, not the drug's route: an arm named
    # "ustekinumab and semi enteral nutrition" read as Oral, and "total
    # parenteral nutrition" reads as an infusion of the study drug (14.2).
    r"(?:semi[\s-]?)?(?:total |partial )?(?:enteral|parenteral)[\s-]?nutrition",
    r"nutritional support", r"\btpn\b", r"\bnutrition therapy\b",
    # Run 8: a MEAL is ingested, not the drug.  Insulin and incretin records are
    # full of "0.10 U/kg immediately before ingestion of a standard meal" and
    # "GLP-1 is a hormone secreted by gut in response to nutrients ingestion" --
    # the same shape as 14.2's enteral-nutrition mask, and it put three
    # subcutaneous-insulin trials and a GLP-1 infusion trial on `Oral` as soon
    # as run 8's identification fix let their own descriptions be read.
    r"ingest\w*\s+(?:of\s+)?(?:a |the |an )?(?:standard |mixed |test |liquid |"
    r"solid |high[\s-]?\w+ |low[\s-]?\w+ |isocaloric )*"
    r"(?:meals?|breakfast|lunch|dinner|food|foods|nutrients?|nutrition|"
    r"carbohydrate\w*|glucose|drink\w*|beverage\w*|water|calories|diet)",
    r"(?:meals?|food|nutrients?|carbohydrate\w*|glucose|calori\w+|protein)"
    r"[\s-]+ingest\w+",
    # run 8: a virus is "orally transmitted"; that is not a drug's route
    r"orally[\s-]transmitted", r"oral[\s-]transmission", r"oral route of",
    r"dry mouth", r"mouth opening", r"foot and mouth",
    # --- oral <non-peptide co-drug> (9.3)
    r"(?:oral|orally|po|p\.o\.|by mouth)[^.;]{0,25}\b(?:metformin|sitagliptin|"
    r"saxagliptin|linagliptin|vildagliptin|alogliptin|dapagliflozin|empagliflozin|"
    r"canagliflozin|ertugliflozin|glimepiride|gliclazide|glibenclamide|glyburide|"
    r"glipizide|pioglitazone|rosiglitazone|acarbose|repaglinide|nateglinide|"
    r"prednisone|prednisolone|dexamethasone|methylprednisolone|melphalan|thalidomide|"
    r"lenalidomide|cyclophosphamide|capecitabine|temozolomide|tamoxifen|letrozole|"
    r"anastrozole|exemestane|abiraterone|enzalutamide|apalutamide|darolutamide|"
    r"bicalutamide|flutamide|nilutamide|estradiol|estriol|estrogen|oestrogen|"
    r"progesterone|norethisterone|medroxyprogesterone|levonorgestrel|mycophenolate|"
    r"cellcept|tacrolimus|sirolimus|everolimus|azathioprine|methotrexate|"
    r"hydroxychloroquine|rifampicin|rifampin|isoniazid|levofloxacin|moxifloxacin|"
    r"ciprofloxacin|amoxicillin|clarithromycin|metronidazole|fluconazole|"
    r"itraconazole|voriconazole|posaconazole|warfarin|aspirin|clopidogrel|"
    r"atorvastatin|simvastatin|rosuvastatin|ramipril|lisinopril|losartan|"
    r"amlodipine|metoprolol|bisoprolol|carvedilol|furosemide|spironolactone|"
    r"omeprazole|pantoprazole|esomeprazole|ondansetron|lactulose|rifaximin|"
    r"ursodeoxycholic|levodopa|donepezil|memantine|lithium|sertraline|fluoxetine|"
    r"quetiapine|olanzapine|risperidone|gabapentin|pregabalin|tramadol|oxycodone|"
    r"morphine|paracetamol|acetaminophen|ibuprofen|naproxen|colchicine|allopurinol|"
    r"febuxostat|calcium|vitamin|folic acid|potassium|magnesium|zinc|iron sulfate|"
    r"ferrous|fcn[\s-]?437c|ly2409021|ta[\s-]?7284|mycophenolic)",
    # --- skin / dermal as indication or outcome (5.2, 9.3)
    r"skin and soft tissue", r"skin (?:infections?|tests?|cancer|lesions?|biops\w+|"
    r"grafts?|pricks?|prick test|flora|colonizations?|colonisations?|barrier|"
    r"hydration|elasticity|firmness|wrinkles?|roughness|moisture|tone|temperature|"
    r"integrity|closure|preparation|antisepsis|disinfection|reactions?|rash|"
    r"necrosis|ulcers?|toxicity|fold thickness)",
    # the outcome list runs on past the first item without repeating "skin":
    # "support skin hydration, elasticity, firmness, dermal collagen content,
    # and wrinkle reduction" -- an ingested collagen supplement's endpoints,
    # which outvoted the record's own "consumed orally"
    r"(?:,\s*(?:and\s+)?(?:elasticity|firmness|wrinkles?|wrinkle reduction|roughness|moisture|hydration|tone|barrier function|collagen content|appearance|density|thickness))+",
    r"dermal (?:collagen|density|thickness|matrix) (?:content|density|synthesis)?",
    r"(?:cutaneous|dermal)[^.;]{0,20}(?:lymphoma|melanoma|carcinoma|cancer|"
    r"metasta\w+|tumou?rs?|lupus|leishmaniasis|manifestations?|toxicity|"
    r"adverse|reactions?|lesions?|wounds?|infections?)",
    r"(?:metastatic|advanced|recurrent|relapsed|refractory)[^.;]{0,15}cutaneous",
    # NB: do NOT mask "intradermal" here -- it is an INJ route word (line ~81).
    # The TOP family's "dermal" already excludes epi-/intra-/trans- via lookbehind.
    r"epidermal", r"dermatomyositis", r"dermatitis",
    r"scleroderma", r"dermatology", r"dermatologic\w*",
    # a comparator's dosage form is not the peptide's route (run 5)
    r"(?:placebo|dummy|sham)[\s-]{0,3}(?:matching|matched)?[\s-]{0,3}(?:pill|tablets?|capsules?|drops?|gel|cream|spray|solution|syrup|ointments?|lotions?|patch(?:es)?|foams?|pastes?|suppositor\w+|sachets?|powders?|inhalers?)",
    r"(?:matching|matched|dummy)[\s-]{0,3}placebo[\s-]{0,3}\w*",
    r"(?:oral|topical|nasal|inhaled)[\s-]{0,3}placebo",
    r"vaginal (?:repair|surgery|hysterectomy|prolapse|mesh|cuff|atrophy)",
    r"(?:cervical or |cervico)?vaginal[^.;]{0,15}"
    r"(?:cancer|carcinoma|tumou?r|neoplas\w+|intraepithelial|dysplasia)",
    # a radioactive seed or device implant is not a drug implant (run 5)
    r"(?:brachytherapy|seed|radioactive|pd[\s-]?103|i[\s-]?125|titanium)"
    r"[\s-]{0,12}implant\w*", r"implant with a \d",
    # a syringe used as an applicator, not a needle (run 5)
    r"syringe[^.;]{0,30}(?:atomi[sz]\w+|mucosal|nasal|oral|feeding|enteral|"
    r"nasogastric|irrigat\w+|applicator)",
    r"(?:atomi[sz]\w+|mucosal|oral|feeding|enteral|nasogastric)[^.;]{0,30}syringe",
    # --- nasal as route-of-oxygen, AE or site (5.2, 10.2, 11.2)
    r"nasal (?:cannula|congestion|symptoms?|oxygen|cpap|swabs?|carriage|polyps?|"
    r"mucosa|obstruction|discharge|packing|airway|bone|cavity cancer|colonization|"
    r"colonisation|screening|prongs?|high[\s-]?flow)",
    r"(?:high[\s-]?flow|humidified)[^.;]{0,15}nasal", r"naso" + P + r"pharyn\w+",
    r"\bnasal (?:spray )?placebo\b", r"placebo nasal spray",
    # --- vaginal/rectal as obstetric event or site (5.2, 10.2)
    r"vaginal (?:deliver\w+|birth|births|labou?r|exams?|examinations?|bleeding|"
    r"blood loss|discharge|flora|microbio\w+|swabs?|cuff|hysterectomy|atrophy|"
    r"dryness|candidiasis|infections?|cytology|ph\b|secretions?)",
    r"trans" + P + r"vaginal", r"vaginally[^.;]{0,10}deliver",
    r"rectal (?:carriage|swabs?|screening|examinations?|temperature|bleeding|"
    r"cancer|tone|balloon|distension|sensation)",
    r"\bcarriage of\b", r"per" + P + r"rectal examination",
    # --- implant as device or biological event (5.2, 9.3)
    r"(?:cochlear|dental|breast|valve|cardiac|penile|ocular|lens|stent|device|"
    r"electrode|pacemaker|defibrillator|port|catheter)[\s-]?implant\w*",
    r"implant(?:ation)? (?:of )?(?:a )?(?:device|pocket|site|surface|bed|failure)",
    r"implant (?:pocket|site|surface|bed)", r"device implantation",
    r"(?:embryo|blastocyst|pre" + P + r"?embryo)[^.;]{0,20}implant\w*",
    r"implantation (?:rate|failure|window|site)", r"post" + P + r"implantation",
    r"fail(?:ed|s|ure)? to implant", r"re" + P + r"implantation",
    # --- IV as access, fluid or Roman numeral (5.2, 10.2)
    r"intravenous (?:lines?|access|fluids?|cathet\w+|hydration|cannula\w*|"
    r"immunoglobulin administration set|drug use)",
    r"\bi\.?v\.? (?:lines?|access|fluids?|cathet\w+|hydration|cannula\w*)",
    # the record often drops the "intra": "a venous line will be installed"
    # for blood sampling, in a trial whose drug is an intranasal spray
    r"\bvenous (?:lines?|access|cathet\w+|sampling|blood sampl\w+)",
    # an infusion of cells or marrow is a procedure, not the peptide's route.
    # A peptide used ex vivo to load a cell product that is then infused is
    # still injection/infusion (1), but by the 5.5 cell-product class, which
    # does not depend on this wording.
    r"(?:stem[\s-]?cell|bone marrow|marrow|platelet|donor lymphocyte)"
    r"[\s-]?(?:product[\s-]?)?(?:infusions?|transplant\w*)",
    r"\bdpp[\s-]?(?:iv|4)\b", r"\bcyp\s?[0-9a-z]*\b",
    r"\b(?:stages?|grades?|classe?s?|types?|phases?|figo|nyha|chf|ckd)\s*"
    r"[0-9ivx]*\s*(?:i{1,3}|iv|v)\s*(?:[-–/]|or|to|and)\s*(?:i{1,3}|iv|v)\b",
    r"\b(?:stage|grade|class|type|phase|figo|nyha)\s*iv\b",
    r"\b[IVX]{1,4}\.\s", r"\(\s*[ivx]{1,4}\s*\)",
    r"\bfactor (?:viii|ix|xi|vii|ii|x|v|iv)\b", r"\bangiotensin\s*iv\b",
    # --- gels and patches that are not a dosage form (5.2, 9.3)
    r"(?:gel|agarose|polyacrylamide|sds)[\s-]?electrophoresis", r"\bagarose\b",
    r"(?:ultrasound|lubricating|conductive|coupling|contact)[\s-]?gel",
    r"gel (?:pads?|filtration|chromatography|strips?|packs?)",
    # Acthar Gel is injected; the brand is also spelled ACTHER/Acthar in records
    r"(?:acth\w*|adrenocorticotropic hormone|corticotropin)[^a-z]{0,25}gel",
    r"patch(?:es)? test(?:ing|s)?", r"patch[\s-]?clamp", r"blood patch",
    # a surgical patch or flap is tissue, not a transdermal dosage form:
    # the "P" of the HOP bundle is a teres *ligament patch*, and the
    # bundle's peptide (octreotide) is subcutaneous
    r"(?:teres|ligament|omental|falciform|tissue|fascial|muscle|serosal|"
    r"pericardial|dural|peritoneal|mesh|graft|pledget)[\s-]?patch(?:es)?",
    r"patch(?:es)? (?:of |made from )?(?:tissue|omentum|ligament|mesh|graft)",
    r"(?:bacitracin|antibiotic)[\s-]?patch", r"\bpatch\b(?=\s*(?:trial|study|group|arm))",
    r"\bpatch\b(?=\s*\))", r"\(patch\)", r"\bPATCH\b(?=[\s:,.])",
    # --- assorted (5.2, 9.3, 10.2)
    r"injection site (?:reactions?|pain|erythema|bruising|nodules?)",
    r"injection drug use", r"people who inject drugs",
    r"pump (?:failure|function|malfunction|inhibitors?)", r"proton pump",
    r"bolus of (?:saline|contrast|air|water)", r"inhalation an(?:a)?esthesi\w+",
    # an imaging tracer or contrast agent is infused alongside the study drug
    # and is never the study drug: "a continuous infusion of FDG will be
    # started" outranked the trial's own intranasal insulin spray
    r"(?:infusions?|injections?|boluss?e?s?) of (?:\[?18[\s-]?f\]?|fdg|"
    r"fluorodeoxyglucose|contrast|gadolinium|radio" + P + r"?tracers?|tracers?|"
    r"radio" + P + r"?label\w*)",
    r"inhaled an(?:a)?esthetic", r"\benema\w*(?= *preparation)",
    r"carbapenemase", r"\bin vitro\b", r"\bin vivo\b", r"\bex vivo\b",
    r"foley", r"balloon cath\w+", r"cervical ripening balloon", r"balloon dilat\w+",
    r"instill\w+ (?:with )?(?:saline|water) ",
    r"(?:drinks?|beverages?|smoothies?|shakes?)\b",
    r"alcoholic drink\w*", r"\botitis\b", r"antibiotic\w*", r"\bnarcotic\w*",
    r"\bcarotid\b", r"atheroscler\w+", r"\bnecrotic\b", r"\bdiabetic\b",
    r"\bidiopathic\b", r"\bsclerotic\b", r"\bpsychotic\b", r"\bnephrotic\b",
    r"\bapoptotic\b", r"\bmitotic\b", r"\bprobiotics?\b", r"\bprognostic\b",
    r"\bdiagnostic\b", r"\basymptomatic\b", r"\bautomatic\b", r"\bhypnotic\b",
    r"\bsyringe (?:pump|driver) (?:failure|alarm)\b",
    r"\bformula(?:tion|ted|tions)\b", r"\bperfusion (?:index|pressure|imaging|scan|"
    r"mri|ct|defect|abnormalit\w+|rate of the)\b", r"\bmyocardial perfusion\b",
    r"\bcerebral perfusion\b", r"\btissue perfusion\b", r"\bperfusion of the\b",
]
MASK_PATTERNS += [
    # anatomy, not a route: "closing the subcutaneous tissue and skin"
    r"sub[\s-]?cutaneous\s+(?:tissues?|fat|layers?|space|pocket)",
]
MASK_RE = [re.compile(p, re.I) for p in MASK_PATTERNS]

def mask(text):
    """Blank masked phrases, preserving length so offsets stay valid."""
    if not text:
        return ""
    out = text
    for rx in MASK_RE:
        out = rx.sub(lambda m: " " * len(m.group(0)), out)
    return out

# ------------------- route words, stripped from the rival-drug token set (10.2)
ROUTE_WORDS = set("""injection injections injected injectable infusion infusions infused
subcutaneous subcutaneously sc sq intravenous intravenously iv intramuscular im
intradermal id intrathecal intraperitoneal intravitreal intratumoral intraarterial
oral orally po tablet tablets capsule capsules pill pills sachet syrup suspension
solution topical cream ointment lotion gel patch transdermal dermal cutaneous
ophthalmic drops eye inhaled inhalation nebulised nebulized aerosol intranasal nasal
spray implant implants vaginal rectal suppository enema sublingual buccal lozenge
intravesical depot pump bolus parenteral enteral nasogastric mouth os per dose doses
mg mcg ug kg ml unit units daily weekly bid tid qd prn placebo saline vehicle sham
control comparator standard care usual arm group dummy water dextrose glucose""".split())

# -------- common non-peptide co-administered agents, for the rival set (10.2)
CO_DRUGS = """metformin sitagliptin saxagliptin linagliptin vildagliptin alogliptin
dapagliflozin empagliflozin canagliflozin ertugliflozin glimepiride gliclazide
glibenclamide glyburide glipizide pioglitazone rosiglitazone acarbose repaglinide
nateglinide prednisone prednisolone dexamethasone methylprednisolone hydrocortisone
melphalan thalidomide lenalidomide pomalidomide cyclophosphamide capecitabine
temozolomide doxorubicin cisplatin carboplatin paclitaxel docetaxel gemcitabine
fluorouracil irinotecan oxaliplatin etoposide vincristine rituximab bevacizumab
tamoxifen letrozole anastrozole exemestane abiraterone enzalutamide apalutamide
darolutamide bicalutamide flutamide nilutamide estradiol estriol estrogen oestrogen
progesterone norethisterone medroxyprogesterone levonorgestrel misoprostol
mifepristone oxytocics ergometrine methylergometrine tranexamic carbetocin
mycophenolate cellcept tacrolimus sirolimus everolimus azathioprine methotrexate
hydroxychloroquine rifampicin rifampin isoniazid ethambutol pyrazinamide levofloxacin
moxifloxacin ciprofloxacin amoxicillin ampicillin ceftriaxone cefazolin meropenem
piperacillin clarithromycin azithromycin metronidazole clindamycin linezolid
fluconazole itraconazole voriconazole posaconazole amphotericin acyclovir
valacyclovir ritonavir tenofovir emtricitabine efavirenz dolutegravir warfarin
aspirin clopidogrel heparin enoxaparin atorvastatin simvastatin rosuvastatin
ramipril lisinopril enalapril losartan valsartan amlodipine metoprolol bisoprolol
carvedilol furosemide spironolactone hydrochlorothiazide omeprazole pantoprazole
esomeprazole ondansetron metoclopramide lactulose rifaximin ursodeoxycholic
levodopa donepezil memantine lithium sertraline fluoxetine citalopram quetiapine
olanzapine risperidone haloperidol gabapentin pregabalin tramadol oxycodone morphine
fentanyl paracetamol acetaminophen ibuprofen naproxen diclofenac ketorolac
colchicine allopurinol febuxostat neomycin lactobacillus propranolol nifedipine
labetalol magnesium betamethasone terbutaline atosiban indomethacin nitroglycerin
dinoprostone sildenafil tadalafil finasteride dutasteride tolterodine solifenacin
mirabegron oxybutynin desmopressin? latanoprost timolol cyclosporine? pilocarpine
ketotifen olopatadine dorzolamide brimonidine prednisolone? fcn 437c ly2409021
ta 7284 metformina metformine alendronate risedronate zoledronic ibandronate
casodex arimidex femara nolvadex xtandi zytiga lupron? zoladex? decapeptyl?
glucophage glucofage palbociclib ribociclib
abemaciclib laquinimod raloxifene fingolimod teriflunomide dimethyl fumarate
nivolumab pembrolizumab ipilimumab atezolizumab durvalumab imiquimod
salbutamol albuterol delafloxacin omarigliptin giredestrant fulvestrant
trimethoprim sulfamethoxazole bortezomib lenvatinib sorafenib sunitinib""".split()
CO_DRUGS = {w.strip("?") for w in CO_DRUGS if len(w) > 3}

# ---- shorthand the trial text uses for a peptide its canonical name misses.
# Only abbreviations/trade names seen in this corpus's records; they are added to
# the peptide's token set so the proximity guard can find it (10.2).
PEP_ALIAS = {
    "desmopressin": ("ddavp", "minirin", "octostim", "nocdurna", "noctiva"),
    "glutathione": ("gsh",),
    "cyclosporine": ("csa", "ciclosporin", "cya", "sandimmun", "neoral", "restasis",
                     "cequa", "ikervis"),
    "corticotropin acth": ("acth", "acthar", "synacthen", "cosyntropin"),
    "insulin glargine": ("lantus", "toujeo", "basaglar", "hoe901"),
    "insulin detemir": ("levemir",),
    "insulin degludec": ("tresiba",),
    "insulin aspart": ("novolog", "novorapid"),
    "insulin lispro": ("humalog",),
    "insulin human regular": ("humulin", "actrapid", "novolin"),
    "liraglutide": ("victoza", "saxenda", "nn2211"),
    "semaglutide": ("ozempic", "wegovy", "rybelsus"),
    "exenatide": ("byetta", "bydureon"),
    "dulaglutide": ("trulicity",),
    "goserelin": ("zoladex",),
    "leuprolide": ("lupron", "eligard", "prostap", "enantone", "leuprorelin"),
    "triptorelin": ("decapeptyl", "trelstar"),
    "teriparatide": ("forteo", "forsteo"),
    "glatiramer acetate": ("copaxone", "glatopa"),
    "octreotide": ("sandostatin",),
    "lanreotide": ("somatuline",),
    "enfuvirtide": ("fuzeon", "t20"),
    "vancomycin": ("vanco", "vancocin"),
    "oxytocin": ("pitocin", "syntocinon"),
    "nesiritide": ("natrecor",),
    "parathyroid hormone 1 84": ("natpara", "natpar"),
    "calcitonin": ("miacalcin", "fortical"),
    "bivalirudin": ("angiomax",),
    "icatibant": ("firazyr",),
}


# A "<hormone> receptor antagonist/agonist <code>" intervention names the peptide as
# the TARGET, not the agent; small-molecule blockers are not peptide drugs (11.2).
RECEPTOR_BLOCKER = re.compile(
    r"receptor (?:antagonist|blocker|inhibitor)|"
    r"\b(?:antagonist|inhibitor) of (?:the )?[a-z0-9\- ]{0,20}receptor", re.I)

def is_receptor_blocker(name, extra=""):
    blob = (name or "") + " " + (extra or "")
    if not RECEPTOR_BLOCKER.search(blob):
        return False
    n = norm(blob)
    # a genuine peptide antagonist still shows peptide morphology / isotope / vaccine
    if PEPTIDE_STEMS.search(n) or (ISOTOPE.search(n) and CHELATOR.search(n)) \
       or (VACCINE_PEP.search(n) and not VACCINE_NEG.search(n)):
        return False
    return True

# ---------------------------------------------------- run 8 verified products
# Products whose names carry no peptide/protein morphology at all and which the
# run-8 identification gate would therefore read as "no peptide drug in this
# trial".  Peptide status is a chemistry call (8.4), but it is made here from a
# retrieved source, never from recall -- the citation for each is the `source`
# column of its drug_routes.tsv row, added in the same run.  Those with a route
# retrieved as well get the route from the table; the rest (PEN-221,
# RLS-0071/pegtarazimod, CM3.1-AC100/AC-100/Dentonin, MOD-6031, FAM-NP41/NP41)
# are peptides on a retrieved source whose route the trial's own record states.
VERIFIED_PEPTIDE_PRODUCTS = re.compile(
    r"\btpx[\s-]?100\b|\bmsi[\s-]?78\b|\bpexiganan\b|\blocilex\b|"
    r"\bpemziviptadil\b|\bpb[\s-]?1046\b|\bhsppc[\s-]?96\b|\boncophage\b|"
    r"\bvitespen\b|\bub[\s-]?311\b|\bcenderitide\b|\bcd[\s-]?np\b|"
    r"\bgsk\s?2586881\b|\bsp[\s-]?16\b|\bgm[\s-]?604\b|\bgm6\b|\bviaject\b|"
    r"\bshr\s?20004\b|\bnoiiglutide\b|\btendu\b|\bleap[\s-]?2\b|"
    r"\bpacap[\s-]?38\b|\bpepgnp\w*|\bpen[\s-]?221\b|\brls[\s-]?0071\b|"
    r"\bpegtarazimod\b|\bcm3[\s.]?1[\s-]?ac[\s-]?100\b|\bac[\s-]?100\b|"
    r"\bdentonin\b|\bmod[\s-]?603[01]\b|\bnp41\b|\bpb[\s-]?1023\b|"
    r"\bglymera\b|\bdpx[\s-]?survivac\b")

# Of those, the two that are recombinant proteins rather than peptides, so that
# a real peptide in the same trial still outranks them (14.2's peptide_rank).
VERIFIED_PROTEIN_PRODUCTS = re.compile(
    r"\bgsk\s?2586881\b|\bhsppc[\s-]?96\b|\boncophage\b|\bvitespen\b")
