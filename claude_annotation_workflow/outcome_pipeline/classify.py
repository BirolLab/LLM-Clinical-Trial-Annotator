#!/usr/bin/env python3
"""Normalise -> relevance gate -> zone order -> polarity -> label (methodology S4-S8).

Offline and fast: no network call anywhere below. Writes work/calls.json
(one record per trial, with the decision source) and work/unresolved.json.
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patterns as P

WORK = os.environ.get("OUTCOME_WORK", "outcome_pipeline/work")
OFF = set(filter(None, os.environ.get("OUTCOME_OFF", "").split(",")))
ON = set(filter(None, os.environ.get("OUTCOME_ON", "").split(",")))

STOPPED = {"TERMINATED", "SUSPENDED", "WITHDRAWN"}
ACTIVE = {"RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING",
          "ENROLLING_BY_INVITATION", "AVAILABLE"}
UNDECIDED = {"COMPLETED", "UNKNOWN"}

# S1: the registry-stop labels are emitted verbatim, so a stopped trial carries its
# own stop kind rather than a collapsed one. FAILED is the reported-failure label; the
# polarity machinery below keeps using the internal token "Negative" and is translated
# to FAILED at the one boundary in classify_one().
FAILED = "Failed - completed trial"

STATUS_LABEL = {"TERMINATED": "Terminated", "SUSPENDED": "Suspended",
                "WITHDRAWN": "Withdrawn", "RECRUITING": "Recruiting",
                "NOT_YET_RECRUITING": "Not yet recruiting",
                "ACTIVE_NOT_RECRUITING": "Active, not recruiting",
                "ENROLLING_BY_INVITATION": "Enrolling by invitation",
                "COMPLETED": "Completed", "UNKNOWN": "Unknown status",
                "AVAILABLE": "Available"}


# ------------------------------------------------------------------ S5.1 normalise
def normalise(text):
    """HTML section headings become sentence leads; remaining tags stripped.

    Left in place, <h4>Conclusions</h4> hides the conclusion marker and breaks
    sentence splitting (S9.3 trap 1).
    """
    t = text or ""
    t = re.sub(r"<\s*/?\s*(?:h[1-6]|p|br|div)\s*/?\s*>", " § ", t, flags=re.I)
    # require a tag-like opener: a bare "<" in "TBR [<3.9 mmol/L]" is a
    # less-than sign, and eating up to the next ">" welds the following
    # section heading into the sentence (a variant of S9.3 trap 1).
    t = re.sub(r"</?[A-Za-z][^>]{0,200}>", " ", t)
    t = (t.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
          .replace("&nbsp;", " ").replace("&#x2009;", " ").replace("&quot;", '"'))
    # '§ Results §' -> 'Results. '
    t = re.sub(r"§\s*(Background|Objectives?|Aims?|Methods?|Results?|Findings?|"
               r"Conclusions?|Interpretation|Discussion|Summary|Purpose|Design|"
               r"Patients and Methods|Materials and Methods|Trial Registration)\s*:?\s*§",
               r" \1. ", t, flags=re.I)
    t = re.sub(r"§\s*(Background|Objectives?|Aims?|Methods?|Results?|Findings?|"
               r"Conclusions?|Interpretation|Discussion|Summary)\s*:?\s*",
               r" \1. ", t, flags=re.I)
    t = t.replace("§", " ")
    return re.sub(r"\s+", " ", t).strip()


ABBR = re.compile(r"\b(?:Dr|Mr|Mrs|Ms|Prof|vs|e\.g|i\.e|cf|approx|et al|No|Fig|"
                  r"St|Inc|Ltd|Co|mg|kg|mL|µg|ug|i\.v|s\.c|p\.o|b\.i\.d|q\.d)\.$", re.I)


def sentences(text):
    parts, cur = [], []
    for tok in re.split(r"(?<=[.!?])\s+", text):
        cur.append(tok)
        joined = " ".join(cur)
        # don't split on an abbreviation or a decimal that ends the fragment
        if ABBR.search(tok.strip()) or re.search(r"\b\d+\.$", tok.strip()):
            continue
        parts.append(joined.strip())
        cur = []
    if cur:
        parts.append(" ".join(cur).strip())
    return [s for s in parts if len(s) > 15]


# ------------------------------------------------------------------ S5.2 relevance
def relevance(paper, nct, text):
    score, why = 0.0, []
    title = paper.get("title", "") or ""
    both = title + " " + text
    if P.NCT_RE.search(text) and nct in text:
        score += 4; why.append("names NCT")
    if P.DESIGN_RE.search(text):
        score += 2; why.append("trial-design language")
    rtype = (paper.get("reftype") or "").upper()
    if rtype == "RESULT":
        score += 5; why.append("registry RESULT reference")
    elif rtype == "DERIVED":
        score += 2; why.append("registry DERIVED reference")
    elif rtype and not (P.NCT_RE.search(text) and nct in text):
        score -= 4
        why.append(f"registry {rtype} reference (prior work, not this trial)")
    if P.REVIEW_TITLE_HARD.search(title):
        score -= 6; why.append("review/meta title")
    elif P.REVIEW_TITLE_SOFT.search(title):
        score -= 3; why.append("review-type title")
    if P.REVIEW_BODY.search(text):
        score -= 3; why.append("review body language")
    ncts = set(P.NCT_RE.findall(text))
    if len(ncts) >= 4:
        score -= 2.5; why.append(f"{len(ncts)} NCT ids (pooled)")
    return score, why


def excluded(paper, text):
    """Hard exclusions (S5.2): nothing here can establish one trial's outcome."""
    title = paper.get("title", "") or ""
    if P.REVIEW_TITLE_HARD.search(title):
        return "meta-analysis / systematic review"
    if P.EXCLUDE_TITLE.search(title):
        return "excluded publication type (title)"
    if P.POOLED_BODY.search(text):
        return "pooled multi-trial report"
    if P.RETRO_BODY.search(text):
        return "retrospective analysis, not a trial report"
    if len(text) < 120:
        return "abstract too short"
    return None


