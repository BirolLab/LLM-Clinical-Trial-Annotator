#!/usr/bin/env python3
"""The S9.3 known-trap table as an executable regression suite.

Every row here produced a confidently wrong call during development, in this
corpus or in the method's reference corpus. Each case asserts the behaviour the
methodology specifies, not merely that something is returned.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import (normalise, sentences, zones, usable, decide_zone, strip_whereas,
                      from_paper, is_substudy, excluded, score_sentence,
                      from_results)

FAILS = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def excl(p):
    """excluded() takes the normalised text as its second argument."""
    return excluded(p, normalise(p["abstract"]))


def paper(title, abstract, **kw):
    d = {"title": title, "abstract": abstract, "pmids": ["1"], "year": "2020",
         "source": "bundle"}
    d.update(kw)
    return d


# 1 -- HTML section markup must not hide the conclusion marker
t = normalise("Background: x. <h4>Results</h4>A rose. <h4>Conclusions</h4>The drug met the primary endpoint.")
check("1 HTML markup -> conclusion marker survives", "Conclusions." in t or "Conclusions" in t, t)
zs = dict(zones(t))
check("1 HTML markup -> conclusion zone is the last section",
      any("met the primary endpoint" in s for s in zs["conclusion"]), zs["conclusion"])

# 1b -- the '<' of a less-than expression is not a tag
t2 = normalise("Primary was TBR [<3.9 mmol/L].<h4>Results</h4>There were no differences.")
check("1b '<3.9 mmol/L' not eaten as a tag", "3.9 mmol/L" in t2, t2)
check("1b heading still split off", len(sentences(t2)) >= 2, sentences(t2))

# 2 -- endpoint-definition sentence is not a result
check("2 endpoint-definition sentence filtered",
      not usable("The primary end points were dose-limiting toxicity and immune response."))
check("2 endpoint sentence with a result verb survives",
      usable("The primary endpoint was not met in the treatment group."))

# 3 -- pooled multi-trial report excluded
check("3 pooled multi-trial report excluded",
      excl(paper("Registrational trials of peptide drugs",
                     "Among 20 FDA-reviewed registrational trials, 10 (50%) failed to meet this "
                     "endpoint, which raises questions about the evidentiary standard applied "
                     "across this class of agents in recent years." * 2)) is not None)

# 4 -- a review of ongoing trials is not a trial report
check("4 review of ongoing trials excluded",
      excl(paper("Peptide vaccines in ongoing clinical trials: status and prospects",
                     "x" * 300)) is not None)

# 5 -- the equivalence no-difference test runs against the sentence, not the hit
r = from_paper(paper("Pharmacokinetic bioequivalence study of insulin glargine",
                     "This randomised, double-blind, two-period crossover trial enrolled 48 healthy "
                     "volunteers to compare the pharmacokinetics of the two products. "
                     "Conclusions. There was no statistically significant difference between the two "
                     "formulations in AUC or Cmax, and the ratios fell within the pre-specified limits."),
              "NCT00000001", {"phase12": False})
check("5 equivalence study: no-difference read as intended result",
      r is not None and r["label"] == "Positive", r)

# 6 -- direction-blind positive
r = decide_zone("conclusion",
                ["Combined ghrelin and Ex9 resulted in greater postprandial glycemia than either alone."],
                {"phase12": False})
check("6 'greater postprandial glycemia' not positive efficacy", r[0] != "Positive", r)

# 6b -- bare stem 'increase' is also direction-checked
r = decide_zone("conclusion",
                ["Treatment produced a clinically significant increase in cardiovascular risk and mortality."],
                {"phase12": False})
check("6b 'significant increase in ... risk' not positive", r[0] != "Positive", r)

# 7 -- safety routing must never fire on a primary-endpoint sentence
r = decide_zone("primary",
                ["There was no significant difference between the two groups in any component of "
                 "the primary outcome or in the rate of death from any cause."],
                {"phase12": False})
check("7 missed primary endpoint not read as tolerability", r[0] != "Positive", r)

# 7b -- genuine safety routing still works away from a primary endpoint
r = decide_zone("conclusion",
                ["Adverse events and hypoglycaemia did not differ significantly between the groups."],
                {"phase12": False})
check("7b safety-subject no-difference reads as tolerated", r[0] == "Positive", r)

# 8 -- biomarker in subject position does not decide a trial
check("8 biomarker-subject sentence filtered",
      not usable("Plasma renin concentrations showed no significant change during treatment."))

# 9 -- a negated family is relabelled, not merely sign-flipped
r = decide_zone("conclusion",
                ["Treatment was associated with no apparent increased risk of hypoglycaemic episodes."],
                {"phase12": False})
check("9 negated hit relabelled to a positive family",
      r[0] == "Positive" and r[1]["family"].startswith("positive"), r)

# 9b -- a negated increase-verb over a bad object is not an endpoint failure
r = decide_zone("conclusion",
                ["The early introduction of everolimus did not increase the risk of wound-healing "
                 "complications, showing a good efficacy and safety profile."],
                {"phase12": False})
check("9b 'did not increase the risk of complications' not Negative", r[0] != "Negative", r)

# 9c -- but a negated reduce-verb over a bad object IS a failure
r = decide_zone("conclusion",
                ["Intensive glucose control did not significantly reduce perioperative complications "
                 "compared with conservative control."],
                {"phase12": False})
check("9c 'did not reduce complications' stays Negative", r[0] == "Negative", r)

# 10 -- generic no-difference wording alone cannot fail a trial (S5.7)
r = decide_zone("conclusion", ["The two groups did not differ in mean body weight at week 12."],
                {"phase12": False})
check("10 generic no-difference alone does not produce Negative", r[0] != "Negative", r)

# 11 -- benign discontinuation wording is not a halted trial
r = decide_zone("conclusion",
                ["Twelve patients discontinued treatment because of adverse events during follow-up."],
                {"phase12": False})
check("11 patient-level discontinuation not an endpoint failure",
      not (r[0] == "Negative" and r[1]["family"] == "negative-endpoint"), r)

# 12 -- a sub-study may support Positive but never fail a trial
sp = paper("Effects of dulaglutide on plasma renin as a probe of the renin-angiotensin system",
           "Twelve healthy volunteers received dulaglutide in this mechanistic study. "
           "Conclusions. Dulaglutide showed no effect on plasma renin activity and did not "
           "significantly reduce aldosterone concentrations over the study period.")
check("12 sub-study flagged", is_substudy(sp, normalise(sp["abstract"])))
r = from_paper(sp, "NCT00000002", {"phase12": False})
check("12 sub-study never produces Negative", r is None or r["label"] != "Negative", r)

# 12b -- meta-analysis excluded outright
check("12b meta-analysis excluded",
      excl(paper("Efficacy of GLP-1 agonists: a systematic review and meta-analysis",
                     "x" * 300)) is not None)

# 13 -- conditional protocol clause (real abstract, PMID 28967549 / NCT00809172).
# The splitter will not break after "at week 8." so the escalation rule is absorbed
# into the endpoint-definition sentence; its "achieved" must not redeem it.
_s13 = ("The primary end point was a patient achieving 50% improvement in the SCORing "
        "Atopic Dermatitis index (SCORAD 50) at week 8. When the primary end point was "
        "not achieved, methotrexate was increased to 25 mg and cyclosporine to 5 mg "
        "during the next 16 weeks.")
check("13 conditional protocol clause not a result", not usable(_s13), _s13[:60])
check("13b a real endpoint result still survives",
      usable("The primary end point was not achieved in the saxagliptin group (P=0.38)."))
check("13c conditional clause contributes no polarity",
      "not achieved" not in strip_whereas(_s13))

# 14 -- chronology: a paper published before the trial started cannot report it.
_p14 = paper("Alterations in glutathione levels in Parkinson disease",
             "GSH in the substantia nigra was significantly reduced only in Parkinson "
             "disease. This randomized double-blind placebo-controlled study enrolled "
             "patients and assessed the primary endpoint at week 12. " + "x" * 150)
_p14["year"] = "1992"
check("14 pre-start paper cannot decide",
      from_paper(_p14, "NCT00000003", {"phase12": False, "start_year": "2015"}) is None)
check("14b same-year paper still allowed",
      from_paper(_p14, "NCT00000003", {"phase12": False, "start_year": "1992"}) is not None)
check("14c missing start year does not block",
      from_paper(_p14, "NCT00000003", {"phase12": False, "start_year": ""}) is not None)

# 15 -- a pooled multi-trial analysis is excluded on phrasing, not on NCT count
_p15 = paper("BeAM value: an indicator of the need to intensify prandial therapy.",
             "Introduction The point at which basal insulin is optimized remains unclear. "
             "Methods For the exploratory and main analyses, data were pooled from phase 3 "
             "trials in adults with T2DM adding basal insulin to oral antidiabetic drugs. "
             "The main analysis included only patients who did not reach A1C 7.0% at week 24. "
             "Results BeAM value increased over 24 weeks. " + "x" * 150)
check("15 pooled-from-trials phrasing excludes the paper", bool(excl(_p15)), excl(_p15))
check("15b pooled paper cannot decide a trial",
      from_paper(_p15, "NCT00000015", {"phase12": False, "start_year": "2005"}) is None)
_p15b = paper("A randomized trial of drug X.",
              "Methods Patients were randomized. Results Data from both treatment arms were "
              "pooled for the safety analysis. Conclusions Drug X met the primary endpoint. "
              + "x" * 150)
check("15c within-trial arm pooling is NOT excluded", not excl(_p15b), excl(_p15b))

# 16 -- superiority is not the goal of a non-inferiority trial
_s16 = ("Clinical response at end of treatment was non-inferior to vancomycin. "
        "Sustained clinical response did not demonstrate superiority versus vancomycin "
        "at end of trial.")
_z16 = [x for x in sentences(normalise(_s16))]
_lab16, _hit16, _ = decide_zone("conclusion", _z16, {"phase12": False, "ni_met": True})
check("16 met non-inferiority is not failed by a superiority test",
      _lab16 != "Negative", f"{_lab16} / {_hit16['frag'] if _hit16 else None}")
# isolated so the check is about the guard, not about two 3.0 hits cancelling out
_s16b = [x for x in sentences(normalise(
    "Sustained clinical response did not demonstrate superiority versus vancomycin."))]
check("16b without a met-NI statement the superiority miss still counts",
      decide_zone("conclusion", _s16b, {"phase12": False, "ni_met": False})[0] == "Negative",
      decide_zone("conclusion", _s16b, {"phase12": False, "ni_met": False})[0])
check("16b2 the same sentence is dropped once non-inferiority was met",
      decide_zone("conclusion", _s16b, {"phase12": False, "ni_met": True})[0] is None,
      decide_zone("conclusion", _s16b, {"phase12": False, "ni_met": True})[0])
_s16c = [x for x in sentences(normalise(
    "Drug A did not meet the primary endpoint of overall survival."))]
_lab16c, _, _ = decide_zone("conclusion", _s16c, {"phase12": False, "ni_met": True})
check("16c a real endpoint miss survives the NI guard", _lab16c == "Negative", _lab16c)

# 17 -- the equivalence re-reading reaches the primary-endpoint sentence
_s17 = [x for x in sentences(normalise(
    "The area under the curve adjusted for body weight was found to be equivalent in young "
    "and elderly subjects (primary end point), with an estimated ratio of 0.94 "
    "(90% confidence interval, 0.84-1.06; P = .39)."))]
_lab17, _hit17, _ = decide_zone("primary", _s17, {"phase12": False, "equiv": True})
check("17 PK equivalence on the primary endpoint reads Positive",
      _lab17 == "Positive", f"{_lab17} / {_hit17['frag'] if _hit17 else None}")
_s17b = [x for x in sentences(normalise(
    "The primary endpoint of non-inferiority was not met, with a difference of 4.1% "
    "(95% CI 1.2-7.0) exceeding the pre-specified margin."))]
_lab17b, _, _ = decide_zone("primary", _s17b, {"phase12": False, "equiv": True})
check("17b a missed non-inferiority goal is not re-read as Positive",
      _lab17b != "Positive", _lab17b)

# 18 -- a harm-rate primary endpoint carried by generic no-difference wording
_s18 = [x for x in sentences(normalise(
    "No difference was observed for percentage of time <4.0 mmol/L over a 4-hour post-meal "
    "period (primary outcome; median 0 vs 0 for both comparisons, p = 0.47)."))]
_lab18, _, _ = decide_zone("primary", _s18, {"phase12": False})
check("18 harm-rate primary with no difference is not a failed trial",
      _lab18 != "Negative", _lab18)
_s18b = [x for x in sentences(normalise(
    "There was no significant difference between the two groups in any component of the "
    "primary outcome or in the rate of death from any cause."))]
_lab18b, _, _ = decide_zone("primary", _s18b, {"phase12": False})
check("18b the component-of-primary-outcome trap still reads Negative",
      _lab18b == "Negative", _lab18b)

# 19 -- a missed SECONDARY measure must not fail a trial whose primary was met
_s19 = [x for x in sentences(normalise(
    "In patients with type 1 diabetes, the combination was safe and produced significant "
    "weight loss but did not significantly improve metabolic and blood pressure control."))]
_lab19, _, _ = decide_zone("conclusion", _s19, {"phase12": False})
check("19 missed secondary measures do not fail a met primary",
      _lab19 != "Negative", _lab19)
_s19b = [x for x in sentences(normalise(
    "The drug was well tolerated but did not significantly improve overall survival."))]
_lab19b, _, _ = decide_zone("conclusion", _s19b, {"phase12": False})
check("19b a missed clinical endpoint in a but-clause still fails the trial",
      _lab19b == "Negative", _lab19b)
_s19c = [x for x in sentences(normalise(
    "The primary endpoint of change in systolic blood pressure was not met (p = 0.42), "
    "although the drug was well tolerated."))]
_lab19c, _, _ = decide_zone("primary", _s19c, {"phase12": False})
check("19c a blood-pressure PRIMARY endpoint miss still fails the trial",
      _lab19c == "Negative", _lab19c)

# 20 -- a p-value's polarity is numeric: a nearby negation must not flip it
_s20 = [x for x in sentences(normalise(
    "The primary endpoint of change in systolic blood pressure was not met (p = 0.42)."))]
_h20 = [h for x in _s20 for h in score_sentence(x, {"phase12": False})]
check("20 a non-significant p-value is not flipped positive by a nearby negation",
      not any(h["family"].startswith("positive") and "0.4" in h["frag"] for h in _h20),
      [(h["family"], h["frag"]) for h in _h20])
_s20b = [x for x in sentences(normalise(
    "The difference was not significant between arms (p = 0.42) for the secondary measure."))]
check("20b the same exemption holds outside a primary sentence",
      not any(h["family"].startswith("positive")
              for x in _s20b for h in score_sentence(x, {"phase12": False})),
      [(h["family"], h["frag"]) for x in _s20b for h in score_sentence(x, {"phase12": False})])

# 21 -- the measure name between "endpoint" and its verb must not hide the miss
_h21 = [h for x in _s20 for h in score_sentence(x, {"phase12": False})]
check("21 'endpoint of <measure> was not met' is a negative-endpoint hit",
      any(h["family"] == "negative-endpoint" for h in _h21),
      [(h["family"], h["frag"]) for h in _h21])

# 22 -- a low AE rate alone cannot carry a Positive when the primary is also efficacy
from classify import from_results
_d22 = {"outcomes": [{"type": "PRIMARY", "pvalues": [],
                      "title": "Mean Change From Baseline in C-peptide Area Under the Curve (AUC)"}],
        "ae_groups": [{"title": "A", "ser": 3, "ser_at": 67, "dead": 0, "dead_at": 67}]}
check("22 low AE rate does not make an efficacy primary Positive",
      from_results(_d22, True) is None, from_results(_d22, True))
_d22b = {"outcomes": [{"type": "PRIMARY", "pvalues": [],
                       "title": "Number of Participants With Dose-limiting Toxicities"}],
         "ae_groups": [{"title": "A", "ser": 3, "ser_at": 67, "dead": 0, "dead_at": 67}]}
check("22b a true safety primary still reads Positive on a low AE rate",
      (from_results(_d22b, True) or {}).get("label") == "Positive", from_results(_d22b, True))
_d22c = {"outcomes": [{"type": "PRIMARY", "pvalues": [],
                       "title": "Percentage of Participants With Adverse Events; Overall Survival Rate"}],
         "ae_groups": [{"title": "A", "ser": 40, "ser_at": 60, "dead": 2, "dead_at": 60}]}
check("22c a high AE rate still reads Negative -- not tolerated is sufficient",
      (from_results(_d22c, True) or {}).get("label") == "Negative", from_results(_d22c, True))

# 23 -- a patient-disposition / eligibility clause is not an endpoint miss
_s23 = [x for x in sentences(normalise(
    "There were 298 patients who did not meet the randomization criteria."))]
check("23 eligibility clause yields no negative-endpoint hit",
      not any(h["family"] == "negative-endpoint"
              for x in _s23 for h in score_sentence(x, {"phase12": False})),
      [(h["family"], h["frag"]) for x in _s23 for h in score_sentence(x, {"phase12": False})])
_s23b = [x for x in sentences(normalise(
    "Of 410 women, 33 (8.1%) did not meet the inclusion criteria and were excluded."))]
check("23b a count-subject eligibility clause also yields none",
      not any(h["family"] == "negative-endpoint"
              for x in _s23b for h in score_sentence(x, {"phase12": False})),
      [(h["family"], h["frag"]) for x in _s23b for h in score_sentence(x, {"phase12": False})])
_s23c = [x for x in sentences(normalise(
    "Patients who achieved a remission had a peak CAR level of 98/uL and those who "
    "did not achieve a remission had a median peak blood CAR level of 12/uL."))]
check("23c a responder/non-responder clause does not fail the trial",
      not any(h["family"] == "negative-endpoint"
              for x in _s23c for h in score_sentence(x, {"phase12": False})),
      [(h["family"], h["frag"]) for x in _s23c for h in score_sentence(x, {"phase12": False})])
_s23d = [x for x in sentences(normalise(
    "The primary endpoint was not met at week 24."))]
check("23d a real endpoint miss still survives the disposition guard",
      any(h["family"] == "negative-endpoint"
          for x in _s23d for h in score_sentence(x, {"phase12": False})),
      [(h["family"], h["frag"]) for x in _s23d for h in score_sentence(x, {"phase12": False})])

# 24 -- "safe but not effective" must not read Positive off its safety half
_s24 = [x for x in sentences(normalise(
    "Conclusions Canakinumab and anakinra were safe but were not effective as single "
    "immunotherapy for recent-onset type 1 diabetes."))]
_h24 = [h for x in _s24 for h in score_sentence(x, {"phase12": False})]
check("24 an explicit non-efficacy verdict is an endpoint-family hit",
      any(h["family"] == "negative-endpoint" for h in _h24),
      [(h["family"], h["frag"]) for h in _h24])
check("24b and it outweighs the positive-safety half of the same sentence",
      sum(h["w"] for h in _h24 if h["family"].startswith("negative"))
      > sum(h["w"] for h in _h24 if h["family"].startswith("positive")),
      [(h["family"], h["w"], h["frag"]) for h in _h24])
# the endpoint families are deliberately outside the S5.6.3 phase rescale, so the
# verdict still carries in a phase-1 trial; a bare tolerability statement does not
# acquire a failure from this pattern.
_s24c = [x for x in sentences(normalise(
    "Conclusions The vaccine was safe and well tolerated at all dose levels."))]
_h24c = [h for x in _s24c for h in score_sentence(x, {"phase12": True})]
check("24c a bare phase-1 tolerability statement still reads positive",
      _h24c and all(h["family"].startswith("positive") for h in _h24c),
      [(h["family"], h["w"], h["frag"]) for h in _h24c])

# 25 -- a retrospective analysis of trial cohorts is not a trial report (S5.2)
_t25 = {"title": "Treatment and outcome of Ganglioneuroma and Ganglioneuroblastoma intermixed."}
_x25 = normalise(
    "Methods Clinical characteristics and outcome of localized GN/GNBI were "
    "retrospectively compared to localized neuroblastoma registered in the German "
    "neuroblastoma trials between 2000 and 2010. Conclusions Chemotherapy is not "
    "effective. Subtotal resection appears to be a sufficient treatment.")
check("25 retrospective design excludes the paper",
      excluded(_t25, _x25) is not None, excluded(_t25, _x25))
_t25b = {"title": "Daptomycin versus ceftriaxone for community-acquired pneumonia: a phase 3 trial"}
_x25b = normalise(
    "Methods Two phase-3 randomized, double-blind trials enrolled adult patients "
    "hospitalized with CAP. Conclusions Daptomycin is not effective for the treatment "
    "of community-acquired pneumonia.")
check("25b a prospective trial report is not excluded by it",
      excluded(_t25b, _x25b) is None, excluded(_t25b, _x25b))

# 26 -- a trial-conduct paper is not a trial-outcome paper (S5.2)
_t26 = {"title": "A Novel Framework Using Remote Telesimulation With Standardized Parents "
                 "to Improve Research Staff Preparedness for Informed Consent"}
_x26 = normalise("Conclusions Titration study consent rates did not improve, suggesting "
                 "that other factors influence parental decisions in this setting.")
check("26 a trial-conduct paper is excluded",
      excluded(_t26, _x26) is not None, excluded(_t26, _x26))
_t26b = {"title": "Initial Vancomycin Taper for the Prevention of Recurrent Clostridioides "
                  "difficile Infection: A Randomized Clinical Trial"}
_x26b = normalise("Methods Adults with recurrent C difficile infection were randomised to a "
                  "vancomycin taper or standard course in a double-blind trial. Results The "
                  "trial was stopped early due to feasibility of recruitment. Conclusions The "
                  "taper did not reduce recurrence of infection at 8 weeks.")
check("26b an early-stop trial report is not caught by it",
      excluded(_t26b, _x26b) is None, excluded(_t26b, _x26b))

# 27 -- transatlantic spellings must BOTH match. "hypoglyc[ae]emia" matched only
# the British form, so the commoner American one was invisible to every vocabulary
# that listed it -- a silent death of exactly the S9.1 kind, and invisible to the
# pattern audit because it sits inside an alternation that still had a high count.
import patterns as _P
_PAIRS = [("hypoglycemia", "hypoglycaemia"), ("hyperglycemia", "hyperglycaemia"),
          ("anemia", "anaemia"), ("diarrhea", "diarrhoea"),
          ("hypoglycemic", "hypoglycaemic")]
_vocabs = [("WORSE_OBJ", _P.WORSE_OBJ), ("SAFETY_SUBJ", _P.SAFETY_SUBJ)]
_bad = []
for name, rx in _vocabs:
    for us, uk in _PAIRS:
        a = bool(rx.search("the incidence of " + us))
        b = bool(rx.search("the incidence of " + uk))
        if a != b:
            _bad.append(f"{name}: {us}={a} {uk}={b}")
check("27 spelling classes match both forms in every vocabulary", not _bad, _bad)

# 27b the sentence that exposed it: a no-increase-in-harm finding is not a failure
_s27 = [x for x in sentences(normalise(
    "Conclusion Overall, weekly efsitora did not increase the incidence, duration, or "
    "severity of hypoglycemia compared to daily glargine during provocation periods in "
    "patients with type 2 diabetes."))]
_h27 = [h for x in _s27 for h in score_sentence(x, {"phase12": False})]
check("27b 'did not increase the incidence ... of hypoglycemia' is not an endpoint miss",
      not any(h["family"] == "negative-endpoint" for h in _h27),
      [(h["family"], h["frag"]) for h in _h27])
check("27c and the British spelling behaves identically",
      not any(h["family"] == "negative-endpoint"
              for x in sentences(normalise(
                  "Conclusion Overall, weekly efsitora did not increase the incidence, "
                  "duration, or severity of hypoglycaemia compared to daily glargine "
                  "during provocation periods in patients with type 2 diabetes."))
              for h in score_sentence(x, {"phase12": False})))

# 27d an object list must not be truncated at its first comma (object_window)
from classify import object_window, worse_object
_w27 = object_window("efsitora did not increase the incidence, duration, or severity of "
                     "hypoglycemia compared to glargine.", len("efsitora did not increase"))
check("27d the object window spans a coordinated list", worse_object(_w27), _w27)
_w27b = object_window("did not increase the risk of wound-healing complications, showing a "
                      "good efficacy and safety profile.", len("did not increase"))
check("27e but still stops at a real clause boundary",
      worse_object(_w27b) and "efficacy" not in _w27b, _w27b)

# 28 -- a device-performance paper measures the instrument, not the trial (S5.2)
_t28 = {"title": "System Accuracy Assessment of a Blood Glucose Meter With Wireless "
                 "Internet Access Associated With Unusual Hypoglycemia Patterns"}
_x28 = normalise("Conclusions Evaluated against standard regulatory guidelines, the meter "
                 "did not meet the level of analytical accuracy required for use in the "
                 "management of insulin-treated diabetes in a clinical trial setting.")
check("28 a device-accuracy paper is excluded", excluded(_t28, _x28) is not None,
      excluded(_t28, _x28))

# 29 -- a responder count is not the trial meeting its endpoint
for _txt, _name in [
        ("Results Three subjects (30%) achieved the primary endpoint at week 24 in this "
         "open-label proof-of-concept study of abatacept in IgG4-related disease.",
         "29 'three subjects (30%) achieved the primary endpoint' is not a met endpoint"),
        ("Results Two of six patients achieved the primary outcome of complete response "
         "in this pilot open-label study of anakinra in Behcet's disease.",
         "29b 'two of six patients achieved the primary outcome' likewise"),
        ("Results Overall 27.5 and 25.6% of patients reached the primary outcome with "
         "glargine and detemir respectively in this randomised comparison.",
         "29c a percentage-of-patients subject likewise")]:
    _h29 = [h for x in sentences(normalise(_txt))
            for h in score_sentence(x, {"phase12": False})]
    check(_name, not any(h["family"] == "positive-endpoint" for h in _h29),
          [(h["family"], h["frag"]) for h in _h29])
_h29d = [h for x in sentences(normalise(
    "Results The study met its primary endpoint, with a response in 85% of the 120 "
    "patients randomised to the active arm.")) for h in score_sentence(x, {"phase12": False})]
check("29d a real met-endpoint statement is untouched",
      any(h["family"] == "positive-endpoint" for h in _h29d),
      [(h["family"], h["frag"]) for h in _h29d])

# ---- 30: an association / prediction paper never fails a trial (S5.8)
_p30 = {"title": "Epigenetic age acceleration is not strongly associated with "
                 "cardiorespiratory fitness in heart failure: a pilot study",
        "abstract": "Background In heart failure, standard measures incompletely capture "
                    "interindividual differences. Methods We analyzed peripheral blood DNA "
                    "methylation from fourteen patients enrolled in REDHART2, a clinical trial "
                    "of interleukin-1 blockade following hospitalization for acute systolic "
                    "heart failure. Results All epigenetic clocks demonstrated moderate to "
                    "strong correlations with chronological age. However, chronological age "
                    "showed similar associations, and biological age did not significantly "
                    "improve prediction of VO2 parameters beyond chronological age alone. "
                    "Conclusions In this pilot study, neither biological age nor epigenetic "
                    "age acceleration provided significant predictive value."}
check("30 an association/prediction paper is a sub-study",
      is_substudy(_p30, normalise(_p30["abstract"])))
_r30 = from_paper(_p30, "NCT03797001", {"phase12": False, "start_year": "2019"})
check("30b and so cannot produce a failure call",
      _r30 is None or _r30["label"] != "Negative", _r30 and _r30["label"])
_p30c = {"title": "Efficacy and safety of semaglutide in a randomised placebo-controlled "
                  "phase 3 trial: association with baseline HbA1c",
         "abstract": _p30["abstract"]}
check("30c but a titled randomised efficacy report is not gated away",
      not is_substudy(_p30c, normalise(_p30c["abstract"])))

# ---- 31: S6 -- a harm-measure primary cannot be made Positive by a bare p-value
_d31 = {"outcomes": [{"type": "PRIMARY", "title": "Proportion of Patients With Nephrotoxicity",
                      "pvalues": [{"p": "0.0002"}]}],
        "ae_groups": [{"ser": 87, "ser_at": 205, "dead": 60}]}
_l31 = (from_results(_d31, False) or {}).get("label")
check("31 a significant nephrotoxicity primary is not read as Positive",
      _l31 != "Positive", _l31)
_d31b = {"outcomes": [{"type": "PRIMARY", "title": "Change in HbA1c From Baseline",
                       "pvalues": [{"p": "0.0002"}]}],
         "ae_groups": [{"ser": 2, "ser_at": 205, "dead": 0}]}
check("31b an efficacy primary with a significant p-value still reads Positive",
      (from_results(_d31b, False) or {}).get("label") == "Positive",
      from_results(_d31b, False))

# ---- 32: S9.2 round 1 on this corpus -- a futility ANALYSIS is not a futility stop
def _neg(sent, **ctx):
    """True when the sentence yields any negative polarity at all."""
    c = {"phase12": False}
    c.update(ctx)
    return any(h["family"].startswith("negative") for h in score_sentence(sent, c))

check("32 a benign futility analysis is not a negative signal",
      not _neg("A planned futility analysis demonstrated a low rate of IFD."))
check("32b a real futility stop still is",
      _neg("The study was closed early owing to futility."))
check("32c and so is a crossed futility boundary",
      _neg("Enrolment proceeded until the prespecified futility boundary was crossed."))

# ---- 33: an administrative stop reported in a paper is not an endpoint failure
check("33 an accrual stop is not an endpoint failure",
      not _neg("However, enrollment was stopped owing to very slow patient accrual, "
               "and the study was underpowered."))
check("33b nor is a trial stopped for recruitment feasibility",
      not _neg("The trial was stopped early due to feasibility of recruitment."))
check("33c nor one terminated for poor accrual",
      not _neg("This study was terminated early because of poor accrual."))
check("33d but a stop for safety still fails the trial",
      _neg("The trial was stopped early for safety reasons."))
check("33e and so does a stop for excess toxicity",
      _neg("The study was stopped early because of excess toxicity."))
check("33f and an arm stopped for futility is untouched",
      _neg("Enrollment in the 40-unit group was stopped for futility."))
check("33g a futility analysis triggered BY slow accrual is not substantive",
      not _neg("A futility analysis was performed because of slow accrual."))
check("33h an interim stop with no administrative reason still fails",
      _neg("The trial was stopped at a preplanned interim analysis after enrollment "
           "of 31 participants."))

# ---- 34: a p-value that states the test's own threshold is a methods statement
check("34 an alpha level is not a non-significant result",
      not _neg("Relapse rate was compared with a significance level of p=0.10."))
check("34b nor is an FDR threshold",
      not _neg("Group differences were assessed with the false discovery rate "
               "corrected at P = 0.05."))
check("34c a real non-significant result p-value still scores",
      _neg("The primary outcome did not differ between groups (P = 0.63)."))

# ---- 35: a statistical artefact is not an endpoint
check("35 'failed to show a center effect' is not a failure",
      not _neg('The statistical analyses failed to show a "center effect".'))
check("35b a real 'failed to show' on efficacy still is",
      _neg("The trial failed to show a significant benefit of the drug on the "
           "primary endpoint."))

# ---- 36: somebody else's trial is not this trial
check("36 'other studies failed to show' contributes nothing",
      not _neg("Other studies failed to show significant benefits with the addition "
               "of this agent."))
check("36b a numbered other study likewise",
      not _neg("Although study 303 failed to demonstrate equivalence, the combined "
               "analysis was supportive."))
check("36c but this trial's own miss survives",
      _neg("This trial failed to show a significant benefit on the primary endpoint."))
check("36d and a leading concessive clause is not dropped wholesale",
      _neg("Although our primary outcome was not statistically significant, the "
           "tested approach remains of interest."))

# ---- 37: eligibility phrased as "patients who failed"
check("37 'patients who failed to achieve target' is the population",
      not _neg("Intensification regimens were studied in patients who failed to "
               "achieve target HbA1c during 26-week basal insulin treatment."))
check("37b and an entry criterion phrased as a reason likewise",
      not _neg("Patients were switched from apremilast because of either failure to "
               "achieve or loss of adequate clinical response."))

# ---- 38: a negated increase in a harm is tolerability, not an endpoint miss
check("38 'did not increase rectal or urinary dysfunction' is not a failure",
      not _neg("Increasing the EBRT dose did not increase rectal or urinary "
               "dysfunction in this trial."))
check("38b an abbreviated AE subject is a safety subject",
      not _neg("SAEs (0.12 per patient-year) did not increase with long-term "
               "exposure to etanercept."))
check("38c a vital-sign subject sentence is filtered",
      not usable("Heart rate did not increase (-0.3 beats/minute) during treatment."))
check("38d an insulin-resistance index likewise",
      not usable("HOMA-IR did not increase or differ between groups."))
check("38e but a negated increase in a GOOD outcome still fails the trial",
      _neg("Vasopressin did not significantly increase the likelihood of return of "
           "spontaneous circulation."))
check("38f and so does a negated increase in survival",
      _neg("Prophylactic rG-CSF did not significantly increase survival free of "
           "infection at 4 weeks."))

# ---- 39: a prognostic-factor or competing-risks analysis is excluded with the
# secondary analyses it belongs to (S5.2)
check("39 a prognostic-factor analysis is excluded",
      excl(paper("Analysis of prognostic factors of acute lymphoblastic leukemia in "
                 "infants: report on CCG 1953 from the Children's Oncology Group",
                 "Infants with ALL were enrolled in a randomised phase 3 trial. "
                 "Among the 3 major MLL rearrangements the difference did not reach "
                 "statistical significance in this analysis of event-free survival." * 2))
      is not None)
check("39b a competing-risks analysis likewise",
      excl(paper("Competing risks of death in younger and older postmenopausal breast "
                 "cancer patients",
                 "Patients randomised in this trial had similar event-free survival "
                 "(P = 0.62) when competing risks of death were accounted for." * 3))
      is not None)
check("39c but the trial's own randomised report is not excluded",
      excl(paper("A randomised phase 3 trial of drug X versus placebo in infants with ALL",
                 "Infants were randomised to drug X or placebo in this double-blind "
                 "placebo-controlled trial. The primary endpoint of event-free "
                 "survival was not met (P = 0.62)." * 2)) is None)

# ---- 40: S9.2 round 2 -- a physiology probe is a S5.8 condition-1 sub-study whatever
# the population, and a surrogate-endpoint validation is an association paper
_p40 = paper("Effects of insulin analogs as an add-on to metformin on cutaneous "
             "microcirculation in type 2 diabetic patients",
             "Capillary blood flow was measured at two visits in randomised patients. "
             "Compared to V1, CBF at fasting did not increase at V2 but there was an "
             "improvement in endothelial-dependent vasodilation." * 2)
check("40 a microcirculation probe is a sub-study in patients",
      is_substudy(_p40, normalise(_p40["abstract"])))
_p40b = paper("Posttreatment prostatic-specific antigen doubling time as a surrogate "
              "endpoint for prostate cancer-specific survival",
              "PSA doubling time was significantly associated with CSS, but did not meet "
              "the prespecified criteria for surrogacy in this randomised trial cohort." * 2)
check("40b a surrogate-endpoint validation is a sub-study",
      is_substudy(_p40b, normalise(_p40b["abstract"])))
check("40c and so cannot produce a failure call",
      (from_paper(_p40b, "NCT00767286", {"phase12": False, "start_year": "2004"}) or {})
      .get("label") != "Negative")

# ---- 41: S9.2 round 2 -- "did not SHOW an efficacy signal" is the same verdict as
# "did not demonstrate efficacy", but only the latter was in the vocabulary, so a
# conclusion reading "was safe but did not show an efficacy signal" scored as a clean
# positive-safety call with no negative weight at all.
check("41 'did not show an efficacy signal' is a negative-endpoint hit",
      any(h["family"] == "negative-endpoint" for h in score_sentence(
          "The addition of UV1 to pembrolizumab was safe but did not show an "
          "efficacy signal in this cohort.", {"phase12": False})))
check("41b and 'did not demonstrate efficacy' still is",
      any(h["family"] == "negative-endpoint" for h in score_sentence(
          "The drug did not demonstrate efficacy on the primary measure.",
          {"phase12": False})))

# ---- 42: S9.1 -- the four patterns the corpus audit scores at ZERO. A zero means a
# broken regex until proved otherwise, so each is asserted against the phrasing it
# targets here; that is what distinguishes "absent from this corpus" from "inert".
_ZEROS = [
    (r"(?:declared|deemed) futile",
     ["the trial was declared futile at the interim analysis",
      "the study was deemed futile"]),
    (r"(?:met|meeting) (?:the )?(?:pre[-\s]?specified |prespecified )?criteri\w+ for futility",
     ["the trial met the prespecified criteria for futility",
      "the study met criteria for futility"]),
    (r"crossed the (?:pre[-\s]?specified |prespecified )?futility (?:boundary|threshold)",
     ["the trial crossed the prespecified futility boundary",
      "the analysis crossed the futility threshold"]),
    (r"(?:primary|co-primary)[^.]{0,40}(?:reached|achieved|attained|met) (?:statistical )?significance",
     ["the primary endpoint reached statistical significance",
      "the co-primary outcome achieved significance"]),
]
import re as _re
for _pat, _tests in _ZEROS:
    _rx = _re.compile(_pat, _re.I)
    check(f"42 zero-count pattern still fires: {_pat[:46]}",
          all(_rx.search(t) for t in _tests))
_fams = {p for pats in __import__("patterns").FAMILIES.values() for p in pats}
check("42b every zero-count pattern is still present in a family",
      all(p in _fams for p, _ in _ZEROS),
      [p for p, _ in _ZEROS if p not in _fams])

print()
if FAILS:
    print(f"{len(FAILS)} TRAP CHECK(S) FAILED: " + ", ".join(FAILS))
    sys.exit(1)
print("all trap checks pass")
