"""Decision function for failure_10_21_2026.csv.

Pattern sets built from the 860 verbatim whyStopped texts in this corpus
(failure_methodology.md section 5.5: "from the verbatim texts in the corpus,
not from imagination").  Imported by both build.py and the audit/test harness
(section 10.6 -- one shared decision function).
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (RECRUITMENT, BUSINESS, INEFFECTIVE, TOXIC, COVID, RESIDUAL,
                    STOPPED_EARLY, STATUS_PRIOR, STATUS_PRIOR_DEFAULT)

I = re.I

def norm(t):
    return re.sub(r"\s+", " ", (t or "").replace("\\", "")).strip()

# ---------------------------------------------------------------- 5.1 pointers
POINTER = re.compile(r"^see\s+(?:termination\s+reason\s+in\s+)?detailed\s+description\.?$", I)

# ------------------------------------------------- 5.2 denials, in order
# pandemic first (rarest, most easily destroyed), then safety, then efficacy.
_CAUSAL_VERB = r"(?:based\s+on|due\s+to|because\s+of|related\s+to|attributable\s+to|influenced\s+by|caused\s+by|a\s+result\s+of)"
_DENIAL_VERB = r"(?:" + _CAUSAL_VERB + r"|for)"
_STOPV = '(?:(?:terminated|stopped|halted|discontinued|closed|withdrawn|suspended|cancell?ed|ended|taken|decided|made)\\s+)?'
DENIALS = [
    # "not" must attach DIRECTLY to the causal verb: a loose pattern reads the
    # "not available" of "Study drug not available due to COVID-19 restrictions"
    # as a denial and drops the one true pandemic case (5.2, trap 9).
    ("pandemic", re.compile(
        r"(?:not|nor|never)\s+" + _STOPV + r"(?:directly\s+|in\s+any\s+way\s+)?" + _DENIAL_VERB
        + r"[^.;]*?(?:covid|corona|pandemic)[^.;]*", I)),
    ("safety", re.compile(
        r"(?:no|without)\s+(?:new|unexpected|apparent|additional|any)?\s*"
        r"(?:safety|toxicit\w*|adverse)[^.;]*", I)),
    ("safety", re.compile(
        r"(?:not|never)\s+" + _STOPV + r"(?:directly\s+|in\s+any\s+way\s+)?" + _DENIAL_VERB
        + r"[^.;]*?(?:safety|toxicit\w*|adverse|benefit/risk|risk\s+profile)[^.;]*", I)),
    ("safety", re.compile(
        r"(?:safety|efficacy)\s+(?:concerns?|issues?)\s+(?:was|were)\s+not[^.;]*|"
        r"there\s+(?:has|have|was|were)\s+been\s+no[^.;]*?"
        r"(?:safety|benefit/risk|risk\s+profile)[^.;]*|"
        r"unrelated\s+to[^.;]*?safety[^.;]*|"
        r"neither\s+safety\s+nor\s+efficacy[^.;]*|nor\s+(?:safety|efficacy)\s+reasons[^.;]*|"
        r"not\s+(?:for|a)\s+safety[^.;]*", I)),
    ("efficacy", re.compile(
        r"(?:not|never)\s+" + _STOPV + r"(?:directly\s+|in\s+any\s+way\s+)?" + _DENIAL_VERB
        + r"[^.;]*?(?:efficacy|effectiveness|quality)[^.;]*", I)),
]
# positively-framed safety, scrubbed before matching (5.2)
POSITIVE_SAFETY = re.compile(r"safety\s+benefit[^.;]*", I)

GENTLE = re.compile(
    r"(?:not|never)\s+(?:\w+\s+){0,2}?" + _CAUSAL_VERB + r"[^,;.]*|"
    r"acknowledged\s+no\s+safety\s+concerns[^,;.]*|"
    r"no\s+(?:new\s+|unexpected\s+)?safety\s+(?:concerns?|issues?|signals?)[^,;.]*", I)

def strip_denials(text):
    """Strict pass. Returns (scrubbed, [names of denials removed])."""
    out, removed = POSITIVE_SAFETY.sub(" ", text), []
    if out != text:
        removed.append("positive-safety")
    for name, rx in DENIALS:
        new = rx.sub(" ", out)
        if new != out:
            removed.append(name)
            out = new
    return re.sub(r"\s+", " ", out).strip(), removed

# ------------------------------------------------- 5.3 non-failure stop texts
NONFAILURE = [
    re.compile(r"^met\s+study\s+stopping\s+rules\.?$", I),
    re.compile(r"^study\s+completed\.?$", I),
    re.compile(r"^finished\.?$", I),
    re.compile(r"^commitment\s+completed\.?$", I),
    re.compile(r"^end[-\s]?point\s+reached\.?$", I),
    re.compile(r"^all\s+patients\s+recruited\.?$", I),
    re.compile(r"^administratively\s+complete\b", I),
    re.compile(r"adopted\s+as\s+standard\s+of\s+care", I),
    re.compile(r"halted\s+to\s+analy[sz]e\s+data", I),
    re.compile(r"reached\s+scientific\s+goals", I),
    re.compile(r"met\s+a\s+pre-?defined\s+protocol\s+study\s+stopping\s+criteria", I),
    re.compile(r"non-?inferiority\s+criterion\s+met", I),
    re.compile(r"overcoming\s+the\s+stopping\s+rule", I),
    re.compile(r"convincing\s+results", I),
    re.compile(r"observed\s+>?\s*\d+\s*%\s+efficacy", I),
    re.compile(r"data\s+rolled\s+over\s+into\s+full\s+trial", I),
    re.compile(r"leading\s+to\s+nih\s+funding\s+of\s+a\s+new\s+protocol", I),
    re.compile(r"agreement\s+with\s+the\s+fda\s+that\s+enrollment[^.]{0,40}can\s+stop", I),
    re.compile(r"safety\s+benefit\s+in\s+(?:the\s+)?experimental", I),
]
HARM = re.compile(r"toxicit\w*|adverse\s+event|side\s+effect|death|died|mortalit\w*|"
                  r"morbidit\w*|safety\s+(?:signal|concern|issue)|transaminitis|"
                  r"hypersensitiv\w*|complication", I)
NEG_BEFORE = re.compile(r"\b(?:not|never|no|without|fail\w*|unable|cannot|could\s+not|"
                        r"would\s+not|did\s+not)\b", I)

def is_nonfailure(text):
    """5.3, with the trap-15 negation guard and the harm guard."""
    for rx in NONFAILURE:
        m = rx.search(text)
        if not m:
            continue
        if NEG_BEFORE.search(text[max(0, m.start() - 55):m.start()]):
            continue                      # trap 15
        if HARM.search(text):
            continue                      # explicit harm reported alongside
        return m.group(0)
    return None

# ------------------------------------------------- 5.4 uninformative texts
UNINFORMATIVE = [
    re.compile(r"^why\s+study\s+stopped\.?$", I),
    re.compile(r"^not\s+stated\.?$", I),
    re.compile(r"^withdrawn\.?$", I),
    re.compile(r"^terminated\.?$", I),
    re.compile(r"^suspended\.?$", I),
    re.compile(r"^trial\s+stopped\s+on\s+.{0,25}$", I),
    re.compile(r"^unable\s+to\s+complete\s+(?:the\s+)?study\.?$", I),
    re.compile(r"^reviewing\s+data\.?$", I),
    re.compile(r"^subject\s+withdrew\.?$", I),
    re.compile(r"^study\s+will\s+be\s+restarted\s+at\s+a\s+later\s+date\.?$", I),
    re.compile(r"^\(?\"?terminated\"?\)?[\s:,-]*recruiting\s+or\s+enrolling\s+participants\s+has\s+halted", I),
    re.compile(r"^participants\s+are\s+no\s+longer\s+being\s+(?:examined|treated)", I),
    re.compile(r"^study\s+(?:paused|on\s+hold)\s+for\s+interim\s+analysis\.?$", I),
]

def is_uninformative(text):
    for rx in UNINFORMATIVE:
        if rx.search(text):
            return True
    return False

# ------------------------------------------------- 5.6 COVID
COVID_TERM = re.compile(r"covid[-\s]?(?:19)?|corona\s?virus|\bpandemic\b", I)
CONTRIBUTORY = re.compile(
    r"(?:also|partly|partially|in\s+part|additionally|as\s+well\s+as|compounded\s+by|"
    r"exacerbated\s+by|during\s+the|in\s+the\s+context\s+of|related\s+to\s+our\s+ability)", I)
COVID_INDICATION = re.compile(
    r"(?:no\s+longer\s+studying|studying|study\s+of|trial\s+of|treatment\s+of|"
    r"patients\s+with|diagnosed\s+with|infected\s+with)\s+(?:long[-\s]?)?covid", I)

# ------------------------------------------------- bucket pattern sets
SHORTFALL = (r"\b(?:slow(?:ly|er|est)?|poor(?:ly)?|low(?:er)?|insufficien\w*|inadequate\w*|"
             r"inabilit\w*|unable|difficult\w*|challeng\w*|lack\s+of|lacking|zero|few|"
             r"limited|declin\w*|diminish\w*|reduc\w*|failure|failed|fail\s+to|"
             r"unsuccessful|infeasib\w*|not\s+feasible|not\s+enough|issues?|problems?|"
             r"shortfall|under[-\s]?enrol\w*|under[-\s]?accrual|protracted|\bno\b|none|"
             r"delay\w*|standstill|impossible|not\s+reachable|not\s+met|not\s+reached|"
             r"not\s+achieved|not\s+possible|not\s+able|not\s+meet\w*|missed|unwilling\w*|willingness|"
             r"dropout\w*|drop[-\s]?out\w*|withdrawal\w*|lost\s+to\s+follow|no[-\s]?show\w*|"
             r"\brare\b|decreas\w*|affecting|affected|too\s+(?:long|slow|low|complex|many|much|challenging)|"
             r"severely\s+affected|took\s+too\s+much\s+time|\b0\b|critical\w*)\b")
TOPIC = (r"\b(?:recruit\w*|recuit\w*|rectruit\w*|recruiment|recrutment|accrual\w*|accrue\w*|"
         r"enrol\w*|inclusion|screen\w*|participants?|subjects?|patients?|volunteers?|"
         r"centres?|centers?|sites?|refer+al\w*|sample\s+size|eligib\w*|randomi\w*)\b")

# high-precision recruitment phrases a proximity window cannot reach
RECRUIT_PHRASES = [
    (r"\b0\s+(?:enrollment|accrual|subjects?\s+enrolled)", "zero enrolment"),
    (r"no\s+recruitment\s+since\s+initiation", "no recruitment since initiation"),
    (r"not\s+able\s+to\s+meet\s+recruitment", "could not meet recruitment"),
    (r"not\s+reachable", "target not reachable"),
    (r"not\s+recruited\s+as\s+intended", "not recruited as intended"),
    (r"screened\s+but\s+not\s+enrolled", "screened but not enrolled"),
    (r"incomplete\s+enrollment", "incomplete enrolment"),
    (r"at\s+a\s+standstill", "recruitment at a standstill"),
    (r"delays?\s+in\s+(?:patient\s+)?enrol\w*", "enrolment delays"),
    (r"accrual\s+factor", "accrual factor"),
    (r"^accrual\s+rate\.?$", "accrual rate"),
    (r"^recruitment\s+rate\b", "recruitment rate"),
    (r"lack\s+of\s+appropriate\s+cases", "no eligible cases"),
    (r"under[-\s]?enrol\w*", "under-enrolment"),
    (r"futility\s+for\s+enrol\w*", "enrolment futility"),
    (r"enrollment\s+futility", "enrolment futility"),
    (r"high\s+(?:number\s+of\s+)?screen\w*\s+(?:rate\s+)?failure", "screen failures"),
    (r"screen\s+rate\s+failure", "screen failures"),
    (r"failure\s+of\s+inclusion", "inclusion failure"),
    (r"recruiting\s+failure", "recruiting failure"),
    (r"poorly\s+recruiting", "poor recruitment"),
    (r"<\s*\d+\s+(?:subjects?|patients?|participants?)\s+(?:were\s+)?enrolled", "under-enrolment"),
    (r"only\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
     r"(?:patients?|subjects?|participants?)\s+(?:was|were|had\s+been|completed|enrolled)", "under-enrolment"),
    (r"\d+\s+enrolled\s+of\s+\d+\s+planned", "under-enrolment"),
    (r"enrolling\s+\d+\s+of\s+the\s+target", "under-enrolment"),
    (r"no\s+patients?\s+randomi", "no randomisation"),
    (r"target\s+population\s+not\s+reached", "target not reached"),
    (r"enrollment\s+(?:target|goals?)\s+(?:not\s+reached|not\s+met|could\s+not\s+be\s+achieved)", "target not reached"),
    (r"(?:number|numbe)\s+of\s+eligible\s+patients\s+has\s+been\s+decreased", "fewer eligible patients"),
    (r"lost\s+to\s+follow[-\s]?up", "loss to follow-up"),
    (r"insufficiently\s+powered", "sample size shortfall"),
    (r"insufficient\s+number\s+of\s+subjects", "sample size shortfall"),
    (r"(?:(?:could|can)\s+not\s+be|was\s+not)\s+achieved\s+within\s+a\s+reasonable\s+time", "target not reached"),
    (r"sample\s+size\s+of\s+\d+[^.]{0,40}could\s+not\s+be\s+achieved", "target not reached"),
]

BUSINESS_PATTERNS = [
    # funding
    (r"fund(?:ing|s|ed|er)?\b", "funding"),
    (r"financ\w+", "funding"),
    (r"grant\w*", "funding"),
    (r"budget\w*", "funding"),
    (r"bankrupt\w*|chapter\s+11|ceased\s+operations|dissolution", "sponsor insolvency"),
    (r"no\s+cost\s+extension", "funding"),
    (r"resources?\s+(?:not\s+secured|can\s+be\s+better\s+spent)|unavailable\s+study\s+resources|"
     r"(?:lack|limited|insufficient|loss)\s+of\s+resources|insufficient\s+resources|"
     r"lack\s+of\s+(?:support|sponsor\s+support)|reallocation\s+of\s+study\s+resources", "resources"),
    (r"(?:withdrew|withdrawal\s+of|withdrawn)\s+(?:its\s+|their\s+)?support", "sponsor support withdrawn"),
    (r"support\s+(?:was\s+)?(?:withdrawn|terminated)|ceased?\s+(?:its\s+)?support|"
     r"end\s+their\s+support|declined\s+to\s+fund|retracted\s+their\s+grant", "sponsor support withdrawn"),
    (r"inadequate\s+support\s+to\s+proceed", "sponsor support withdrawn"),
    # sponsor / strategic / portfolio decisions
    (r"business\s+(?:reason|decision|purpose|strateg)\w*", "business decision"),
    (r"strategic\s+(?:reason|decision|business)\w*|business\s+strategy|"
     r"change\s+in\s+(?:clinical|the\s+sponsor'?s?\s+research)\s+strateg\w*|"
     r"commercial\s+strateg\w*|clinical\s+development\s+plan|"
     r"(?:research|development|product\s+development)\s+strateg\w*|"
     r"halted\s+for\s+strategic\s+reasons|concluded\s+for\s+strategic\s+reasons", "strategic decision"),
    (r"corporate\s+decision|company\s+decision|company\s+shifted|management\s+decision|"
     r"industry\s+sponsor\s+decision|funder\s+decision|commercial\s+reasons|"
     r"sponsor\s+discretion|sponsor'?s?\s+decision|decision\s+by\s+sponsor|per\s+sponsor|"
     r"sponsor\s+decision|sponsor\s+decides|sponsor\s+requested|cancellation\s+by\s+sponsor|"
     r"closed\s+by\s+(?:the\s+)?(?:sponsor|funder|grantor)|sponsor\s+closed|"
     r"terminat\w*\s+by\s+(?:the\s+)?sponsor|"
     r"non-?medical\s+reasons|legislative\s+reasons|organizational\s+reasons|"
     r"organisational\s+(?:reasons|problems)|for\s+administrative\s+reasons", "sponsor decision"),
    (r"program(?:me)?\s+(?:was\s+)?terminated|development\s+program\s+has\s+been\s+terminated|"
     r"(?:discontinue|suspend|terminate|halt|cancel)\w*\s+(?:the\s+)?(?:further\s+)?"
     r"(?:development|program)|stopped\s+development|drug\s+development", "programme discontinued"),
    (r"portfolio|shifted\s+(?:the\s+)?focus|changed\s+the\s+focus|scientific\s+priorities\s+shifted|"
     r"no\s+longer\s+(?:interested|aligned)|not\s+(?:be\s+)?pursuing|"
     r"decided\s+not\s+to\s+(?:proceed|pursue|carry\s+out|move\s+forward|go\s+forward|open|renew)|"
     r"no\s+focus\s+on\s+this\s+topic|no\s+longer\s+required|no\s+longer\s+(?:a\s+)?novel|"
     r"no\s+longer\s+deemed\s+appropriate|study\s+was\s+outdated|"
     r"no\s+good\s+reason\s+to\s+proceed|not\s+go\s+forward|"
     r"other\s+behavioral\s+study|engaged\s+in\s+other", "portfolio decision"),
    (r"renew\s+(?:the\s+)?(?:contract|marketing\s+authorization)|did\s+not\s+decide\s+to\s+renew|"
     r"market\s+performance|stop\s+marketing|no\s+commercial\s+availability|"
     r"withdraw\s+\w+\s+due\s+to\s+lack\s+of\s+market", "commercial decision"),
    # investigator / staff
    (r"\bpi\b|principal?\s+investigator|principle\s+investigator|primary\s+investigator|"
     r"investigators?\b|\bsub-?i\b|dr\.?\s+\w+", "investigator"),
    (r"personnel|staff\w*|study\s+team|research\s+team|department\s+chairman|deployed|"
     r"leave\s+of\s+absence|graduated|post-?doc", "personnel"),
    # supply / manufacturing / product
    (r"(?:drug|device|equipment|medication|placebo|agent|antibiotic|vaccine|product|"
     r"study\s+drug|imp|intranasal\s+delivery\s+device|catheter|inhaler|pens?|test\s+article)\b"
     r"[^.;]{0,40}(?:not\s+available|unavailab\w*|no\s+longer\s+available|could\s+not\s+be\s+"
     r"(?:obtained|delivered)|not\s+be\s+obtained|shortage|recall\w*|expir\w*|"
     r"supply\s+chain|stability)", "drug supply"),
    (r"unavailab\w*\s+of\s+(?:study\s+)?(?:drug|device|equipment|medication|placebo)|"
     r"drugs?/equipment\s+unavailab\w*|availability\s+of\s+investigational|"
     r"interruption\s+in\s+drug\s+supply|supply\s+chain\s+issues|"
     r"lack\s+of\s+(?:antibiotic|drug|peptide)\s+availability|"
     r"end\s+of\s+validity\s+of\s+(?:the\s+)?(?:peptide\s+)?vaccine|"
     r"expiry\s+of\s+study\s+drug|study\s+drug\s+expired|bradykinin\s+shortage|"
     r"preserve\s+clinical\s+supplies|product\s+stability|out\s+of\s+the\s+expire\s+date|"
     r"unable\s+to\s+obtain\s+glp|termination\s+of\s+\[?18f|"
     r"did\s+not\s+provide\s+the\s+treatment|withdrew\s+drug|new\s+regulatories\s+of\s+the\s+peptides|"
     r"manufacturing\s+process|adequate\s+clinical\s+batches|bought\s+out", "drug supply"),
    # never started
    (r"(?:study|trial|project)?\s*(?:was\s+|is\s+)?(?:not|never)\s+"
     r"(?:initiated|started|activated|commenced|opened|approved|submitted|realised|realized|"
     r"start\s+up|move\s+ahead|moved\s+forward)", "study never started"),
    (r"never\s+(?:started|opened|initiated|activated|commenced|enrolled|submitted)|"
     r"^not\s+(?:initiated|funded|activated)|withdrawn\s+prior\s+to\s+(?:initiation|enrollment|"
     r"enrolling|patient\s+dosing)|prior\s+to\s+study\s+start|abandoned\s+before\s+opening|"
     r"stopped\s+prior\s+to\s+patient\s+enrollment|not\s+foreseeable|"
     r"did\s+not\s+start\s+up|submission\s+discarded|not\s+move\s+forward\s+to\s+phase", "study never started"),
    # protocol / registration / replacement
    (r"protocol\s+(?:amendment|design|change|revis\w*|rewritten|redesign\w*|being\s+rewritten|"
     r"name\s+change)|(?:being\s+)?redesign\w*|revised\s+(?:study\s+)?protocol|"
     r"replaced\s+(?:with|by)\s+(?:another|a\s+new|new)|replace\s+this\s+(?:study|protocol)|"
     r"new\s+protocol|resubmitted\s+under|re-?applied|registration\s+(?:of\s+this\s+research\s+plan\s+)?"
     r"was\s+incorrect|official\s+request\s+for\s+protocol\s+registration|duplicate\s+study|"
     r"major\s+revision\s+of\s+the\s+protocol|revise\s+the\s+protocol|altered\s+to\s+account|"
     r"submitted\s+as\s+(?:a\s+)?new\s+study|new\s+study\s+to\s+open|different\s+study\s+initiation|"
     r"alternative\s+study|revised\s+to\s+retrospective|changed\s+to\s+insulin|"
     r"study\s+pending\s+amendment|use\s+the\s+qrh\s+for\s+a\s+new\s+study|"
     r"unplanned\s+interim\s+analysis|not\s+to\s+recommence|"
     r"interim\s+analysis\s+has\s+been\s+performed\s+by\s+the\s+site|"
     r"methodological\s+issues|qualified\s+this\s+trial\s+as\s+a\s+new\s+trial|"
     r"study\s+a\s+different\s+medication|new\s+pilot\s+trial|no\s+longer\s+fit\s+the\s+description|"
     r"joint\s+industry\s+effort|new\s+formulation|new\s+compounds|"
     r"alternative\s+joint|superseded\s+this\s+study", "protocol change"),
    # regulatory / administrative
    (r"^administrat\w+|administrat\w+\s+(?:reason|problem|challenge|terminated|suspended)|"
     r"\birb\b|ethics?\s+(?:approval|committee)|authorization\s+denied|approval\s+denied|"
     r"\bmhra\b|\baifa\b|italian\s+medicines\s+agency|\bmpa\b|\bmoph\b|\bwcmq\b|\bmetc\b|"
     r"regulatory\s+(?:uncertainty|authorit|hold)|awaiting\s+fda\s+approval|"
     r"fda\s+changed\s+the\s+labeling|fda\s+draft\s+guidance|release\s+from\s+the\s+pmr|"
     r"pharmacy\s+temporarily\s+suspended|expiration\s+of\s+irb\s+approval|"
     r"no\s+documentation|inadequate\s+supporting\s+documentation|audits|"
     r"ind\s+approval|commitment\s+for\s+license|cradda?\s+partner|crada\s+partner|"
     r"contract|conflict\s+of\s+interest|delay\s+of\s+ethics\s+approval|not\s+approved\s+by", "regulatory/administrative"),
    (r"\boperational\b|logistic\w*|technical\s+(?:issue|problem)|technical\w*\s+not\s+feasible|"
     r"lack\s+of\s+feasibility|not\s+feasible\s+within\s+timeframe|"
     r"electronic\s+diary|assay|unreliable\s+psa|not\s+evaluable|not\s+fully\s+developed\s+and\s+validated|"
     r"unable\s+to\s+(?:measure|analyze|analyse|perform|reliably\s+measure)|"
     r"not\s+possible\s+to\s+visuali[sz]e|ultrasound\s+machines|microdialysis|"
     r"infusion\s+set|mixed\s+randomization|error\s+made\s+by\s+local\s+pharmacy|"
     r"data\s+(?:collection\s+discontinuity|was\s+not\s+collected|were\s+not\s+collected)|"
     r"could\s+not\s+be\s+optimally\s+analyzed|insufficient\s+data\s+to\s+analyze|"
     r"no\s+data\s+is\s+available|internal\s+review|stopped\s+after\s+internal\s+review|"
     r"phlebotomy|equipment\s+unvailable|partner\s+with\s+cath\s+lab|"
     r"loss\s+of\s+clinical\s+equipoise", "technical/operational"),
    # competing work, external evidence, scope
    (r"competing|competitive\s+trial|competitive\s+studies|other\s+new\s+drugs|"
     r"higher\s+enrolling\s+studies", "competing study"),
    (r"(?:published|publication|recently\s+published|other\s+(?:study|trial)s?\s+(?:suggest|demonstrated)|"
     r"newly\s+available\s+data|recent\s+studies\s+suggest|preliminary\s+data\s+run\s+on\s+rat|"
     r"preclinical|did\s+not\s+meet\s+its\s+primary\s+endpoint|outcome\s+of\s+relax|"
     r"rtog0525|abemaciclib|maestro-01|i3y-mc-jpcm|not\s+enhance\s+predictive\s+value|"
     r"dose-?response\s+problem|clinical\s+translation\s+difficult|"
     r"would\s+not\s+produce\s+conclusive\s+results)", "external evidence"),
    (r"(?:no\s+longer\s+studying|not\s+a\s+novel\s+study|standard\s+of\s+care|"
     r"changing\s+epidemiology|change\s+in\s+standard\s+care|changes\s+in\s+standard\s+care|"
     r"practice\s+changes|widespread\s+use\s+of|infrequent\s+use\s+of|"
     r"market\s+authorizations|health\s+insurance\s+reimbursement)", "clinical landscape"),
    (r"pollen\s+season|seasonal", "timing decision"),
    (r"no\s+plan\s+to\s+continue|preparing\s+our\s+results\s+for\s+publication|"
     r"will\s+not\s+resume|without\s+having\s+re-?opened|not\s+be\s+completed|"
     r"cut\s+off\s+should\s+be\s+scheduled|could\s+not\s+be\s+completed|"
     r"reopening\s+the\s+study[^.]{0,20}not\s+feasible", "abandoned"),
]

INEFFECTIVE_PATTERNS = [
    (r"futil\w*", "futility"),
    (r"lack\s+of\s+(?:clinical\s+)?efficacy|lack\s+of\s+effect|no\s+efficacy|"
     r"inefficac\w*|ineffective|not\s+effective|proved\s+ineffective|treatment\s+ineffective", "lack of efficacy"),
    (r"primary\s+(?:endpoint|outcome)[^.;]{0,30}(?:not\s+(?:met|reached|achieved)|"
     r"was\s+not\s+met|miss\w*)|did\s+not\s+meet\s+(?:its\s+)?primary", "primary endpoint missed"),
    (r"(?:not|no\s+longer)\s+superior\w*|superiority\s+(?:was\s+)?no\s+longer\s+attainable|"
     r"not\s+Superior\s+to\s+standard", "superiority not shown"),
    (r"no\s+(?:significant|statistical|dramatic)\s+(?:difference|benefit|change|improvement|effect|uptake)|"
     r"not\s+a\s+significant\s+difference|no\s+statistical\s+difference|"
     r"not\s+show\s+significant\s+benefit|treatment\s+differences\s+not\s+detected|"
     r"no\s+survival\s+benefit|inconsistent\s+treatment\s+benefit|"
     r"failed\s+to\s+demonstrate|no\s+sign\s+of\s+the\s+anticipated\s+effect|"
     r"negative\s+efficacy\s+results|obtained\s+results\s+were\s+not\s+good|"
     r"low\s+probability\s+of\s+success|risk\s+of\s+(?:failure|non-?response)[^.;]{0,40}higher|"
     r"low\s+response|did\s+not\s+pass\s+stage\s+1|do\s+not\s+support\s+the\s+expected|"
     r"lack\s+of\s+substantial\s+evidence|not\s+needed\s+in\s+patients|"
     r"achieve\s+significative\s+differences|deemed\s+futile", "no efficacy difference"),
    (r"stopping\s+rule\s+on\s+response|less\s+than\s+\d+%\s+of\s+the\s+phase\s+ii", "futility rule"),
    (r"interim\s+(?:analys[ei]s|review)[^.;]{0,80}efficacy|efficacy\s+data\b", "interim efficacy analysis"),
]

TOXIC_PATTERNS = [
    (r"toxicit\w*|toxic\b", "toxicity"),
    (r"adverse\s+event|side\s+effect|\bsae\b", "adverse events"),
    (r"safety\s+(?:concern|issue|signal|reason)\w*|for\s+safety\b|stopped\s+the\s+study\s+for\s+safety", "safety concern"),
    (r"morbidit\w*|mortalit\w*|\bdeaths?\b|early\s+deaths", "mortality/morbidity"),
    (r"transaminitis|hepatic\s+safety|liver\s+transaminitis|hypersensitivity\s+reaction|"
     r"lymphoproliferative\s+disorder|arryth\w*|tolerabilit\w*|severe\s+toxicit\w*|"
     r"patient\s+complications|too\s+many\s+safety\s+issues|cluster\s+of\s+adverse", "safety finding"),
]

# 5.7 weak signals -- only when nothing concrete matched
WEAK = [
    (re.compile(r"data\s+(?:and\s+)?safety\s+monitoring\s+board|\bdsmb\b|\bdsmc\b|"
                r"data\s+monitoring\s+committee|independent\s+(?:data\s+)?monitoring|"
                r"independent\s+committee|monitoring\s+board", I),
     None, "monitoring-board stop", "a monitoring-board stop, which may be for safety or for futility"),
    (re.compile(r"clinical\s+hold|placed\s+on\s+(?:clinical\s+)?hold|fda\s+put\s+the\s+study\s+on\s+hold|"
                r"enrollment\s+hold|on\s+hold", I),
     BUSINESS, "regulatory/administrative hold", "an unexplained hold, with no reason given"),
    (re.compile(r"lack\s+of\s+statistical\s+power|statistical\s+power|"
                r"power\s+analysis|sample\s+size\s+calculation|would\s+need\s+\d+\s+patients", I),
     INEFFECTIVE, "underpowering", "underpowering, which the text does not attribute to recruitment"),
    (re.compile(r"interim\s+analys[ei]s|interim\s+(?:data|review|outcomes)|preliminary\s+analysis|"
                r"stage\s+1\s+interim|pre-?specified\s+interim", I),
     INEFFECTIVE, "bare interim analysis", "an interim-analysis stop with no finding stated"),
]

# 5.7 bare decision mentions, demoted when another bucket matches substantively
BARE_DECISION = re.compile(
    r"^(?:(?:the\s+)?sponsor|company|corporate|management|per\s+sponsor|trial\s+terminated\s+by\s+sponsor|"
    r"closed\s+by\s+sponsor|decision\s+by\s+sponsor|termination\s+by\s+sponsor)\b[^.;]{0,60}$", I)
THIN_BUCKET = re.compile(
    r"^(?:administrative|administratively\s+terminated|operational|per\s+sponsor|"
    r"management\s+decision|trial\s+terminated\s+by\s+sponsor|business\s+reasons?|"
    r"business\s+decision|sponsor\s+decision|sponsor'?s?\s+decision|company\s+decision|"
    r"corporate\s+decision|strategic\s+decision|funding|funder\s+decision|pi\s+request|"
    r"per\s+pi\s+request|sponsor\s+requested|program\s+terminated|business\s+purposes?|"
    r"closed\s+by\s+sponsor|decision\s+by\s+sponsor|termination\s+by\s+sponsor|"
    r"due\s+to\s+administrative\s+reasons|for\s+business\s+reasons)\.?$", I)

OTHER_TRIAL_EFFICACY = re.compile(
    r"(?:negative\s+efficacy\s+results|outcome|results?)\s+of\s+(?:the\s+)?"
    r"(?:phase\s+i+i?i?\s+)?[\w-]*\d[\w-]*\s*(?:trial|study)|"
    r"related\s+study[^.;]{0,50}did\s+not\s+meet|"
    r"data\s+relating\s+to\s+\w+\s+in\s+advanced", I)

CAUSAL = re.compile(
    r"\b(?:due\s+to|because\s+of|because|owing\s+to|as\s+a\s+result\s+of|in\s+view\s+of|"
    r"caused\s+by|secondary\s+to)\b", I)


def _matches(text):
    """All bucket matches as (offset, bucket, sub-reason, matched text)."""
    out = []
    for rx, sub in RECRUIT_PHRASES:
        for m in re.finditer(rx, text, I):
            out.append((m.start(), RECRUITMENT, sub, m.group(0)))
    # proximity rule: a shortfall predicate beside a topic word, either order.
    # offset recorded at the TOPIC word, so a business cause stated first wins.
    for m in re.finditer(SHORTFALL + r"[^.;]{0,30}?(" + TOPIC + r")", text, I):
        out.append((m.start(1), RECRUITMENT, "recruitment shortfall", m.group(0)))
    for m in re.finditer(r"(" + TOPIC + r")[^.;]{0,30}?" + SHORTFALL, text, I):
        out.append((m.start(1), RECRUITMENT, "recruitment shortfall", m.group(0)))
    for pats, bucket in ((BUSINESS_PATTERNS, BUSINESS),
                         (INEFFECTIVE_PATTERNS, INEFFECTIVE),
                         (TOXIC_PATTERNS, TOXIC)):
        for rx, sub in pats:
            for m in re.finditer(rx, text, I):
                out.append((m.start(), bucket, sub, m.group(0)))
    return sorted(out, key=lambda z: z[0])


def _covid_is_cause(text):
    """5.6 rule 1. Returns the matched COVID term, or None."""
    for m in COVID_TERM.finditer(text):
        if COVID_INDICATION.search(text[max(0, m.start() - 40):m.end() + 10]):
            continue                                        # indication, not a reason
        if CONTRIBUTORY.search(text[max(0, m.start() - 35):m.start()]):
            continue                                        # contributory factor
        return m.group(0)
    return None


def _causal_clause(text):
    """First causal clause not prefixed by a contributory qualifier (5.6 rule 2)."""
    for m in CAUSAL.finditer(text):
        if CONTRIBUTORY.search(text[max(0, m.start() - 20):m.start()]):
            continue
        end = len(text)
        for sep in (". ", "; "):
            p = text.find(sep, m.end())
            if p != -1:
                end = min(end, p)
        return m.end(), end
    return None


def classify_text(raw, status, source="whyStopped", operational_residual=True):
    """Read a stated stop reason.  Returns a dict or None if no reason is on record."""
    text = norm(raw)
    if not text:
        return None
    note = []
    scrubbed, removed = strip_denials(text)
    if removed:
        note.append("denied cause(s) stripped: " + ", ".join(removed))

    # 5.6 rule 1 -- pandemic tested before the non-failure phrasings (5.3)
    cov = _covid_is_cause(scrubbed)
    hits = _matches(scrubbed)
    if cov:
        others = [h for h in hits if h[1] != COVID]
        if not others:
            return dict(reason=COVID, confidence="High", basis=f"{source} (pandemic named as cause)",
                        sub="pandemic", note=note, quote=text, rule="5.6.1 pandemic is the cause named")
        note.append("pandemic named without a contributory qualifier, so it outranks the "
                    "concrete cause also present (5.6.1)")
        return dict(reason=COVID, confidence="Medium", basis=f"{source} (pandemic named as cause)",
                    sub="pandemic", note=note, quote=text, rule="5.6.1 pandemic is the cause named")

    nf = is_nonfailure(text) or is_nonfailure(scrubbed)
    if nf:
        return dict(reason=None, confidence="Low", basis="NONE - stated reason describes a non-failure stop",
                    sub="", note=note + [f'the stated reason describes a non-failure stop ("{nf}")'],
                    quote=text, rule="5.3 not a failure")
    if is_uninformative(scrubbed):
        return dict(reason=None, confidence="Low", basis="NONE - stated reason carries no reason",
                    sub="", note=note + ["the stated reason restates the status and names no cause"],
                    quote=text, rule="5.4 uninformative")

    if not hits:
        # gentle second pass (5.2) -- never accept Toxic/unsafe from it
        if removed:
            g = re.sub(r"\s+", " ", GENTLE.sub(" ", text)).strip()
            gh = [h for h in _matches(g) if h[1] != TOXIC]
            if gh:
                hits, note = gh, note + ["reason recovered by the gentle denial pass (5.2)"]
    if hits and OTHER_TRIAL_EFFICACY.search(scrubbed):
        kept = [h for h in hits if h[1] != INEFFECTIVE]
        if kept:
            hits = kept
            note.append("the stated reason is another named trial's efficacy result, so the "
                        "stop of this trial is a sponsor decision in light of external data "
                        "rather than a finding about this intervention (section 1)")
    if hits:
        cc = _causal_clause(scrubbed)
        rule = "5.6.3 first reason named"
        pool = hits
        if cc:
            inside = [h for h in hits if cc[0] <= h[0] < cc[1]]
            if inside:
                pool, rule = inside, "5.6.2 clause after the causal marker"
        if not cc or pool is hits:
            tox = [h for h in pool if h[1] == TOXIC]
            if tox and not cc:
                pool, rule = tox, "5.6.4 explicit safety statement outranks the rest"
        # 5.7 demote a bare decision mention
        if pool[0][1] == BUSINESS and BARE_DECISION.search(text):
            sub = [h for h in pool if h[1] != BUSINESS]
            if sub:
                pool, rule = sub, "5.7 bare decision mention demoted"
                note.append("the business signal was a bare decision mention, so the "
                            "substantive bucket was taken (5.7)")
        off, bucket, sub, matched = pool[0]
        buckets = {h[1] for h in hits}
        conf = "High"
        if len(buckets) > 1:
            conf = "Medium"
            note.append("the text named more than one bucket (" +
                        ", ".join(sorted(buckets)) + "); arbitrated by " + rule)
        if THIN_BUCKET.search(text):
            conf = "Medium" if conf == "High" else conf
            note.append("the text names a bucket without substance, so confidence is capped (5.7)")
        return dict(reason=bucket, confidence=conf, basis=source, sub=sub,
                    note=note, quote=text, rule=rule, matched=matched)

    # 5.7 weak signals
    for rx, forced, sub, why in WEAK:
        m = rx.search(scrubbed)
        if not m:
            continue
        if sub == "monitoring-board stop":
            if "safety" in removed or "positive-safety" in removed:
                continue                          # text explicitly denies safety
            forced = INEFFECTIVE
        return dict(reason=forced, confidence="Low", basis=f"{source} (weak signal)", sub=sub,
                    note=note + [f"the stated reason gives only {why}"], quote=text,
                    rule="5.7 weak signal")

    # 5.4 operational residual, stopped-early trials only
    if operational_residual and status in STOPPED_EARLY and len(text.split()) >= 3:
        return dict(reason=BUSINESS, confidence="Medium", basis=f"{source} (operational circumstance)",
                    sub="operational circumstance", note=note +
                    ["the bucket was read from the circumstance described rather than from an "
                     "explicit business statement (5.4)"],
                    quote=text, rule="5.4 operational residual")
    return dict(reason=None, confidence="Low", basis="NONE - stated reason carries no reason",
                sub="", note=note + ["the stated reason names no cause this method can read"],
                quote=text, rule="5.4 uninformative")


def status_prior(status):
    return STATUS_PRIOR.get((status or "").upper(), STATUS_PRIOR_DEFAULT)


# =====================================================================
# 4.1  Registry narrative fields beyond whyStopped
# =====================================================================
STOP_SUBJECT = (r"\b(?:stud(?:y|ies)|trial|protocol|enrol\w*|accrual|recruitment|"
                r"randomi[sz]\w*|program(?:me)?|investigation)\b")
STOP_VERB = (r"\b(?:terminat\w*|stopp\w*|halt\w*|discontinu\w*|clos(?:e|ed|ing|ure)\b|"
             r"withdraw\w*|withdrew|suspend\w*|cancell?\w*|abandon\w*|curtail\w*|"
             r"ceas(?:e|ed|ing)\b|not\s+initiated|never\s+(?:started|initiated|activated))")
# long prose fields are full of protocol boilerplate about stopping the DRUG
DOSING_BOILER = re.compile(
    r"will\s+be\s+(?:stopped|discontinued|halted|terminated)|will\s+discontinue|"
    r"until\s+(?:toxicity|progression|disease)|(?:participants?|patients?|subjects?)\s+will\b|"
    r"study\s+drug\s+will|dose\s+will|may\s+be\s+discontinued|if\s+the\s+(?:patient|subject)|"
    r"criteria\s+for\s+(?:discontinu|withdraw|stopping)|reasons?\s+for\s+discontinu|"
    r"(?:who|that)\s+discontinue|should\s+be\s+discontinued|be\s+withdrawn\s+from\s+the\s+study|"
    r"permitted\s+to|eligible\s+(?:patients?|subjects?)|inclusion\s+criteria|"
    r"exclusion\s+criteria|will\s+be\s+(?:randomi|enrolled|assigned)|"
    r"\bwill\s+(?:be|include|continue|document|occur|consist|last|receive|undergo|have|"
    r"remain|then|also|not\s+receive)\b|\bmay\s+(?:continue|be|receive|remain)\b|"
    r"one\s+of\s+the\s+following|screening\s+phase|treatment\s+phase|"
    r"follow-?up\s+(?:phase|visit|period)|every\s+\d+\s+(?:months?|weeks?|days?)|"
    r"(?:up\s+to|approximately)\s+\d+\s+(?:days?|weeks?|months?)\s+(?:prior|after)|"
    r"\b(?:will|would|shall)\s+(?:be\s+|not\s+be\s+)?(?:terminat|stop|halt|discontinu|"
    r"clos|end|withdraw|suspend|cancel)\w*|was\s+included\s+whereby|"
    r"^(?:subjects?|patients?|participants?|pts)\b|(?:were|are|was)\s+allowed\s+to|"
    r"roll-?over\s+study|as\s+judged\s+by|until\s+they\s+no\s+longer", I)
EARLY_STOP = re.compile(
    r"(?:terminated|stopped|closed|halted|ended|discontinued)\s+(?:early|prematurely)|"
    r"earl(?:y|ier)\s+(?:termination|closure|discontinuation)|ended\s+prematurely|"
    r"premature(?:ly)?\s+(?:terminat|clos|stopp|discontinu)", I)

def _sentences(text):
    t = re.sub(r"<[^>]{1,40}>", " \u2022 ", text or "")
    t = norm(t)
    parts = []
    for chunk in t.split("\u2022"):
        parts += re.split(r"(?<=[.;!?])\s+(?=[A-Z0-9(])", chunk)
    return [p.strip() for p in parts if p.strip()]

def stop_sentences(text, maxlen=400):
    """Sentences whose subject is the study and which report that it stopped (4.1)."""
    out = []
    for s in _sentences(text):
        if len(s) > maxlen or DOSING_BOILER.search(s):
            continue
        if EARLY_STOP.search(s) or re.search(
                STOP_SUBJECT + r"[^.;]{0,60}?" + STOP_VERB, s, I) or re.search(
                STOP_VERB + r"[^.;]{0,60}?" + STOP_SUBJECT, s, I):
            out.append(s)
    return out

def classify_narrative(text, status, source):
    """4.1 -- confidence capped one step below the dedicated field.  5.4's operational
    residual is not applied here: it is about the sponsor's answer to "why did this
    stop", and a narrative sentence that matches no keyword states no reason."""
    for s in stop_sentences(text):
        d = classify_text(s, status, source=source, operational_residual=False)
        if d and d["reason"]:
            d["confidence"] = {"High": "Medium", "Medium": "Low", "Low": "Low"}[d["confidence"]]
            d["note"] = d["note"] + ["read from a narrative field rather than from the "
                                     "sponsor's answer to \"why did this stop\", so confidence "
                                     "is capped one step below (4.1)"]
            return d
    return None

