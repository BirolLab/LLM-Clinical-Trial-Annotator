#!/usr/bin/env python3
"""Corpus match count per individual pattern (methodology S9.1).

A zero is a broken regex, not a rare phrase -- the classic cause is a `\b`
placed after a stem or at the end of an alternation. Mandatory after every edit
to patterns.py; investigate low counts too, not only the zeroes.
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patterns as P
from classify import normalise

WORK = os.environ.get("OUTCOME_WORK", "outcome_pipeline/work")

lit = json.load(open(os.path.join(WORK, "lit.json")))
texts, titles = [], []
for t in lit:
    for p in t["papers"]:
        texts.append(normalise(p["abstract"]))
        titles.append(p.get("title", ""))
ep = os.path.join(WORK, "extra_papers.json")
if os.path.exists(ep):
    for ps in json.load(open(ep)).values():
        for p in ps:
            texts.append(normalise(p["abstract"]))
            titles.append(p.get("title", ""))
print(f"corpus: {len(texts)} abstracts\n")

rows = []
for fam, pats in P.FAMILIES.items():
    for pat in pats:
        rx = re.compile(pat, re.I)
        n = sum(1 for t in texts if rx.search(t))
        rows.append((n, fam, pat))

SINGLES = [("relevance", "DESIGN_RE", P.DESIGN_RE, texts), ("relevance", "NCT_RE", P.NCT_RE, texts),
           ("title", "REVIEW_TITLE_HARD", P.REVIEW_TITLE_HARD, titles),
           ("title", "REVIEW_TITLE_SOFT", P.REVIEW_TITLE_SOFT, titles),
           ("body", "REVIEW_BODY", P.REVIEW_BODY, texts),
           ("title", "EXCLUDE_TITLE", P.EXCLUDE_TITLE, titles),
           ("body", "POOLED_BODY", P.POOLED_BODY, texts),
           ("title", "SUBSTUDY_TITLE", P.SUBSTUDY_TITLE, titles),
           ("title", "BIOMARKER_TITLE", P.BIOMARKER_TITLE, titles),
           ("body", "HEALTHY_RE", P.HEALTHY_RE, texts),
           ("title", "CLIN_ENDPOINT_TITLE", P.CLIN_ENDPOINT_TITLE, titles),
           ("filter", "SKIP_SENT", P.SKIP_SENT, texts), ("filter", "ANIMAL_SENT", P.ANIMAL_SENT, texts),
           ("filter", "EXPLORATORY_SENT", P.EXPLORATORY_SENT, texts),
           ("filter", "ENDPOINT_DEF", P.ENDPOINT_DEF, texts),
           ("filter", "PROTOCOL_COND", P.PROTOCOL_COND, texts),
           ("filter", "DOSE_ACTION", P.DOSE_ACTION, texts),
           ("filter", "RESULT_VERB", P.RESULT_VERB, texts),
           ("filter", "ANALYTE_SUBJ", P.ANALYTE_SUBJ, texts),
           ("filter", "PRIMARY_SENT", P.PRIMARY_SENT, texts),
           ("filter", "CONCL_MARK", P.CONCL_MARK, texts),
           ("corr", "NEG_GUARD", P.NEG_GUARD, texts), ("corr", "SAFETY_SUBJ", P.SAFETY_SUBJ, texts),
           ("corr", "EFFICACY_WORD", P.EFFICACY_WORD, texts), ("corr", "NO_DIFF", P.NO_DIFF, texts),
           ("corr", "HIGHER_BAD", P.HIGHER_BAD, texts), ("corr", "WORSE_OBJ", P.WORSE_OBJ, texts),
           ("corr", "BETTER_OBJ", P.BETTER_OBJ, texts), ("corr", "EQUIV_STUDY", P.EQUIV_STUDY, texts),
           ("corr", "NI_MET", P.NI_MET, texts),
           ("corr", "SUPERIORITY_MISS", P.SUPERIORITY_MISS, texts),
           ("corr", "EQUIV_FAIL", P.EQUIV_FAIL, texts),
           ("corr", "SAFETY_PRIMARY_MEASURE", P.SAFETY_PRIMARY_MEASURE, texts),
           ("corr", "SECONDARY_OBJ", P.SECONDARY_OBJ, texts),
           ("body", "RETRO_BODY", P.RETRO_BODY, texts),
           ("filter", "DISPOSITION_CLAUSE", P.DISPOSITION_CLAUSE, texts),
           ("filter", "COUNT_SUBJ", P.COUNT_SUBJ, texts),
           # S9.2 round 1-2 additions: audited like every other lexicon, so a
           # `\b`-style break in one of them fails loudly rather than silently.
           ("filter", "OTHER_STUDY_CLAUSE", P.OTHER_STUDY_CLAUSE, texts),
           ("corr", "ADMIN_STOP_REASON", P.ADMIN_STOP_REASON, texts),
           ("corr", "SUBSTANTIVE_STOP_REASON", P.SUBSTANTIVE_STOP_REASON, texts),
           ("corr", "STOP_HIT", P.STOP_HIT, texts),
           ("corr", "ACCRUAL_STOP", P.ACCRUAL_STOP, texts),
           ("corr", "ALPHA_WINDOW", P.ALPHA_WINDOW, texts),
           ("corr", "STAT_ARTEFACT", P.STAT_ARTEFACT, texts),
           ("title", "CLIN_ENDPOINT_STRICT", P.CLIN_ENDPOINT_STRICT, titles)]

print("=== ZERO or LOW (<15) polarity patterns ===")
bad = 0
for n, fam, pat in sorted(rows):
    if n < 15:
        bad += 1
        print(f"{n:6d}  {'*ZERO*' if n == 0 else '      '} {fam:18s} {pat[:105]}")
if not bad:
    print("  (none)")

print("\n=== all polarity patterns, by count ===")
for n, fam, pat in sorted(rows, reverse=True):
    print(f"{n:6d}  {fam:18s} {pat[:100]}")

print("\n=== named lexicons ===")
for grp, name, rx, corpus in SINGLES:
    n = sum(1 for t in corpus if rx.search(t))
    flag = " *ZERO*" if n == 0 else ""
    print(f"{n:6d}  {grp:9s} {name}{flag}")
