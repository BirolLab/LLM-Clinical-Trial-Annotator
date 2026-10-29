# failure_pipeline — how failure_10_21_2026.csv was built

Method: `../failure_methodology.md`. Notes/deliverable commentary:
`../failure_10_21_2026_notes.md`. Section numbers below refer to the methodology.

## Modules (§13 roles)

| file | role |
|---|---|
| `config.py` | **the seven inputs of §0 in one place** — corpus glob, registry endpoint, failure-signal table and column, label-set path (none), vocabulary, output schema, residual-vs-prior switch, §3 regimes, §7.2 priors |
| `fetch_ctg.py` | registry API, batched → status, `whyStopped`, dates, phase, enrolment, sponsor, conditions, interventions, primary outcomes, reference list |
| `fetch_detail.py` | registry API, subset → detailed description, limitations-and-caveats, participant flow, primary-outcome analyses (§4.1) |
| `fetch_refs.py` | Europe PMC → abstracts for registry-listed references, `RESULT`→`DERIVED`→`BACKGROUND` (§6.4) |
| `parse_lit.py` | per-trial bundle `## Literature` text, keyed by NCT id |
| `rules.py` | **the decision function** — scrubbers, pattern sets, arbitration, narrative/publication/results readers. Patterns and arbitration only; no paths, no column names |
| `build.py` | walks the row set, applies the §4 tiers in order, writes the deliverable and the sidecar |
| `units.py` | 71 verbatim stop texts → expected bucket (fast regression check, §10.6) |
| `test_traps.py` | the 19 trap classes of §10.3, checked on this corpus |
| `validate.py` | the 18 invariants of §10.4, row-set invariant asserted by name |
| `audit.py` | per-pattern match counts over the corpus stop texts, to find inert regexes (§10.1) |
| `manual.json` | external overrides (§11). **Absent — external search yielded zero rows.** |

`rules.py` is imported by `build.py`, `units.py`, `test_traps.py` and `audit.py`, so the
rules being scored cannot drift from the rules being shipped (§10.6).

## Run order

```bash
cd failure_pipeline
python3 -I -c "..."                                   # work/ids_all.txt from the outcome table
python3 -I fetch_ctg.py    work/ids_all.txt    work/ctg_base.jsonl
python3 -I parse_lit.py    work/lit.jsonl
python3 -I fetch_detail.py work/ids_detail.txt work/ctg_detail.jsonl     # unresolved + posted-results subset
python3 -I fetch_refs.py   work/ctg_base.jsonl work/ids_refs.txt work/refs.jsonl
python3 -I build.py && python3 -I units.py && python3 -I test_traps.py && python3 -I validate.py
```

`fetch_ctg.py` takes a few minutes for 7,734 ids in batches of 50. **It buffers its
output**: a partially-written `ctg_base.jsonl` during the run is lag, not a crash — check
the log for its `DONE` line before concluding anything.

## Defects found by hand-reading, and fixed (§10.2)

Every one of these was found by reading `Evidence` against the source text. **None was
visible in any aggregate statistic**, and the table passed its invariants with several of
them live.

1. **§5.2 denial too loose** — `not available due to COVID-19` read the `not available`
   as a denial and dropped the one true pandemic case (trap 9). Fixed by requiring `not`
   to attach directly to the causal verb.
2. **§5.2 denial too tight, after (1)** — `the study was not terminated due to any safety
   issues` then survived and produced a false `Toxic/unsafe`. Fixed by allowing one
   intervening *stop* verb only.
3. **§5.2 `for` missing from the denial markers** — `not for safety reasons` and
   `neither safety nor efficacy reasons` produced false `Toxic/unsafe` on three Pfizer
   Exubera trials. `for` belongs in the §5.2 denial list while staying out of §5.6's
   causal list (trap 13); I had conflated the two.
4. **§5.3 scrubbed before it was tested** — the positive-safety scrubber removed
   `safety benefit in Experimental arm`, the very phrase marking the non-failure, so the
   row fell through to a monitoring-board weak signal. Fixed by testing the unscrubbed
   text too.
5. **§6 literature route far too permissive** — it was accepting any sentence that merely
   *framed* an endpoint, and then letting §5.4's operational residual fire on it. 120 rows,
   nearly all wrong: review prose, mechanism descriptions, methods sentences, positive
   findings. Rewritten to §4's tiers 3 and 4 only — a trial-level early-stop statement, or
   an explicit endpoint-miss construction — and the operational residual is now confined to
   the sponsor's stated reason. 120 → 20 rows.
6. **Trap 14 in the literature route** — `2 patients … failed to achieve a response` and
   `patients who failed to achieve target HbA1c` read as endpoint misses. Fixed with a
   participant-subject guard.
7. **Europe PMC markup defeated sentence splitting** — `<h4>Conclusion</h4>` welded a
   result clause to a conclusion clause, so 4 of 14 reference rows quoted a sentence that
   said the opposite of the call (one quoted a *significant benefit*, 61% vs 34%, p=.03).
   Fixed by treating a tag as a sentence boundary.