def classify_dispositions(disps, status):
    """4.1 -- a trial-level reason appearing as a participant-disposition category."""
    TRIAL_LEVEL = re.compile(
        r"\b(?:study|trial)\b[^.;]{0,25}\b(?:terminat|clos|stopp|withdraw|halt|suspend)|"
        r"\b(?:terminat|clos|stopp|halt)\w*\s+by\s+(?:the\s+)?(?:sponsor|investigator|irb)", I)
    for d in disps:
        if not TRIAL_LEVEL.search(d):
            continue
        got = classify_text(d, status, source="participant-flow disposition type",
                            operational_residual=False)
        if got and got["reason"]:
            got["confidence"] = "Medium" if got["confidence"] == "High" else "Low"
            return got
    return None


# =====================================================================
# 6  Turning a publication into a reason
# =====================================================================
# 6.1 relevance gate: the sentence must frame a trial endpoint or a comparison
ENDPOINT_FRAME = re.compile(
    r"primary\s+(?:endpoint|outcome)|secondary\s+(?:endpoint|outcome)|composite\s+(?:endpoint|outcome)|"
    r"\bendpoint\b|outcome\s+measure|compared\s+with|compared\s+to|versus|\bvs\.?\b|"
    r"placebo|control\s+(?:group|arm)|standard\s+of\s+care|between[-\s](?:group|arm)|"
    r"hazard\s+ratio|odds\s+ratio|risk\s+ratio|\bHR\b|\bOR\b|\bRR\b|p\s*[<>=]|p-?value|"
    r"significant\w*|\barm\b|treatment\s+group", I)
