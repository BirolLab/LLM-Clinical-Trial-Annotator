# Trial-outcome annotation — method

A reusable method for turning a corpus of per-trial markdown bundles into a
trial-outcome table. It is written to be run against any such corpus, not one
particular release: nothing below depends on the size of the input, on the drug
class, or on a labelled subset existing.

## 1. The task this method performs

Given a `bundles_chunks/` directory of `chunk_*.md` files, each containing one
`# NCT…` heading per study, decide **the outcome of that trial** and record the
text the decision rests on.

| column | meaning |
|---|---|
| `NCT Number` | ClinicalTrials.gov identifier, one row per `# NCT…` heading, source order |
| `Outcome` | `Positive` \| `Failed - completed trial` \| `Terminated` \| `Suspended` \| `Withdrawn` \| `Active` \| `Unknown` |
| `Confidence` | `High` \| `Medium` \| `Low` |
| `Evidence` | the specific sentence or field the call rests on, with its source; every `Low` row is prefixed `LOW CONFIDENCE:` |

Label definitions:

* **`Positive`** — the trial's own report shows the drug was safely tolerated
  **and** the clinical endpoint(s) were met: met/achieved the primary endpoint,
  superiority, non-inferiority met, a significant improvement on the trial's own
  outcome measure, or — for a safety/tolerability-primary trial — acceptable
  tolerability. Also the default call defined in §7.
* **`Failed - completed trial`** — the trial ran to a report and that report is
  negative: the drug was not safely tolerated, **or** the clinical endpoint was not
  met. It is a *reported* failure, so it is reserved for trials that were not stopped
  early — in practice registry status `Completed` or `Unknown`. `Evidence` names the
  registry status alongside the failing sentence, so the "completed" half of the label
  is auditable rather than assumed.
* **`Terminated`**, **`Suspended`**, **`Withdrawn`** — the registry status itself,
  reproduced verbatim as the label. A trial stopped early, halted, or withdrawn before
  enrolling is recorded as what happened to it; no attempt is made to decide whether
  the stop reflects on the drug.
* **`Active`** — the trial is still underway: `Recruiting`, `Not yet
  recruiting`, `Active, not recruiting`, `Enrolling by invitation`.
* **`Unknown`** — nothing on record settles the outcome. `Evidence` records what
  was searched, so the row is auditable rather than merely blank.

Two framing rules that change many individual calls:

**The call is about the trial, not the drug.** A trial of a drug later approved is
`Failed - completed trial` if *that trial* missed its endpoint; a trial of an
abandoned drug is `Positive` if *that trial* met its endpoint. Never reason from
what the molecule eventually became.

**Work from located text, never from recall.** Every non-`Unknown` row must be
traceable to a sentence or registry field quoted in `Evidence`. If no such text was
found, the row is `Unknown` — that is a valid answer, not a failure to try.

### A note on collapsing

The four failure situations a reader cares about — a trial stopped early, a trial
halted mid-flight, a trial withdrawn before enrolling, and a trial that ran to a
report and missed its endpoint — are four separate labels, not one. Nothing is
collapsed across them, so no filtering is needed to tell them apart.

One collapse remains, and it is inside `Terminated`/`Suspended`/`Withdrawn`: a stop
for "lack of funding" and a stop for toxicity carry the same label. That split is
administrative-versus-substantive, it cannot be read off the status field, and it is
kept recoverable by quoting `whyStopped` verbatim in `Evidence` for every stopped row
(§4).

A second thing worth stating plainly: these labels are **not** a two-way
success/failure axis. `Positive` and `Failed - completed trial` are the two outcomes
of a trial that reported; the three stop labels are facts about the trial's conduct;
`Active` and `Unknown` are not outcomes at all. Any downstream count of "failures"
has to say which of the five it means.

## 2. Read the corpus shape before designing anything

Do this first, on every new dataset. Census the headings:

```
grep -h '^#' bundles_chunks/chunk_*.md | sort | uniq -c | sort -rn | head -40
```

In the reference corpus each trial carries only two kinds of section — a
`## Molecular evidence` section (ChEMBL / UniProt / PDB / IntAct / IUPHAR records
for the drug and its target) and a `## Literature (n)` section of linked publication
abstracts.