8. **§5.1 pointer path over-gated** — `See termination reason in detailed description`
   was re-filtered through §4.1's study-as-subject gate, which discarded a termination
   narrative whose subject was the *drug programme*. All 11 pointer trials were falling
   through to the residual or to an operational residual. Fixed by substituting the
   detailed description wholesale, as §5.1 says. All 11 now resolve.
9. **§4.1 boilerplate exclusion too thin** — future-tense protocol design text
   (`The study will include a screening phase…`, `Patients may continue on study treatment
   until…`) was being read as termination narrative and produced three false
   `Toxic/unsafe` rows. Fixed by excluding future/permissive tense and schedule language.

10. **§4.1 route admitting non-trial-level text** — the participant-disposition route was
    accepting per-participant categories (`Protocol discontinuation criteria met`,
    `Non-Compliance With Study Drug`, `Randomized but not treated`) rather than the
    trial-level ones §4.1 intends (`Study terminated by sponsor`); §5.4's operational
    residual was also firing on narrative sentences that stated no reason at all. Fixed by
    requiring a trial-level termination in the disposition and confining the operational
    residual to the sponsor's stated reason. 40 → 18 narrative rows, all of which now read
    correctly.
11. **Unanchored alternatives matching inside words** — `clos\w*` matched the *clospo* of
    "cy**clospo**rine" and `low` matched the *llow* of "fo**llow**ing", so protocol text was
    selected as a termination narrative and `site following a move` was read as a
    recruitment shortfall. Fixed by anchoring `STOP_VERB`, `STOP_SUBJECT`, `SHORTFALL` and
    `TOPIC` with `\b`. This class of bug is invisible in aggregate — it changed only 2 rows
    here — but it is silent and systemic, and worth checking for on any new corpus. The fix
    itself then regressed one row (`not meeting` no longer matched `not\s+meet`), caught by
    diffing the table before and after; `not\s+meet\w*` restored it.

Two further corrections, caught while writing the notes rather than by hand-reading: the
notes first claimed §4.1 recovered 20 of the 132 blank-`whyStopped` trials (measured: 10),
and the first draft of this README claimed 15.

## Deliberate departures from the methodology's examples

* **§5.4 operational residual is confined to the stated stop reason and the registry
  narrative fields.** The methodology does not say this explicitly; defect 5 is why.
* **A bare interim-analysis stop is treated like §5.7's bare monitoring-board stop** —
  `Ineffective for purpose` at Low with the ambiguity in `Evidence`. The methodology names
  the board case but not the bare-interim case.
* **`recruitment rate` and `accrual rate` as a leading bare clause count as a recruitment
  shortfall**, by the same reasoning §5.5 applies to `Accrual Factor`.

---

## Generation 4 — rebuild of 2026-10-22

`outcome_10_20_2026.csv` was regenerated (7,734 rows; 1,300 `Negative`, against 1,331
in the table generation 3 was built from), so the table was rebuilt from it.
`rules_g3.py` is a frozen copy of the decision function that produced the generation-3
sidecar (`work/sidecar_g3_snapshot.csv`); `rules.py` carries the generation-4 line, and
every change below is marked `g4` in the source.

**Re-measured before anything was changed (§0d):** the field list was re-validated with
a single-record call; the corpus census was re-run (7,734 records, 0 hits for any
spelling of the stop reason); `audit.py` was re-run over the 860 `whyStopped` texts
(2 inert patterns, both genuinely absent whole-string anchors); all 71 unit cases and
all 19 trap classes re-checked. Registry evidence was extended to the new failure set:
`ctg_detail.jsonl` 818 → 1,335 trials, `refs.jsonl` +6 trials.

### Defects found by hand-reading, and fixed (§10.2)

Each fix was applied alone and diffed row by row against the whole table before it was
kept; the row counts below are from those diffs.

12. **A planned per-protocol pause read as a safety stop.** `NCT00828009`, a COMPLETED
    trial: *"suspended per protocol on January 12, 2012 for interim toxicity analysis …
    reactivated on October 9, 2012 … closed to accrual on October 13, 2014"* was being
    read by the §4.1 narrative route as `Toxic/unsafe`. A stop the same sentence says
    was planned, or says was later undone, is not a termination. `PLANNED_PAUSE` added
    to `stop_sentences`. **1 row.**
13. **An objective-form sentence read as an endpoint miss** (trap 14). `METHODS_BOILER`
    required the word *whether* after the objective verb, so *"To examine a novel
    ligand model … with the a priori hypothesis that high tumor expression … would
    predict panitumumab therapy benefit …; and low expression, lack of efficacy"*
    reached `ENDPOINT_MISS` on its `lack of efficacy` tail. Added the bare objective
    opening and the `a priori hypothesis` / `hypothesised that` markers. **1 row.**