# reject outright, whatever else matches
FAVOURABLE_NEGATION = re.compile(
    r"did\s+not\s+(?:increase|worsen|raise|exacerbate|impair|prolong|affect\s+adversely|"
    r"differ\s+in\s+(?:safety|adverse))|no\s+(?:increase|worsening|excess)\s+in\s+"
    r"(?:the\s+)?(?:incidence\s+of\s+)?(?:adverse|serious)|was\s+not\s+inferior|"
    r"non-?inferior(?:ity)?\s+(?:was\s+)?(?:met|demonstrated|established|confirmed)|"
    r"no\s+(?:significant\s+)?(?:safety|tolerability)\s+(?:concerns?|signals?|issues?)\s+"
    r"(?:were\s+)?(?:observed|identified|reported)|well\s+tolerated|"
    r"no\s+treatment-?related\s+(?:deaths|serious)", I)
POSITIVE_FINDING = re.compile(
    r"significant(?:ly)?\s+(?:improv\w*|increas\w*|reduc\w*|decreas\w*|greater|better|higher\s+"
    r"(?:response|efficacy)|lower\s+(?:risk|rate\s+of\s+(?:death|progression)))|"
    r"was\s+(?:safe|effective|efficacious|well\s+tolerated|superior)|were\s+effective|"
    r"met\s+(?:its|the)\s+primary\s+(?:endpoint|outcome)|"
    r"demonstrated\s+(?:significant|efficacy|clinical\s+benefit|antiviral\s+activity)|"
    r"observed\s+to\s+have\s+significant|promising\s+(?:strategy|agent|results|approach)|"
    r"improved\s+(?:significantly|outcomes|survival)|"
    r"(?:benefit|efficacy)\s+was\s+(?:observed|demonstrated|confirmed)|"
    r"achieved\s+(?:its|the)\s+primary|supports?\s+(?:the\s+)?(?:use|further\s+development)|"
    r"improved\s+the\s+[^.;]{0,40}primary|"
    r"(?:proportion|rate|survival)\s+was\s+\d+%?[^.;]{0,30}versus\s+\d+%", I)
