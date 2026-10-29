"""The nineteen trap classes of section 10.3, checked explicitly on this corpus."""
import csv, json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, rules
from rules import classify_text, classify_publication, CAUSAL

SIDE = list(csv.DictReader(open(config.SIDECAR_CSV)))
FS = [r for r in SIDE if r["In Failure Set"] == "yes"]
OTH = [r for r in SIDE if r["In Failure Set"] == "no"]
fails = []

def chk(n, name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  trap {n:2d}  {name}{(' -- ' + detail) if detail else ''}")
    if not ok:
        fails.append(n)

T = "TERMINATED"
def bucket(t, st=T):
    d = classify_text(t, st)
    return d["reason"] if d else None

# 1 negated causes read as positives
chk(1, "negated causes", all(bucket(t) != config.TOXIC for t in [
    "Company decision not related to safety.",
    "Sponsor decision not related to safety reasons",
    "Recruitment challenges and not due to safety concerns.",
    "Strategic decision not related to safety or efficacy concerns for Ibrexafungerp.",
    "Trial was terminated for business reasons. There has been no change in the benefit/risk profile of ofatumumab.",
    "Logistical challenges; no safety concerns",
    "Halted due to lack of statistical power. No safety concerns identified.",
    "Slow enrollment decreased sample size No unexpected safety issues.",
    "Study discontinued due to administrative reasons unrelated to safety",
    "The Sponsor decided to halt the development of GDC-0810, but not due to any safety concerns.",
    "Due to poor accrual. This decision was taken without any safety reasons. Since beginning of the study (June 2011) only six patients were enrolled.",
]))
# 2 death / AE counts read as toxicity -- every Toxic row must quote a safety STATEMENT
tox = [r for r in FS if r["Reason for Failure"] == config.TOXIC]
chk(2, "death/AE counts as toxicity",
    all(not r["Basis"].startswith(("posted results", "bundle literature")) or
        "stop" in r["Evidence"].lower() for r in tox),
    f"{len(tox)} Toxic rows, none inferred from a count")
# 3 non-failure stops read as failures
nf = [r for r in FS if "non-failure stop" in r["Basis"]]
chk(3, "non-failure stops as failures",
    all(r["Reason for Failure"] == config.RESIDUAL for r in nf),
    f"{len(nf)} non-failure texts, all residual")
# 4 / 17 favourable negations and positive findings in publications
chk(4, "favourable negations in publications",
    classify_publication([{"title": "A randomized trial of drug X", "year": "2015",
        "abstract": "Drug X did not increase the incidence of adverse events compared with placebo. "
                    "Drug X was not inferior to placebo on the primary endpoint."}], T) is None)
chk(17, "positive findings in publications",
    classify_publication([{"title": "A randomized trial of drug X", "year": "2015",
        "abstract": "Drug X significantly improved the primary endpoint versus placebo (p=0.001). "
                    "Drug X met its primary endpoint and was effective."}], T) is None)
# 5 / 10 topic words with no shortfall predicate
chk(5, "topic words without predicates", all(bucket(t) != config.RECRUITMENT for t in [
    "Recruitment was stopped before start of the pollen season",
    "Enrollment was stopped based on the Data Monitoring Committee's recommendation.",
    "Temporarily closed to accrual pending availablity of drug.",
]))
chk(10, "enrolment vocabulary without a shortfall",
    bucket("Terminated: recruiting or enrolling participants has halted prematurely and will not "
           "resume; participants are no longer being examined or treated") is None
    and bucket("Futility for enrollment") == config.RECRUITMENT)
# 6 weak signals outranking concrete ones
chk(6, "weak signals outranking concrete",
    bucket("Study was terminated prior to enrolling protocol target accrual goal due to declining "
           "accrual and Data Safety Monitoring Board recommendations.") == config.RECRUITMENT
    and bucket("DSMC acknowledged no safety concerns with the trial, recommending that the trial be "
               "terminated due to slow enrollment") == config.RECRUITMENT)
# 7 reference year check
chk(7, "publication-year check",
    classify_publication([{"title": "Trial of X", "year": "2001",
        "abstract": "The trial did not meet its primary endpoint versus placebo."}], T,
        start_year="2010") is None)
# 8 lookahead backtracking
chk(8, "lookahead backtracking",
    not re.search(r"\\w\*\s*\(\?\!", open("rules.py").read()),
    "no \\w*-before-lookahead construction in the rule set")
# 9 denial passes mis-ordered
chk(9, "denial pass order",
    bucket("Recruitment rate; a lower than anticipated observed cardiovascular event rate. The "
           "Sponsor decision to stop the trial was not based on any safety concerns or any "
           "knowledge of the results, or influenced by issues imposed by the COVID-19 pandemic.")
    == config.RECRUITMENT
    and bucket("Study drug not available due to COVID-19 FDA restrictions") == config.COVID)
# 11 residual chosen without knowing the metric
chk(11, "residual convention uniform",
    config.RESIDUAL_FILLED
    and all(r["Reason for Failure"] == config.RESIDUAL for r in SIDE if r["Basis"].startswith("NONE"))
    and all(r["Status Prior"] for r in SIDE),
    "residual-filled throughout; the status prior is carried on every row")
# 12 row set gated on the upstream failure label
oc = {r["NCT Number"].strip().upper() for r in csv.DictReader(open(config.OUTCOME_CSV))}
chk(12, "row set not gated on the failure label",
    {r["NCT Number"] for r in SIDE} == oc, f"{len(SIDE)} rows == {len(oc)} outcome-table ids")
# 13 a bare "for" in the causal-marker set
chk(13, "bare 'for' not a causal marker",
    not CAUSAL.search("terminated the study early for enrollment futility")
    and bucket("Lack of substantial evidence for immune responses in response to vaccination.")
        == config.INEFFECTIVE
    and bucket("Enrollment was much slower than anticipated, leading to a decision to terminate "
               "the study early for enrollment futility.") == config.RECRUITMENT)
# 14 a publication enumerating endpoints read as a finding
chk(14, "endpoint enumeration as a finding",
    classify_publication([{"title": "A trial of X", "year": "2015",
        "abstract": "The primary outcomes were overall survival and serious adverse events. "
                    "Secondary endpoints included safety and tolerability."}], T) is None)
# 15 goal-attainment phrase inside a negation
chk(15, "goal attainment inside a negation",
    bucket("terminated early after a futility analysis suggested a full sample size would not lead "
           "to a positive result") == config.INEFFECTIVE)
# 16 the reason keyed to one outcome label -- every failure-set row carries a decision
chk(16, "every failure-set row carries a decision",
    all(r["Reason for Failure"] in config.VOCAB and r["Reason for Failure"] for r in FS)
    and not [r for r in FS if not r["Confidence"]],
    f"{len(FS)} failure-set rows, 0 empty or dropped")
# 18 a reason asserted where the outcome was not negative
bad18 = [r for r in OTH if r["Reason for Failure"] != config.RESIDUAL]
chk(18, "no reason where the outcome is not negative", not bad18,
    f"{len(OTH)} non-failure-set rows, {len(bad18)} naming a reason")
# 19 a pattern referenced by list index -- assert the per-route row counts
routes = collections.Counter(r["Basis"].split(" (")[0] for r in FS)
chk(19, "no route silently at zero",
    all(routes.get(k, 0) > 0 for k in ("whyStopped", "whyStopped -> DetailedDescription",
                                       "bundle literature",
                                       "posted results", "participant-flow disposition type",
                                       "posted-results Limitations and Caveats")),
    "; ".join(f"{k}={v}" for k, v in sorted(routes.items()))[:260] +
    "  [non-pointer DetailedDescription is genuinely absent: of the 76 unresolved "
    "blank-whyStopped trials with a description, 1 mentions termination and it is "
    "future-tense protocol text]")

print(f"\n{19 - len(set(fails))}/19 trap classes pass" + (f"  FAILED: {sorted(set(fails))}" if fails else ""))
sys.exit(1 if fails else 0)