14. **The participant-subject guard was one clause too short** (README defect 6's
    class). *"2 patients in the prednisone arm of the study failed to achieve a
    response"* puts seven words between the subject and the match and the guard allowed
    six, so a participant-flow sentence became a High-confidence endpoint miss.
    Widened to nine. **1 row.**
15. **Paper-level relevance: the bundle literature contains papers about neither the
    trial's intervention nor its question.** An abstract on *"the impact of feedback
    training on prediction of cancer clinical trial results"* was supplying the endpoint
    miss for a Hodgkin chemotherapy trial *and* for an antifungal prophylaxis trial, and
    a hepatocellular-carcinoma review's brivanib result was supplying one for a
    thymalfasin trial. §6.1's gates are all sentence-level or title-level and none of
    them can see this. Added `drug_terms` / `_paper_mentions`: a tier-4 endpoint miss
    from bundle literature must come from a paper naming one of the trial's own
    interventions (or the trial id). **3 rows.**

    Scoped deliberately to tier 4 from the bundle. The first draft applied it to every
    paper and every tier and lost two correct rows — a registry-listed `RESULT`
    reference whose abstract named none of the conditioning drugs (`NCT00378534`), and
    a tier-3 early-stop sentence whose paper says *orteronel* where the registry says
    *TAK-700* (`NCT01546987`). A tier-3 sentence is already constrained by
    `STOP_SUBJECT`/`POOLED`, and a registry-listed reference carries the registry's own
    assertion of the link.

### Other changes

* `manual.json` now exists (§11): one external override (`NCT01076764`, TAO/otamixaban)
  and one *negative* override — an entry whose `"reason"` is `null` keeps the residual
  but replaces the `Evidence` string, for the case where the external source
  establishes that there is no failure reason to give (`NCT04255433`, SURPASS-CVOT met
  its primary non-inferiority objective). `build.py` gained that branch.

---

## Generation 5 — rebuild of 2026-10-22 (later)

The deliverable `../failure_10_21_2026.csv` was absent while the generation-4 sidecar was
present, so the table was rebuilt from the generation-4 rules and inputs. Inputs were
re-verified aligned before the run: 7,734 outcome ids, all present in `ctg_base.jsonl`,
none extra; `ctg_detail.jsonl` covers all 1,300 failure-set trials. All 71 unit cases,
19 trap classes and 18 invariants pass.

**The generation-4 hand-verified corrections were checked individually for survival**
(they are the thing a rebuild drops invisibly): fix 12 `NCT00828009` still `Unknown` not
`Toxic/unsafe`; fix 15's two deliberately-out-of-scope rows still resolve
(`NCT01546987` `Business reasons`, `NCT00378534` `Ineffective for purpose`); both
`manual.json` branches still fire (`NCT01076764`, `NCT04255433`). The rebuild reproduced
generation 4 exactly: against `work/sidecar_g3_snapshot.csv`, 10 rows differ, every one
attributable — 4 to the outcome-table change, 4 to fixes 13-15 removing false
`Ineffective for purpose` calls, 2 to fix 12 and the external override.

### External search, run 3 (§11)

**Two programmes attempted, one resolved, three trials gained.** Unresolved failure-set
rows were ranked by §11's criteria (industry sponsor, later phase, larger enrolment,
terminated over withdrawn) and only the top of the list was worked.

* **Resolved — Bayer Trasylol (aprotinin), 3 trials.** `NCT00327379`, `NCT00306137`,
  `NCT00306150`: all three have a blank `whyStopped` and nothing on record anywhere in
  the pipeline's sources. Bayer announced on 2007-01-25 that it was discontinuing the
  Trasylol programme in non-CABG indications, naming **exactly three** studies — spinal
  fusion, pneumonectomy/esophagectomy, cystectomy — which match these three trials'
  titles one for one. All three terminated with a completion date of 2007-03. Recorded
  `Business reasons` at **Low** confidence as a programme-level attribution.
  The announcement explicitly denies a safety basis, and the two events that would
  suggest `Toxic/unsafe` — the BART mortality signal (2007-10-17) and the worldwide
  sales suspension (2007-11-05) — both *post-date* the termination, so the safety
  reading is ruled out by date as well as by the source.
* **Not resolved — Endo octreotide implant, 1 trial.** `NCT00765323` terminated with an
  end date of 2011-06; Endo's decision to discontinue the acromegaly implant programme
  is well documented but dated 2011-11-11, **five months after the trial ended**. The
  §11 date check kills an otherwise well-sourced attribution, exactly as it did in run 2.
  The row stays `Unknown`. (The sibling trial the search surfaced, `NCT01295060`, needs
  no external source: its own `whyStopped` says *"Program was terminated for business
  reasons"* and it already resolves `High` from the registry.)

Net effect of run 3: `Unknown` 259 → 256, `Business reasons` 437 → 440, 3 rows changed
and no others.