TIMEPOINT_STOP = re.compile(r"\bend(?:ed|ing)?\s+of\s+(?:treatment|study|therapy|follow-?up|"
                            r"period|cycle|infusion|dosing)", I)
OPTIONS_SENSE = re.compile(r"(?:limited|few|no|lack\s+of)\s+(?:\w+\s+){0,2}?treatment\s+options?|"
                           r"therapeutic\s+options?", I)
METHODS_BOILER = re.compile(
    r"^(?:background|methods?|objectives?|aims?|introduction|results?|conclusions?|"
    r"purpose|design|importance|rationale)\s*:|"
    r"\bwe\s+(?:used|analy[sz]ed|assessed|conducted|performed|searched|aimed|sought|report|review)|"
    r"\bto\s+(?:test|determine|evaluate|assess|investigate|compare|examine)\s+whether|"
    r"the\s+(?:aim|objective|purpose|goal)\s+(?:of|was|is)|"
    r"defined\s+as|if\s+any\s+of\s+the\s+following|"
    r"inclusion\s+and\s+exclusion|statistical\s+analys|regression\s+model|"
    r"\bassum\w*|may\s+result\s+in|center\s+effect|this\s+(?:review|article|paper)|"
    r"retrospective\s+analys|post\s*-?hoc|subsets?\s+of\s+patients|in\s+contrast\s+with|"
    r"\bprotocol\s+(?:paper|describes)", I)