def is_substudy(paper, text):
    """S5.8: may support Positive, never produce Negative."""
    title = paper.get("title", "") or ""
    if P.SUBSTUDY_TITLE.search(title):
        return True
    if (P.BIOMARKER_TITLE.search(title) and P.HEALTHY_RE.search(text)
            and not P.CLIN_ENDPOINT_TITLE.search(title)):
        return True
    # An association/correlation/prediction paper, in any population, is not an
    # endpoint report (S5.8). Gated on the title alone, so the clinical-endpoint
    # vocabulary must be absent -- a randomised efficacy report is never caught.
    if P.ASSOC_TITLE.search(title) and not P.CLIN_ENDPOINT_STRICT.search(title):
        return True
    return False


# ------------------------------------------------------------------ S5.3 zones
def zones(text):
    sents = sentences(text)
    primary = [s for s in sents if P.PRIMARY_SENT.search(s)]
    marks = list(P.CONCL_MARK.finditer(text))
    if marks:
        tail = text[marks[-1].end():]
        concl = sentences(tail) or sents[-3:]
    else:
        concl = sents[-3:]
    # the results half: second half of the abstract, minus the conclusion zone
    half = sents[len(sents) // 2:]
    cset = set(concl)
    results = [s for s in half if s not in cset]
    return [("primary", primary), ("conclusion", concl), ("results", results)]


# ------------------------------------------------------------------ S5.4 filters
def usable(sent):
    if P.SKIP_SENT.search(sent.strip()):
        return False
    if P.ANIMAL_SENT.search(sent) and not P.DESIGN_RE.search(sent):
        return False
    if P.EXPLORATORY_SENT.search(sent):
        return False
    if P.ENDPOINT_DEF.search(sent) and not P.RESULT_VERB.search(
            P.DISPOSITION_CLAUSE.sub(
                " ", P.DOSE_ACTION.sub(" ", P.PROTOCOL_COND.sub(" ", sent)))):
        return False          # definition, not a result (S9.3 trap 2); a result
                              # verb sitting only inside a conditional protocol
                              # clause does not redeem an endpoint definition
    if P.ANALYTE_SUBJ.search(sent) and not P.PRIMARY_SENT.search(sent):
        return False          # biomarker in subject position (S9.3 trap 8)
    return True


def strip_whereas(sent):
    """Drop a comparator clause introduced by whereas/while/although (S5.4).

    Also drops a conditional protocol clause, which states an escalation rule
    rather than a result and must not contribute polarity, a patient-disposition
    or eligibility clause, whose "did not meet" is about who entered the trial
    rather than about what the trial found, and a clause whose subject is another
    trial ("Other studies failed to show significant benefits ...").
    """
    sent = P.OTHER_STUDY_CLAUSE.sub(
        " ", P.DISPOSITION_CLAUSE.sub(
            " ", P.DOSE_ACTION.sub(" ", P.PROTOCOL_COND.sub(" ", sent))))
    m = re.search(r",?\s*\b(?:whereas|while|although|though)\b", sent, re.I)
    if m and m.start() > 40:
        return sent[:m.start()]
    return sent


# ------------------------------------------------------------------ S5.5-S5.6 polarity
def worse_object(after):
    """True when the object of a comparative is a worse clinical state (S5.6.4).

    Whichever of the two vocabularies matches FIRST describes the object: in
    "the risk of wound-healing complications" the bad term comes first, so a
    later good-sounding word must not cancel the check.
    """
    w = P.WORSE_OBJ.search(after)
    if not w:
        return False
    b = P.BETTER_OBJ.search(after)
    return b is None or w.start() <= b.start()


CLAUSE_CUE = re.compile(
    r"\b(?:showing|demonstrating|suggesting|indicating|while|whereas|although|"
    r"was|were|which|who|resulting|leading|despite|however|but)\b", re.I)

# a comma-separated fragment that is still part of the object, not a new clause:
# "the incidence, duration, or severity of hypoglycaemia" is one object list.
OBJ_CONT = re.compile(
    r"^\s*(?:(?:or|and|nor)\b|(?:the\s+|a\s+|an\s+)?[\w\-/]+"
    r"(?:\s+(?:of|in|for|to)\s+[\w\-/]+)?\s*$)", re.I)


def object_window(s, end, span=70):
    """Text describing the object of a comparative, for the S5.6.4 direction check.

    Clipped at the next clause boundary: in "did not increase the risk of
    wound-healing complications, showing a good efficacy and safety profile" the
    trailing clause would otherwise supply a BETTER_OBJ hit and cancel the check.

    A comma inside a coordinated object list is NOT such a boundary. Clipping at
    it truncated "did not increase the incidence, duration, or severity of
    hypoglycaemia" to "the incidence", which holds no WORSE_OBJ term -- so the
    direction check never fired and a no-increase-in-harm finding was scored as a
    failed endpoint. Commas are therefore walked segment by segment and kept while
    each segment still reads as part of the object.
    """
    w = s[end:end + span]
    hard = re.search(r"[;:]|" + CLAUSE_CUE.pattern, w, re.I)
    if hard:
        w = w[:hard.start()]
    parts = w.split(",")
    kept = [parts[0]]
    for seg in parts[1:]:
        if not OBJ_CONT.match(seg):
            break
        kept.append(seg)
    return ",".join(kept)


def score_sentence(sent, ctx):
    """Return [(family, weight, matched_text, pattern)] for one sentence."""
    hits = []
    s = strip_whereas(sent)
    is_primary = bool(P.PRIMARY_SENT.search(s))
    safety_ctx = bool(P.SAFETY_SUBJ.search(s)) and not P.EFFICACY_WORD.search(s)

    for fam, pats in P.COMPILED.items():
        for pat, rx in pats:
            for m in rx.finditer(s):
                fam_i, w = fam, P.WEIGHTS[fam]
                frag = s[max(0, m.start() - 30):m.end() + 40]

                # --- S5.6.1 negation guard
                if pat not in P.SELF_NEGATED and pat not in P.NUMERIC_POLARITY:
                    pre = s[max(0, m.start() - 26):m.start()]
                    if P.NEG_GUARD.search(pre):
                        fam_i = P.FLIP[fam]          # relabel, don't just flip sign
                        w = P.WEIGHTS[fam_i]

                # --- a p-value that states the test's own threshold is a methods
                # statement, not a result: "with a significance level of p=0.10",
                # "false discovery rate corrected at P = 0.05". Checked in a window
                # around the hit so a result p-value elsewhere in the sentence still
                # scores.
                if (pat in P.NUMERIC_POLARITY
                        and P.ALPHA_WINDOW.search(
                            s[max(0, m.start() - 60):m.end() + 30])):
                    continue

                # --- "the statistical analyses failed to show a 'center effect'" is a
                # model diagnostic, not an endpoint. The failure vocabulary owns
                # "failed to show", so without this it is a confident failed trial.
                if fam_i.startswith("negative") and P.STAT_ARTEFACT.search(s):
                    continue

                # --- a stop reported in a paper, on a trial the registry calls
                # Completed, is read here as a reported failure -- but "enrollment was
                # stopped owing to very slow patient accrual" is administrative and
                # says nothing about the drug (S4's administrative/substantive split,
                # applied to a stop that comes from the publication rather than the
                # status field). An accrual stop is administrative by default; a
                # trial-level stop only when a reason of that kind is given.
                if fam_i.startswith("negative") and P.STOP_HIT.search(m.group(0)):
                    subst = P.SUBSTANTIVE_STOP_REASON.search(s)
                    if not subst and (P.ACCRUAL_STOP.search(s)
                                      or P.ADMIN_STOP_REASON.search(s)):
                        continue

                # --- a response rate is not a met endpoint (mirror of
                # DISPOSITION_CLAUSE): drop to neutral when a patient count or
                # proportion holds the subject slot ahead of the endpoint verb.
                if (fam_i.endswith("endpoint")
                        and re.search(r"\b(?:achieved|met|reached|attained)\b",
                                      m.group(0), re.I)
                        and P.COUNT_SUBJ.search(s[:m.start()])):
                    continue

                # --- S5.6.4 direction check (before the positive hit is trusted)
                if fam_i.startswith("positive") and P.HIGHER_BAD.search(m.group(0)):
                    after = object_window(s, m.end())
                    if worse_object(after):
                        continue                      # drop to neutral, don't flip

                # --- S5.6.4 mirrored: a negated increase-verb is direction-blind too.
                # "did not increase the risk of wound-healing complications" is good
                # news, but the negative-endpoint family owns "did not ... increase".
                # Only increase-verbs flip this way: "did not reduce complications"
                # is a genuine failure and must survive.
                if (fam_i.startswith("negative")
                        and re.search(r"\b(?:no|not|without|neither|nor)\b", m.group(0), re.I)
                        and re.search(r"(?:increase[sd]?|higher|greater|more frequent|"
                                      r"more common|elevated|worsen)", m.group(0), re.I)):
                    after = object_window(s, m.end())
                    # a safety-subject sentence has no endpoint to miss, so the
                    # negated increase is neutral-to-good there whatever follows
                    if worse_object(after) or (safety_ctx and not is_primary):
                        continue

                # --- S5.6.5 (NI arm): superiority is not what a non-inferiority trial
                # set out to show, so "did not demonstrate superiority" is not a failure
                # once the same abstract states non-inferiority was met.
                if (ctx.get("ni_met") and fam_i.startswith("negative")
                        and P.SUPERIORITY_MISS.search(s)):
                    continue

                # --- S5.6.2 safety-context routing, never over a primary endpoint
                if safety_ctx and not is_primary and "k4" not in OFF:
                    if fam_i == "negative-efficacy" and P.NO_DIFF.search(s):
                        fam_i, w = "positive-safety", P.WEIGHTS["positive-safety"]
                    elif fam_i == "negative-efficacy" and P.HIGHER_BAD.search(m.group(0)):
                        fam_i, w = "negative-safety", P.WEIGHTS["negative-safety"]

                # --- S5.6.5 equivalence re-reading, tested on the whole sentence
                # The primary-endpoint sentence is the one this rule exists for in a
                # PK/bioequivalence study ("AUC was equivalent ... (primary end point)
                # ... P = .39"), so it is re-read too -- unless the sentence itself
                # reports the equivalence or non-inferiority goal being missed.
                if (ctx.get("equiv") and fam_i in ("negative-efficacy", "negative-endpoint")
                        and P.NO_DIFF.search(s)
                        and not (is_primary and P.EQUIV_FAIL.search(s))):
                    fam_i, w = "positive-endpoint", P.WEIGHTS["positive-endpoint"]
                    frag = "[equivalence study: absence of a difference is the intended result] " + frag

                # --- S5.6.3 phase weighting
                if ctx.get("phase12"):
                    if "safety" in fam_i:
                        w *= 1.8
                    elif "efficacy" in fam_i:
                        w *= 0.8

                hits.append({"family": fam_i, "w": w, "frag": frag.strip(),
                             "sent": s, "primary": is_primary, "pattern": pat,
                             "end": m.end()})
    return hits


def decide_zone(zone_name, sents, ctx):
    """S5.5 sum, S5.7 failure gate. Returns (label, hit, hits) or (None, None, [])."""
    hits = []
    for s in sents:
        if usable(s):
            hits.extend(score_sentence(s, ctx))
    if not hits:
        return None, None, []
    pos = sum(h["w"] for h in hits if h["family"].startswith("positive"))
    neg = sum(h["w"] for h in hits if h["family"].startswith("negative"))
    if pos == neg:
        return None, None, hits
    if neg > pos:
        if ctx.get("substudy"):
            return None, None, hits          # S5.8: a sub-study never fails a trial
        best = max((h for h in hits if h["family"].startswith("negative")),
                   key=lambda h: h["w"])
        # S5.7: a failure needs endpoint-level evidence
        if "k3" not in OFF:
            if best["family"] != "negative-endpoint" and not best["primary"]:
                return None, None, hits
            # A primary endpoint that is itself a harm-rate measure carried only by
            # generic no-difference wording is not a failed trial; decline rather than
            # flip (S5.6.4), since S5.6.2 forbids safety routing over a primary.
            if (best["family"] == "negative-efficacy" and best["primary"]
                    and P.NO_DIFF.search(best["sent"])
                    and P.SAFETY_PRIMARY_MEASURE.search(best["sent"])):
                return None, None, hits
            # S5.4 mirrored: a miss on a named secondary measure, in a sentence that
            # also reports a positive result and is not itself a primary-endpoint
            # statement, does not fail the trial. Decline rather than flip.
            if not best["primary"]:
                obj = object_window(best["sent"], best.get("end", 0), span=90)
                if (P.SECONDARY_OBJ.search(obj) and not P.PRIMARY_SENT.search(obj)
                        and any(h["family"].startswith("positive")
                                and h["sent"] == best["sent"] for h in hits)):
                    return None, None, hits
        return "Negative", best, hits
    best = max((h for h in hits if h["family"].startswith("positive")), key=lambda h: h["w"])
    # S5.8 lets a sub-study support a Positive, but a raw biomarker-direction
    # sentence ("plasma lipids were markedly increased") is not support for a
    # trial outcome. Require the decisive signal to be an endpoint or safety
    # statement, or to sit in a primary-endpoint sentence.
    if ctx.get("substudy") and not (
            best["family"].endswith("endpoint") or "safety" in best["family"]
            or best["primary"]):
        return None, None, hits
    return "Positive", best, hits


def predates_trial(paper, ctx_base):
    """True if the paper was published before the trial started (S5.2)."""
    py = (paper.get("year") or "").strip()[:4]
    sy = (ctx_base.get("start_year") or "").strip()[:4]
    if not (py.isdigit() and sy.isdigit()):
        return False
    return int(py) < int(sy)


def from_paper(paper, nct, ctx_base):
    text = normalise(paper.get("abstract", ""))
    ex = excluded(paper, text)
    if ex:
        return None
    if predates_trial(paper, ctx_base):
        return None
    rel, why = relevance(paper, nct, text)
    floor = 2 if "k7" not in ON or paper.get("source") != "epmc_ft" else 1
    if rel < floor:
        return None
    ctx = dict(ctx_base)
    ctx["equiv"] = bool(P.EQUIV_STUDY.search((paper.get("title") or "") + " " + text[:600]))
    ctx["ni_met"] = bool(P.NI_MET.search(text))
    ctx["substudy"] = is_substudy(paper, text)
    for zname, sents in zones(text):
        label, hit, _ = decide_zone(zname, sents, ctx)
        if label:
            return {"label": label, "zone": zname, "hit": hit, "rel": rel,
                    "why": why, "paper": paper, "names_nct": nct in text,
                    "equiv": ctx["equiv"], "substudy": ctx["substudy"]}
    return None


# ------------------------------------------------------------------ S6 posted results
HARM_PRIMARY = re.compile(
    r"\b(?:nephro|hepato|cardio|oto|neuro|myelo)?toxicit(?:y|ies)|\badverse (?:event|reaction|effect)|"
    r"\btoxic effect|\bdose[- ]limiting", re.I)


def from_results(det, phase12):
    prim = [o for o in det.get("outcomes", []) if o["type"] == "PRIMARY"]
    pv = [(o, a) for o in prim for a in o["pvalues"]]
    # S6: the registry records significance but not direction. Where the primary
    # outcome is itself a harm measure, a significant result is as likely to mean more
    # toxicity as less, so the p-value proportion cannot support a Positive at all.
    # Skip the p-value branch and let the adverse-event rate below decide. Found by
    # hand-read (S9.2): a nephrotoxicity primary with p=0.0002, 42% serious AEs and 60
    # deaths was being called Positive.
    if pv and HARM_PRIMARY.search(" ".join(o["title"] for o in prim)):
        pv = []
    if pv:
        sig = 0
        for o, a in pv:
            m = re.search(r"([<>=]?)\s*0?\.(\d+)|([<>=]?)\s*(\d+\.\d+)", a["p"])
            try:
                val = float(re.sub(r"[^0-9.]", "", a["p"]))
            except ValueError:
                continue
            lt = "<" in a["p"] or "≤" in a["p"]
            if val < 0.05 or (lt and val <= 0.05):
                sig += 1
        shown = "; ".join(f"{o['title'][:80]}: p{a['p']}" for o, a in pv[:3])
        ae = ae_summary(det)
        label = "Negative" if sig == 0 else "Positive"
        return {"label": label, "evidence":
                f"registry posted results, primary-outcome analyses: {shown} "
                f"({sig}/{len(pv)} analyses reach p<0.05; the registry records "
                f"significance but not direction). {ae}"}
    # no p-values: follow serious-AE rate only when the primary outcome is safety/PK
    titles = " ".join(o["title"] for o in prim).lower()
    # S6 restricts this branch to a safety / tolerability / PK primary outcome.
    # The Phase-1 bridge from S5.6.3 ("in a phase 1 trial the primary endpoint IS
    # safety") is a reasonable extension, but only where the posted primary outcome
    # is not itself plainly an efficacy measure -- judging a RECIST-response or
    # 1-year-survival primary on its adverse-event rate alone is a safety-only read
    # of an efficacy endpoint.
    safety_primary = bool(re.search(
        r"adverse|safety|tolerab|toxicit|dose-limiting|pharmacokinet|\bAUC\b|cmax|"
        r"maximum tolerated|number of participants with.*event", titles, re.I))
    efficacy_primary = bool(re.search(
        r"response|survival|progression|remission|rejection|hba1c|glycem|glycaem|"
        r"efficacy|cure|eradication|pain|quality of life|time to|change from baseline|"
        r"rate of (?:delivery|pregnancy|induction|success)|bone mineral|fracture",
        titles, re.I))
    safety_primary = safety_primary or (phase12 and not efficacy_primary)
    groups = det.get("ae_groups", [])
    if not (safety_primary and groups):
        return None
    ser = sum(g["ser"] or 0 for g in groups)
    at = sum(g["ser_at"] or 0 for g in groups)
    dead = sum(g["dead"] or 0 for g in groups)
    ae = ae_summary(det)
    if at:
        rate = ser / at
        # A low adverse-event rate establishes only that the drug was tolerated. Where
        # the posted primary ALSO names an efficacy measure ("...C-peptide area under
        # the curve", "...Overall Survival Rate at 12 months"), that is half of what a
        # Positive requires, so the row is left uncalled (S6 mid-band) and falls to S7.
        # A high rate is different: "not safely tolerated" is on its own sufficient for
        # a Negative under the task's label definitions, so that branch still fires.
        if rate < 0.15 and dead == 0 and not efficacy_primary:
            return {"label": "Positive", "evidence":
                    f"registry posted results, safety/PK primary outcome "
                    f"('{prim[0]['title'][:90] if prim else 'n/a'}'); {ae}"}
        if rate >= 0.50 or (rate >= 0.30 and dead > 0):
            # Not safely tolerated is on its own sufficient (S1), so this branch fires
            # whether or not the primary is a safety measure -- say which it was rather
            # than calling an efficacy primary "safety/PK".
            kind = ("safety/PK primary outcome" if not efficacy_primary
                    else "serious-adverse-event rate; posted primary outcome")
            return {"label": "Negative", "evidence":
                    f"registry posted results, {kind} "
                    f"('{prim[0]['title'][:90] if prim else 'n/a'}'); {ae}"}
    return None          # mid-band left uncalled (S6)


def ae_summary(det):
    groups = det.get("ae_groups", [])
    ser = sum(g["ser"] or 0 for g in groups)
    at = sum(g["ser_at"] or 0 for g in groups)
    dead = sum(g["dead"] or 0 for g in groups)
    # S9.3: report the bare count when the denominator is missing, never '2/0 (n/a)'
    s = (f"serious adverse events {ser}/{at} ({100 * ser / at:.0f}%)" if at
         else f"serious adverse events {ser} (at-risk denominator not posted)")
    return s + f", deaths {dead}."


# ------------------------------------------------------------------ assemble a call
def classify_one(trial, st, det, extra_papers):
    nct = trial["nct"]
    status = st.get("status", "")
    why = (st.get("why_stopped") or "").strip()
    phases = st.get("phases", [])
    phase12 = (("PHASE1" in phases or "PHASE2" in phases) and "PHASE3" not in phases
               and "PHASE4" not in phases)
    phase12 = phase12 and "PHASE1" in phases      # S5.6.3: Phase 1 or Phase 1/2 only

    # --- S4: status decides five of the seven labels
    if status in STOPPED:
        lab = STATUS_LABEL[status]
        ev = (f"ClinicalTrials.gov registry status: {lab}. "
              + (f'whyStopped (verbatim): "{why}"' if why else
                 "whyStopped: no reason posted by the sponsor."))
        return {"nct": nct, "outcome": lab, "confidence": "High",
                "evidence": ev, "source": "status-stopped"}
    if status in ACTIVE:
        return {"nct": nct, "outcome": "Active", "confidence": "High",
                "evidence": f"ClinicalTrials.gov registry status: {STATUS_LABEL[status]}.",
                "source": "status-active"}
    if status == "NOT_IN_REGISTRY":
        return {"nct": nct, "outcome": "Unknown", "confidence": "Low",
                "evidence": "LOW CONFIDENCE: searched ClinicalTrials.gov (no record returned "
                            "for this identifier) and the bundle literature section; "
                            "nothing on record settles the outcome.",
                "source": "unknown"}

    ctx = {"phase12": phase12, "start_year": (st.get("start_date") or "")[:4]}
    papers = list(trial.get("papers", [])) + list(extra_papers)

    # --- S3 src 2/3: publications
    best = None
    for p in papers:
        r = from_paper(p, nct, ctx)
        if not r:
            continue
        # prefer a RESULT-reference or NCT-naming paper, then a primary/conclusion zone
        rank = ((p.get("reftype") == "RESULT") * 4 + r["names_nct"] * 3
                + {"primary": 2, "conclusion": 1, "results": 0}[r["zone"]])
        if best is None or rank > best[0]:
            best = (rank, r)
    if best:
        r = best[1]
        p = r["paper"]
        src = {"bundle": "bundle ## Literature section",
               "registry_ref": f"registry-listed {p.get('reftype','')} reference",
               "epmc_ft": "Europe PMC full-text search on the NCT id"}.get(
                   p.get("source", "bundle"), "literature")
        pm = ("PMID " + p["pmids"][0]) if p.get("pmids") else "no PMID"
        strong = (r["names_nct"] or p.get("reftype") == "RESULT")
        endpointy = (r["hit"]["family"].endswith("endpoint")
                     or "safety" in r["hit"]["family"] or r["hit"]["primary"])
        if r["zone"] == "results" or r["equiv"]:
            conf = "Low"
        elif strong and endpointy and r["zone"] in ("primary", "conclusion"):
            conf = "High"
        else:
            conf = "Medium"
        ev = (f"{src}: \"{p.get('title','')[:160]}\" ({pm}); {r['zone']} zone, "
              f"{r['hit']['family']} signal: \"...{r['hit']['frag'][:260]}...\"")
        if r["equiv"] and r["label"] != "Negative":
            ev += " [equivalence/PK study: absence of a significant difference read as the intended result]"
        if r["substudy"]:
            ev += " [sub-study/mechanistic paper: allowed to support a positive call only]"
        lab = FAILED if r["label"] == "Negative" else r["label"]
        if lab == FAILED:
            # S1: the label asserts the trial reported out rather than stopping early,
            # so the registry status it rests on is named in Evidence.
            ev += (f" Registry status: {STATUS_LABEL.get(status, status)} "
                   "(not stopped early; the failure is a reported one).")
        if conf == "Low":
            ev = "LOW CONFIDENCE: " + ev
        return {"nct": nct, "outcome": lab, "confidence": conf,
                "evidence": ev, "source": "publication"}

    # --- S3 src 4 / S6: posted results
    if det:
        rr = from_results(det, phase12)
        if rr:
            ev = "LOW CONFIDENCE: " + rr["evidence"]
            if det.get("caveats"):
                ev += f' Limitations and caveats: "{det["caveats"][:200]}"'
            lab = FAILED if rr["label"] == "Negative" else rr["label"]
            if lab == FAILED:
                ev += (f" Registry status: {STATUS_LABEL.get(status, status)} "
                       "(not stopped early; the failure is a reported one).")
            return {"nct": nct, "outcome": lab, "confidence": "Low",
                    "evidence": ev, "source": "posted-results"}

    # --- S7: the default-positive convention
    has_trail = bool(papers) or bool(st.get("refs")) or bool(st.get("has_results"))
    if status == "COMPLETED" and has_trail and "k5" not in OFF:
        bits = []
        if papers:
            bits.append(f"{len(papers)} candidate publication(s)")
        if st.get("refs"):
            bits.append(f"{len(st['refs'])} registry-listed reference(s)")
        if st.get("has_results"):
            bits.append("registry posted results")
        return {"nct": nct, "outcome": "Positive", "confidence": "Low",
                "evidence": "LOW CONFIDENCE: scored Positive by convention, NOT from a "
                            "located outcome statement. Registry status: Completed, with a "
                            "paper trail (" + ", ".join(bits) + "), and nothing on record "
                            "reports a missed endpoint, an early stop or a safety failure. "
                            "No usable outcome sentence was found in the available abstracts "
                            "or posted results.",
                "source": "convention"}

    searched = ["ClinicalTrials.gov registry status (" + STATUS_LABEL.get(status, status) + ")"]
    if trial.get("papers"):
        searched.append(f"{len(trial['papers'])} bundle abstract(s), none passing the "
                        f"relevance gate or yielding an outcome signal")
    else:
        searched.append("the bundle ## Literature section (no abstracts present)")
    if st.get("refs"):
        searched.append(f"{len(st['refs'])} registry-listed reference(s)")
    if extra_papers:
        searched.append(f"{len(extra_papers)} fetched abstract(s)")
    if st.get("has_results"):
        searched.append("registry posted results (no primary-outcome p-values and no "
                        "decisive safety rate)")
    return {"nct": nct, "outcome": "Unknown", "confidence": "Low",
            "evidence": "LOW CONFIDENCE: searched " + "; ".join(searched)
                        + ". Nothing on record settles the outcome.",
            "source": "unknown"}


def main():
    lit = json.load(open(os.path.join(WORK, "lit.json")))
    st = json.load(open(os.path.join(WORK, "status.json")))
    dp = os.path.join(WORK, "detail.json")
    det = json.load(open(dp)) if os.path.exists(dp) else {}
    ep = os.path.join(WORK, "extra_papers.json")
    extra = json.load(open(ep)) if os.path.exists(ep) else {}

    calls = []
    for t in lit:
        calls.append(classify_one(t, st.get(t["nct"], {}), det.get(t["nct"]),
                                  extra.get(t["nct"], [])))
    with open(os.path.join(WORK, "calls.json"), "w") as fh:
        json.dump(calls, fh)
    unres = [c["nct"] for c in calls if c["source"] in ("unknown", "convention")]
    with open(os.path.join(WORK, "unresolved.json"), "w") as fh:
        json.dump(unres, fh)

    from collections import Counter
    print("--- outcome ---")
    for k, v in Counter(c["outcome"] for c in calls).most_common():
        print(f"{v:6d}  {k}")
    print("--- confidence ---")
    for k, v in Counter(c["confidence"] for c in calls).most_common():
        print(f"{v:6d}  {k}")
    print("--- decision source ---")
    for k, v in Counter(c["source"] for c in calls).most_common():
        print(f"{v:6d}  {k}")
    print(f"unresolved (for later fetch stages) = {len(unres)}")


if __name__ == "__main__":
    main()