**The consequence is the single most important fact about this method: the bundles
contain no trial-status and no results field.** The `Unknown`/`Completed` partition
the task names cannot be read off the files at all, and neither can
`Terminated`/`Suspended`/`Withdrawn` — which, under the vocabulary in §1, are three
of the seven output labels and not merely a routing step. Those must come from the
registry. Confirm
this on any new corpus rather than assuming it — if a future bundle does carry a
status field, prefer it and skip the status fetch.

`## Molecular evidence` is never outcome evidence. It describes the compound and its
target, not what happened in the trial. Parse it out and ignore it; feeding it to a
keyword scorer produces confident nonsense.

## 3. Evidence sources, in order

Consult in this order and **use a later source only where every earlier one yielded
nothing**. This is both an accuracy rule (the bundles are the task's primary source)
and the main cost control.

1. **Registry status** — overall status, `whyStopped`, phases. Settles
   `Terminated`, `Suspended`, `Withdrawn` and `Active` outright, with no text
   analysis at all — four of the seven labels, and the label *is* the status.
2. **`## Literature` abstracts in the chunk files** — the primary outcome source.
3. **Publications the registry lists for the trial** — `RESULT` type (the sponsor's
   own results paper) and `DERIVED` type; abstracts fetched by PMID.
4. **Registry posted results** — primary-outcome statistical analyses, adverse-event
   group totals, deaths, limitations-and-caveats text.
5. **Literature full-text search on the NCT ID** — catches result papers that cite
   the registration number in the body rather than the abstract.

Expect sharply diminishing returns down this list: in the reference corpus source 5
decided well under 1 % of rows. Run it anyway for the trials nothing else resolved,
but do not expect it to rescue them.

## 4. Status decides four of the seven labels

Read straight off the registry; nothing overrides it.

| registry status | label | confidence |
|---|---|---|
| `Terminated` | `Terminated` | High |
| `Suspended` | `Suspended` | High |
| `Withdrawn` | `Withdrawn` | High |
| `Recruiting`, `Not yet recruiting`, `Active, not recruiting`, `Enrolling by invitation` | `Active` | High |
| `Completed`, `Unknown` | resolve with §5–§7 | — |

This is free accuracy and should never be second-guessed by a publication. A trial
whose registry entry says `Terminated` is a terminated trial, whatever a paper about
it reports.

**Quote `whyStopped` verbatim in `Evidence` for every stopped row.** The task's
records every stop under its own status label, including stops that say nothing
about the drug — "lack of funding", "slow enrolment", a sponsor dissolving, a PI leaving. That
is the specified behaviour, but it conflates administrative with drug-driven
failure. Quoting the reason verbatim is what makes the two separable afterwards by
filtering `Evidence`, so the conflation costs the downstream reader nothing.

A stop label is never upgraded to `Failed - completed trial`, and
`Failed - completed trial` is never applied to a trial whose status is a stop: the
two are mutually exclusive by construction. A terminated trial with a published paper
reporting a missed endpoint stays `Terminated` — the status is the harder fact, and
the paper's finding is still in `Evidence` for anyone who wants it.

## 5. Turning a publication into a call

### 5.1 Normalise the text first

Abstracts from literature APIs carry HTML: `<h4>Results</h4>`, `<h4>Conclusions</h4>`.
Left in place this breaks sentence splitting *and* hides the conclusion marker, so
the conclusion zone silently falls back to "last three sentences" and lands in the
wrong section. Convert section headings to sentence leads and strip remaining tags
before anything else touches the text.

### 5.2 Relevance gate — is this paper about *this* trial?

A paper is used only if it plausibly reports this trial. Score:

| signal | weight |
|---|---|
| abstract names the NCT ID | +4 |
| trial-design language (randomised / double-blind / placebo-controlled / phase / primary endpoint …) | +2 |
| registry-declared `RESULT` reference | +5 |
| registry-declared `DERIVED` reference | +2 |
| review-type title | −3, or −6 if the title says "review" or "meta-analysis" |
| review-type body language | −3 |
| abstract lists ≥4 NCT IDs (a pooled report) | −2.5 |

Papers scoring **< 2** are not used. Abstracts shorter than ~120 characters are not
used — a stub cannot establish an outcome.

Excluded outright, whatever they score: meta-analyses, systematic / narrative /
scoping reviews, pooled analyses, post-hoc / secondary / subgroup analyses, in-vitro,
ex-vivo and animal studies, method and assay validation papers, case reports, study
protocols, design papers, cost-effectiveness and claims analyses, and **reviews of
ongoing trials** ("…in ongoing clinical trials: status", "trials in progress",
pipeline/landscape surveys). None of these establishes the outcome of one trial.

Also exclude **pooled multi-trial reports** detected by phrasing rather than by NCT
count — "Among 20 FDA-reviewed registrational trials, 10 (50 %) failed to meet this
endpoint" is a survey, and without this rule it fails 20 trials at once.

### 5.3 Zone order — where in the abstract to look

Within the chosen paper, scan sentences in this order and let **the first zone with
any signal decide**:

1. sentences stating a **primary endpoint** result;
2. the **conclusion** — text after the last `Conclusion(s)` / `Interpretation` /
   `In summary` marker, else the final three sentences;
3. the **results** half of the abstract.

Zone 3 is materially less reliable than 1–2 and every call made there is `Low`.

### 5.4 Sentence filters

Skip sentences that describe methods, background, objectives and aims, baseline
characteristics, demographics, inclusion/exclusion criteria, prior literature, calls
for further research, author opinion, and animal experiments.

Skip **exploratory, subgroup, post-hoc and sensitivity** findings, so that a failed
primary endpoint is never overridden by a positive subgroup.

Skip a sentence that only **defines** the endpoint. "The primary end points were
dose-limiting toxicity and immune response" is a methods statement that happens to
contain a toxicity keyword; read as a result it fails a trial that reported none.
Allow the sentence through only if it also carries a result verb — met, achieved,
missed, not met, failed, significant, a p-value, superior, non-inferior, futility.

Skip a sentence whose **subject is a biomarker or analyte level** — a hormone,
cytokine, lipid, bone-turnover marker, receptor occupancy, gene expression — unless
it is itself a primary-endpoint statement. Require the analyte in subject position
(roughly the first 45 characters) so that a clinical sentence merely mentioning a
biomarker later is not discarded.

Drop a clause introduced by *whereas / while / although / though*, which normally
describes the comparator arm rather than the drug.

### 5.5 Polarity

Six keyword families are matched per surviving sentence:

| family | weight |
|---|---|
| negative-endpoint | 3.0 |
| negative-safety | 2.5 |
| negative-efficacy | 1.6 |
| positive-endpoint | 3.0 |
| positive-safety | 1.4 |
| positive-efficacy | 1.0 |

Endpoint families outweigh efficacy families deliberately: an explicit statement
about the registered endpoint is better evidence than a directional adjective.

Sum the per-sentence weights across the zone; the sign of the total decides, and the
largest-magnitude single hit is what gets quoted in `Evidence`.

### 5.6 The five corrections

Each of these exists because its absence produced wrong calls that were caught by
hand-reading. Expect to need all five on any new corpus.

1. **Negation guard.** A directional phrase preceded by *no / not / without /
   neither / nor / lack of / absence of / never / none* within ~26 characters flips
   sign, so "with **no apparent increased risk** of hypoglycaemic episodes" counts as
   positive safety rather than negative. Skip the guard for patterns that already
   contain their own negation, or they flip twice. **Relabel the family when it
   flips** — otherwise `Evidence` reports a `Positive` row under a
   `negative-safety` signal and contradicts itself on its face.

2. **Safety-context routing.** In a sentence whose subject is adverse events,
   tolerability, hypoglycaemia, discontinuation or mortality — and not efficacy —
   "no significant difference" / "comparable" / "did not differ" means *tolerated*
   (positive), while "significantly higher" means *not tolerated* (negative).
   **This must never apply to a primary-endpoint sentence.** "There was no
   significant difference between the two groups in any component of the primary
   outcome or in the rate of death from any cause" mentions death, but it is a
   missed primary endpoint, not a tolerability finding; without the exception it
   reads as a confident `Positive`.

3. **Phase weighting.** In a trial that is Phase 1 (or Phase 1/2) and not Phase 3,
   the primary endpoint *is* safety: weight safety signals ×1.8 and efficacy
   signals ×0.8.

4. **Direction check.** "Greater / higher / increased / more / elevated" is
   direction-blind — whether it is good news depends on what rose. Drop a positive
   hit whose object within the next ~70 characters is a worse clinical state
   (hyperglycaemia, mortality, risk, adverse events, toxicity, impairment,
   progression, relapse, pain, exacerbation, hospitalisation, complications,
   infection) and is not a good one (improvement, reduction, weight loss, control,
   response, remission, survival, clearance, cure). "Resulted in greater
   postprandial glycemia" is not positive efficacy. Dropping to neutral is safer
   than flipping: the zone then yields no signal and the scan moves on.

5. **Equivalence re-reading.** In a pharmacokinetic / pharmacodynamic /
   bioequivalence / biosimilar / equivalence study, the *absence* of a significant
   difference is the intended result, so score it `Positive` and say so in
   `Evidence`. Match the no-difference phrasing **against the whole sentence, not
   the narrow keyword hit** — "no statistically significant" does not itself contain
   the word "difference", so a narrow test misses the very case the rule exists for.

### 5.7 A failure call needs endpoint-level evidence

When the negative weight wins, label `Failed - completed trial` **only if** the
decisive signal is
from the negative-endpoint family — "did not meet the primary endpoint",
"non-inferiority was not met", "stopped for futility", "was not superior to" — or
the decisive sentence is itself a primary-endpoint statement.

A win carried only by generic negative-efficacy wording — "did not differ", "no
significant difference", "no effect on" — is **not enough**: move on to the next zone
or the next paper instead. Generic no-difference wording in an abstract is far more
often a secondary measure, a safety comparison or an equivalence result than a failed
trial, and treating it as a failure is the largest single source of false
`Failed - completed trial` calls.

### 5.8 A sub-study may support a trial but never fail one

A paper that measures something other than the registered endpoint — plasma or serum
hormone levels, bone-turnover markers, gastric emptying, gallbladder volume,
receptor occupancy, signalling, immunogenicity, metabolomics, or anything whose title
frames it as mechanistic, exploratory, or "as a probe of" — is allowed to support a
`Positive` call but is **never** allowed to produce a failure call.

Apply the gate when any of three hold:

1. the title alone establishes it is not a clinical endpoint paper (probe / receptor
   occupancy / mechanistic / proof of mechanism);
2. the title is biomarker/physiology-shaped *and* the abstract is in healthy
   volunteers *and* no clinical endpoint is named in the title;
3. the title frames the paper as an **association, correlation or prediction** —
   "X is (not) associated with Y", "correlates with", "predicts", "as a marker /
   predictor / surrogate of", or an epigenetic / methylation framing — *and* no
   clinical-endpoint vocabulary appears in the title. This one is population-blind on
   purpose: condition 2 requires healthy volunteers and so misses association papers
   written on the trial's own patients.

Without this, sentences like "dulaglutide showed no effect on plasma renin" become
trial outcomes. Condition 3 exists because a methylation-clock sub-study of a heart
failure trial — "Epigenetic age acceleration is not strongly associated with
cardiorespiratory fitness" — failed that trial on a sentence about whether a
biological-age estimate predicted VO2. Requiring the clinical-endpoint vocabulary to
be *absent* is what keeps a titled randomised efficacy report out of the gate; and
because the gate only ever blocks a failure call, a paper it catches wrongly still
costs nothing.

## 6. Posted-results fallback

Used when no publication is usable.

If primary-outcome analyses carry **p-values**, follow the proportion reaching
p < 0.05: none significant → `Failed - completed trial`; otherwise → `Positive`. Quote
the outcome-measure title and the p-values, plus serious-AE and death counts.

**Except where the primary outcome is itself a harm measure** — toxicity of any organ
class, adverse events, toxic effects, dose-limiting toxicity. There the
direction-blindness below is not a caveat but a reversal: a significant difference in
a toxicity endpoint is as likely to mean more toxicity as less, so the p-value
proportion cannot support a `Positive` at all. Skip the p-value branch entirely for
these and let the adverse-event rate decide. A nephrotoxicity primary with
p = 0.0002, 42 % serious adverse events and 60 deaths was being called `Positive`
before this rule.

These rows are **always `Low`**, for a reason worth stating plainly: the registry
records significance but not **direction**, so a significant result favouring the
comparator is indistinguishable from one favouring the drug. Quote the numbers so
each row can be checked by hand.

If no p-values are posted but the primary outcome is itself a safety, tolerability
or PK measure, follow the serious-AE rate: < 15 % and no deaths → `Positive`;
≥ 50 %, or ≥ 30 % with deaths → `Failed - completed trial`. **Leave the mid-band uncalled** — it
becomes `Unknown` or falls to §7.

When the at-risk denominator is not posted, report the bare count rather than an
"n/a" fraction; `Evidence` is read by people.

## 7. The default-positive convention

A trial that reached `Completed`, has a publication or posted-results trail, and has
**nothing on record reporting a missed endpoint, an early stop or a safety failure**
is labelled `Positive` — not from a located outcome statement, but by convention.

The justification is publication bias, and it is a property of how trials are
reported rather than of any one dataset: sponsors publish trials that worked far
more often than trials that did not, so "completed, published, nothing says it
failed" carries real information. Withholding a label there is not neutral — it is
systematically wrong in one direction. Expect this convention to decide a large
share of rows (about 30 % of the reference corpus); it is the method's biggest single
assumption and should be reported as such.

Apply it narrowly, under two conditions:

* **Status `Completed` only.** A status of `Unknown` means the registry entry was
  abandoned rather than closed out, which is not evidence that anything succeeded.
* **A trail is required** — at least one candidate publication, one registry-listed
  reference, or posted results. A completed trial with no paper trail at all keeps
  `Unknown`.

Make it fully reversible. Every such row carries `Confidence = Low` and an
`Evidence` string that says in words "scored Positive by convention, NOT from a
located outcome statement", so the stricter reading is recoverable by filtering
`Evidence`, or by re-running with the convention switched off.

**Re-validate both conditions on each new dataset** rather than inheriting them.
They are coarse by design — two conditions, no tuned numbers — but they are the
method's main lever, and the no-trail condition in particular is close to a coin
flip and could reasonably fall the other way on a differently-sourced corpus. If any
labelled rows are available, check the `Completed`-with-no-trail subset directly:
extend the convention only if positives clearly outnumber unknowns there, and bear
in mind that extending it converts a large block of rows into unverifiable
`Positive`. With no labelled rows, leave the conditions as specified and say in the
run notes that they are unvalidated.

## 8. Confidence

| | |
|---|---|
| **High** | registry status alone decides it — the four status labels `Terminated`, `Suspended`, `Withdrawn`, `Active`; **or** the paper names the NCT ID or is the registry-declared results paper, **and** the decisive signal is an endpoint or safety statement in the primary or conclusion zone with one polarity clearly dominant |
| **Medium** | a relevant paper's conclusion decides it, but either the paper does not name the trial or the signal is generic-efficacy wording rather than an endpoint statement |
| **Low** | the call rests on the results half of an abstract, on a weak or mixed signal, on an equivalence re-reading, on registry p-values of unknown direction, or on a safety-only read — **and** every convention row and every `Unknown` row |

Prefix every `Low` row's `Evidence` with `LOW CONFIDENCE:` so the flag survives
being pasted into a spreadsheet, a slide, or a downstream join that drops columns.

## 9. Validation

Agreement against a labelled subset, where one exists, is the strongest check — but
it is not available on a new dataset and it is not sufficient on an old one. The
checks below are the ones that found real errors, in the order they are cheapest to
run.

### 9.1 Audit the patterns for inert regexes — after every edit

This is mandatory, not optional. Count corpus matches for each individual pattern and
flag any with zero. **A zero means the pattern is broken, not that the phrase is
rare.** The classic cause is a `\b` placed after a stem or at the end of an
alternation: `)\b` after `…|no difference)` can never match "difference**s**", and
the whole alternation silently stops firing. Several filters have been found dead
this way, each one invisible in the output and each one costing accuracy with no
error message.

Re-run the audit after any change to the keyword families, and investigate every
low-count pattern rather than only the zeroes.

### 9.2 Hand-read the evidence against the source abstracts

Sample in stratified rounds and read each `Evidence` string against the full source
abstract. Prioritise, in this order:

1. **`Failed - completed trial` calls decided by a publication** — the
   highest-stakes, lowest-volume
   class, and historically the most error-prone.
2. **`High`-confidence rows of any label** — a confident error is worse than a
   hedged one.
3. **Posted-results rows**, for direction and denominator sanity.
4. **`Positive` rows decided by a publication**, which are numerous enough that a
   systematic fault there dominates the output.

Keep going until a round surfaces no new *class* of error. Individual wrong rows will
always remain; what matters is that the round stops producing new failure modes.

### 9.3 Known trap classes — check each explicitly on a new corpus

Every one of these produced confidently wrong rows during development. Treat the list
as a regression suite.

| trap | what it looks like |
|---|---|
| HTML section markup | `<h4>Results</h4>` hides the conclusion marker and breaks sentence splitting |
| endpoint-definition sentences | "The primary end points were dose-limiting toxicity and immune response" read as a toxicity finding |
| pooled multi-trial reports | "Among 20 trials, 10 failed to meet this endpoint" fails 20 trials at once |
| reviews of ongoing trials | pipeline/landscape surveys scored as trial reports |
| narrow-scope equivalence test | the no-difference check run against the keyword hit instead of the sentence |
| direction-blind positives | "resulted in greater postprandial glycemia" scored as positive efficacy |
| safety routing over a primary endpoint | "no significant difference in any component of the primary outcome or in the rate of death" scored `Positive`, `High` |
| biomarker subject sentences | a hormone-level sentence deciding a trial |
| unrelabelled negated families | a `Positive` row whose `Evidence` cites a `negative-safety` signal |
| inert `\b` | a filter that silently never fires |
| benign discontinuation wording | "patients discontinued because of adverse events" read as a halted trial |
| missing at-risk denominator | `Evidence` printing "2/0 (n/a)" |
| association/prediction sub-studies | "epigenetic age acceleration is not associated with cardiorespiratory fitness" failing the trial it was nested in |
| significant harm primary | a nephrotoxicity primary outcome with p = 0.0002 read as a met endpoint |

### 9.4 Invariants on the finished table

Assert all of these before shipping; they are cheap and they catch assembly bugs that
no amount of reading will:

* exactly one row per `# NCT…` heading, in source order, no duplicates;
* every NCT ID well-formed;
* no empty cell in any column;
* `Outcome` and `Confidence` drawn only from their declared vocabularies;
* every `Low` row's `Evidence` carries the `LOW CONFIDENCE:` prefix;
* every non-`Unknown` row's `Evidence` names a source;
* every `Terminated`/`Suspended`/`Withdrawn` row's `Evidence` quotes the registry
  status it was taken from, and no row carries one of those labels without it;
* no `Failed - completed trial` row sits on a stopped registry status, and no stopped
  registry status produces any label but its own (§4) — the one invariant the new
  vocabulary adds, and the one an off-by-one in the status map would break silently.

### 9.5 If a labelled subset exists

Use a chance-corrected agreement statistic rather than raw accuracy — the label
distribution is lopsided, and raw accuracy flatters a method that just says
`Positive`. Then, before reading the number:

* **Join on the intersection.** Labelled identifiers that are not in the corpus
  cannot be labelled by any method applied to it. Scoring them as a miss, or as an
  extra category, depresses the figure dramatically and measures corpus coverage
  rather than method quality. Report coverage separately.
* **Check the annotators against each other first.** Human–human agreement is the
  ceiling, and it is often lower than expected. A systematic difference between two
  annotators — for instance one treating `Completed` trials as still active — caps
  any score against that annotator and tells you nothing about the pipeline.
* **Report agreement per decision source**, not just overall. Status-decided,
  publication-decided, posted-results-decided and convention-decided rows have very
  different accuracy, and the overall figure hides which part needs work.
* **Do not tune on a small labelled set.** A few hundred rows is enough to detect a
  gross vocabulary or convention error and not enough to justify a threshold. Prefer
  changes that are also justified by reading the evidence; treat a change that only
  helps the score as unvalidated.

## 10. Known limits of what these sources can establish

State these in the run notes every time; they bound what the table can be used for.

* **Completed-trial failures are under-detected.** A trial that quietly missed its
  endpoint, posted no results and has no linked paper reporting the miss is
  indistinguishable from a success by these sources, and the convention in §7 will
  call it `Positive`. The `Failed - completed trial` count is a **lower bound**, not
  a count of failed trials. The stop labels are not affected — they come from the
  status field and are as complete as the registry is.
* **Registry p-value rows have unknown direction** (§6).
* **No-trail completed trials stay `Unknown`** by design (§7); this is the largest
  deliberate disagreement with a human reader, who will often call them positive.
* **Convention rows are an assumption, not a finding.** Report how many there are
  as a headline number, not a footnote.
* Any row intended for a downstream decision should be read against its `Evidence`
  string; `Low` rows are provisional.

## 11. Cost discipline

The method is designed to stay cheap, and the ordering in §3 is most of it.

* **Fetch for unresolved trials only.** Sources 3–5 are driven off the unresolved set
  from the previous classify pass, so each one touches a strictly smaller set.
* **Batch registry and literature queries** — tens of IDs per request, not one.
* **Make every fetch resumable and cached**, keyed by NCT ID or PMID: re-running
  after an interruption must not re-request anything, and classification is re-run
  many times while fetches are not.
* **Request only the fields needed.** Full study records are large; status, phases,
  references, primary-outcome analyses and AE totals are small.
* **Keep classification offline and fast.** It should run in well under a minute
  over the whole corpus, because it will be run dozens of times during validation.
  Never put a network call inside the classifier.

## 12. Pipeline

```
outcome_pipeline/
  parse_lit.py       # ## Literature sections out of bundles_chunks/chunk_*.md
  fetch_status.py    # registry: status, whyStopped, phases, hasResults, references
  fetch_detail.py    # registry: primary-outcome analyses, AE totals, caveats
  fetch_extra.py     # abstracts for registry-listed RESULT/DERIVED references
  fetch_epmc2.py     # literature full-text search on the NCT ID (unresolved only)
  patterns.py        # the six keyword families + relevance/exclusion lexicons
  classify.py        # normalise, relevance gate, zone order, polarity, labelling
  assemble.py        # writes the output CSV
  audit_patterns.py  # corpus match count per pattern; catches inert regexes
  score.py           # agreement against a labelled subset, if one exists
```

Run order — the two later fetch stages read the unresolved set from a prior
classify pass, so classify runs three times:

```
parse_lit → fetch_status → fetch_detail → classify
          → fetch_extra  → classify
          → fetch_epmc2  → classify → assemble
```

Pointing it at a new dataset:

| variable | meaning |
|---|---|
| `BUNDLES` | the `bundles_chunks` directory to parse |
| `OUTCOME_WORK` | directory for intermediate `work/` files and caches |
| `OUTCOME_CSV` | output CSV path |
| `EPMC_BY` | which decision sources to re-search in the full-text stage |

Method switches, all defaults on, for ablation and for recovering a stricter table:

| switch | effect |
|---|---|
| `OUTCOME_OFF=k5` | drop the default-positive convention; those rows become `Unknown` |
| `OUTCOME_OFF=k3` | drop the endpoint-level requirement for failures and the sub-study gate |
| `OUTCOME_OFF=k4` | drop safety-context routing |
| `OUTCOME_ON=k7` | loosen the relevance gate for full-text hits |

Measure any switch before trusting it. Two that look obviously helpful were measured
and **left off**: loosening the relevance gate for full-text hits (it adds calls
without adding agreement), and letting a publication override `Active, not
recruiting` status.

## 13. Checklist for a new dataset

1. Census the headings; confirm what the bundles do and do not contain (§2).
2. Confirm whether a status field exists; if not, fetch it (§2–§3).
3. Parse literature; count trials with and without any abstract.
4. Fetch status; tabulate the status distribution and note how many trials status
   alone resolves.
5. Run classify; check the decision-source breakdown is plausible before reading any
   label counts.
6. Run the pattern audit (§9.1).
7. Hand-read in stratified rounds until no new error class appears (§9.2–§9.3).
8. Re-validate the §7 conditions; if unvalidatable, say so.
9. Assert the §9.4 invariants.
10. Write run notes recording the counts, the decision-source breakdown, the defects
    found and fixed, and the §10 limits.

Per-run results, counts and measurements belong in a dated notes file beside the
output, not in this document.