POOLED = re.compile(
    r"\d+\s+(?:studies|trials)|\bI²\b|\bI2\s*=|pooled|meta-?analys|systematic\s+review|"
    r"(?:several|many|other|previous|most|numerous|various)\s+(?:clinical\s+)?(?:trials|studies)|"
    r"\bin\s+(?:other\s+)?clinical\s+trials\b|"
    r"previous(?:ly)?\s+(?:trials|studies|reported|published)|literature\s+search|"
    r"randomi[sz]ed\s+controlled\s+trials\s+(?:were|have)", I)
SUBSYSTEM = re.compile(
    r"(?:data\s+collection\s+system|glycemic\s+data|meter|monitor(?:ing)?\s+(?:device|system)|"
    r"assay|questionnaire|software|platform|catheter|pump|sensor)\s+[^.;]{0,30}"
    r"(?:discontinued|replaced|withdrawn)", I)
# 6.1 enumeration of endpoints is not a finding (trap 14)
ENUMERATION = re.compile(
    r"(?:primary|secondary|co-?primary)\s+(?:outcomes?|endpoints?)\s+"
    r"(?:was|were|is|are|included?|comprised?|consisted|assessed|measured|compared)\b", I)
HARM_PREDICATE = re.compile(
    r"(?:higher|increased|greater|more\s+frequent|excess|unacceptable|dose-?limiting|"
    r"severe|serious|fatal|led\s+to|resulted\s+in|caused|attributable|incidence\s+of)\b", I)
# titles that cannot report this trial's result
BAD_TITLE = re.compile(
    r"\breview\b|systematic|meta-?analys|\bprotocol\b|rationale\s+and\s+design|study\s+design|"
    r"overview|narrative|landscape|perspectives?|advances|current\s+status|guideline|"
    r"consensus|update|\beditorial\b|commentary|state\s+of\s+the\s+art|"
    r"challenges\s+and|future\s+directions|a\s+primer|what\s+we\s+know", I)

def _lit_reject(s):
    for rx, why in ((FAVOURABLE_NEGATION, "favourable negation"),
                    (POSITIVE_FINDING, "positive finding"),
                    (TIMEPOINT_STOP, "protocol timepoint read as a stop"),
                    (OPTIONS_SENSE, "the 'treatment options' sense"),
                    (METHODS_BOILER, "methods/review boilerplate"),
                    (POOLED, "pooled or other-trial statement"),
                    (SUBSYSTEM, "sub-system statement"),
                    (ENUMERATION, "an enumeration of endpoints")):
        if rx.search(s):
            return why
    return None

# 4 tier 4 -- an endpoint-miss statement.  An explicit miss construction is
# required: merely framing an endpoint is not a finding (6.1, trap 14).
PATIENT_SUBJECT = re.compile(
    r"(?:\d+|few|some|most|many|several)?\s*(?:patients?|subjects?|participants?|children|"
    r"adults?|women|men)\s+(?:\w+\s+){0,6}?$", I)

ENDPOINT_MISS = re.compile(
    r"did\s+not\s+meet\s+(?:its\s+|the\s+)?(?:primary|co-?primary|pre-?specified|"
    r"prespecified|primary\s+or\s+secondary)|"
    r"(?:primary|co-?primary)\s+(?:end[-\s]?point|outcome)s?[^.;]{0,50}?"
    r"(?:was|were)?\s*not\s+(?:met|reached|achieved|significant)|"
    r"failed\s+to\s+(?:meet|demonstrate|show|achieve|improve|reach)|"
    r"no\s+significant\s+(?:difference|benefit|improvement|effect|reduction|increase)"
    r"[^.;]{0,70}(?:primary|end[-\s]?point|outcome|placebo|control|standard)|"
    r"(?:primary|end[-\s]?point|outcome|placebo|control)[^.;]{0,70}"
    r"no\s+significant\s+(?:difference|benefit|improvement|effect|reduction)|"
    r"was\s+not\s+superior|not\s+superior\s+to\s+(?:placebo|control|standard)|"
    r"did\s+not\s+(?:improve|prolong\s+survival|increase\s+survival|confer)|"
    r"stopped\s+(?:early\s+)?(?:for|because\s+of)\s+futility|"
    r"terminated\s+(?:early\s+)?for\s+futility|futility\s+analysis|"
    r"no\s+(?:clinical|survival|treatment|added)\s+benefit|"
    r"(?:lack|absence)\s+of\s+(?:efficacy|clinical\s+benefit)", I)


def classify_publication(papers, status, source="bundle literature", start_year=None):
    """Sections 6.1-6.4.  Tier 3 (a trial-level early-stop statement) and tier 4
    (an explicit endpoint-miss statement) only.  Every other sentence is rejected:
    the bundled literature is mostly reviews, sub-studies and unrelated papers."""
    best = None
    for pap in papers:
        title = pap.get("title", "") or ""
        if BAD_TITLE.search(title):
            continue
        # 6.4 -- a paper published before the trial started cannot report its result
        y = (pap.get("year") or "").strip()
        if start_year and y.isdigit() and int(y) < int(start_year):
            continue
        for s in _sentences(pap.get("abstract", "") or ""):
            if len(s) > 400 or _lit_reject(s):
                continue
            # --- tier 3: the trial itself stopped early, with a reason
            trial_stop = bool(EARLY_STOP.search(s)) and bool(
                re.search(STOP_SUBJECT, s, I)) and not POOLED.search(s)
            if trial_stop:
                d = classify_text(s, status, source=source, operational_residual=False)
                if d and d["reason"]:
                    if d["reason"] == TOXIC and not HARM_PREDICATE.search(s):
                        continue                       # 7.3 / trap 14
                    d["confidence"] = "Medium"
                    d["note"] = d["note"] + ["a trial-level early-stop statement in a "
                                             "publication rather than a sponsor statement (6.2)"]
                    if best is None or 3 > best[0]:
                        best = (3, d, pap, s)
                continue
            # --- tier 4: an explicit endpoint-miss statement -> Ineffective only
            m = ENDPOINT_MISS.search(s)
            if not m or not ENDPOINT_FRAME.search(s):
                continue
            if PATIENT_SUBJECT.search(s[max(0, m.start() - 45):m.start()]):
                continue                           # participants, not the intervention
            prim = re.search(r"(?:primary|co-?primary)\s+(?:end[-\s]?point|outcome)", s, I)
            sec = re.search(r"secondary\s+(?:end[-\s]?point|outcome)", s, I)
            rank = 4 if prim else (1 if sec else 2)
            d = dict(reason=INEFFECTIVE,
                     confidence="High" if prim else ("Low" if rank == 1 else "Medium"),
                     basis=source, sub="endpoint miss reported in a publication",
                     note=["the bucket came from a publication rather than a sponsor "
                           "statement (6.3)"],
                     quote=s, rule="6.1 endpoint-miss statement", matched=m.group(0))
            if rank == 1:
                d["note"].append("the statement concerns only secondary outcomes (6.3)")
            if best is None or rank > best[0]:
                best = (rank, d, pap, s)
    if best is None:
        return None
    rank, d, pap, s = best
    if (pap.get("reftype") or "") == "BACKGROUND":
        d["confidence"] = "Low"
        d["note"] = d["note"] + ["the paper is a registry-listed BACKGROUND reference, so it may "
                                 "describe related work rather than this trial's own result (6.4)"]
    elif pap.get("reftype"):
        d["confidence"] = "Low" if d["confidence"] == "Low" else "Medium"
        d["note"] = d["note"] + [f"from a registry-listed {pap['reftype']} reference (6.4)"]
    cite = pap.get("title", "")[:120]
    if pap.get("pmid"):
        cite += f" [PMID {pap['pmid']}]"
    if pap.get("year"):
        cite += f" ({pap['year']})"
    d["quote"] = s
    d["cite"] = cite
    return d


# =====================================================================
# 7.1  Posted results
# =====================================================================
def classify_results(outcomes):
    """All primary-outcome analyses non-significant -> Ineffective, Low (7.1)."""
    prim = [o for o in outcomes if (o.get("type", "") or "").upper() == "PRIMARY"]
    vals = []
    for o in prim:
        for a in o.get("p", []):
            raw = (a.get("pValue", "") or "").strip()
            m = re.match(r"^([<>]=?)?\s*([0-9.]+)$", raw)
            if m:
                vals.append((m.group(1) or "=", float(m.group(2)), o.get("title", ""), raw))
    if not vals:
        return None
    sig = [v for v in vals if (v[1] < 0.05 and v[0] in ("=", "<", "<=")) ]
    if sig:
        return None                        # mixed significance is not evidence of failure
    quoted = "; ".join(f'"{t[:60]}" p{op}{raw}' for op, _, t, raw in vals[:4])
    return dict(reason=INEFFECTIVE, confidence="Low", basis="posted results (primary outcomes)",
                sub="all primary analyses non-significant",
                note=["no stop reason or publication statement was on record; every primary-outcome "
                      "analysis posted to the registry was non-significant"],
                quote=quoted, rule="7.1 posted results")
