# Failure-reason annotation — method

A reusable method for turning a corpus of per-trial records, plus a table that says
which of them failed, into a reason-for-failure table. Nothing below depends on the
size of the input, the drug class, the registry release, or on a labelled subset
existing.

The method is written for clinical-trial registries, and §4–§7 name registry fields
directly. The parts that carry most of the score are not registry-specific: the row
scope (§1.1), the vocabulary discipline (§1.2), the evidence-tier cascade (§4), the
status-conditioned prior (§7.2), and the validation and diagnosis order (§10) all
transfer to any task of the form "say why each of these things failed, from whatever
text is on record".

**On the numbers quoted in this document.** Figures in *italic callouts* are
observations from past runs, never requirements. They are there so a new run can tell
a plausible result from an implausible one. Unless a callout says otherwise, the runs
recorded here were made against **one corpus and one label file**, at two pipeline
generations — labelled *Run 1* and *Run 2* below. A figure that appears in both is a
re-measurement, **not** an independent replication, and nothing here has been validated
on a genuinely different dataset. Treat every number as calibration from a single
setting and re-measure it on yours; §15 collects the headline figures in one table for
exactly that comparison.

## 0. Inputs — fix these before reading further

This method has seven inputs. Name them explicitly at the start of a run, record the
answers in the deliverable's notes, and do not let them drift afterwards. Most of the
expensive mistakes in §1 and §10 are an input that was assumed rather than checked.

| # | input | what it is | where it bites |
|---|---|---|---|
| 1 | **corpus** | the per-trial records you were pointed at: a directory, one or more files, one record per trial under some identifier | §2 — census it; it probably does not contain the stop reason |
| 2 | **registry** | the authoritative source of status and the stated stop reason, reachable by identifier | §2, §4, §4.1 — validate the field list before batching |
| 3 | **outcome determination** | whatever says which trials had a negative outcome: an upstream outcome table, a status rule, or nothing | §1.1 — the reason is **scoped to negative trials** but must not be **keyed** to one fallible label; §3 — it may be coarser than the task needs |
| 4 | **label set** | an annotated subset, if one exists, with its own identifier case and its own spelling of the reasons | §1.2, §10.5 — take identifiers for coverage, never labels for selection |
| 5 | **target vocabulary** | the exact reason strings that will be scored, and whether a residual class exists | §1.2 — the requester's prose and the label file routinely disagree |
| 6 | **output schema** | the columns the requester asked for, in their spelling | §1 below — the deliverable follows the request; extras go in a sidecar |
| 7 | **scoring metric** | the statistic that will be computed, over which rows, and what it does with rows an annotator left blank | §1.2 — **it decides whether to emit a residual label at all**; §10.5 |

**Input 7 is the one most likely to be missing, and it changes the answer.** Ask for it
explicitly. "How will this be scored?" is not a process question; two reasonable metrics
pull the residual-label decision in opposite directions, and no amount of rule work
compensates for getting it wrong (§1.2). If the requester cannot say, assume a
chance-corrected agreement over all rows — it is the stricter of the two — and ship the
table so that **either** metric can be computed from it without a re-run.

Write the answers down in this form, in the run's notes:

```
corpus            <path / glob>, <n> records, identifier = <field or heading pattern>
registry          <API + version>, fields validated on <date>
failure signal    <table + column + value> | <status rule> | none
label set         <path>, <n> rows, id case = <lower|upper>, reason column(s) = <...>
vocabulary        <exact strings, in the target's spelling>; residual class: <yes|no>
output schema     <column list, in the requester's spelling>
scoring metric    <statistic> over <which rows>; blank gold rows: <scored|excluded>
```

## 1. The task this method performs

Given the **corpus** of input 1 and the **failure signal** of input 3, decide **why
each failed trial failed** and record the text the decision rests on.

The deliverable carries the columns the requester asked for, spelled their way
(input 6). The method needs five things recorded per row; where the requested schema
has no column for one of them, it goes in a sidecar table keyed by the same identifier
rather than being dropped:

| role | meaning |
|---|---|
| identifier | the registry id, upper-cased; §1.1 decides which trials get a row |
| reason | one of the target's buckets, spelled exactly as the target spells it (§1.2) |
| confidence | `High` \| `Medium` \| `Low` (§9) |
| basis | which evidence source decided the row, or `NONE - …` where no reason was on record (§4, §1.1) |
| evidence | the specific field or sentence the call rests on, with its source; every `Low` row is prefixed `LOW CONFIDENCE:` |

Carry the registry status and the upstream failure signal as columns too, in the
sidecar if not in the deliverable. They cost nothing, and every downstream question —
"score only the stopped trials", "filter to the rows the upstream table called
failures" — otherwise needs a re-join.

Throughout the rest of this document these roles are referred to by the names the
reference implementation gave its columns — `Basis`, `Evidence`, `Confidence` — because
the rules are easier to state against a concrete name. Read them as the roles above,
whatever your schema calls them.

**If `Basis` has no column in the requested schema, the deliverable must still be
filterable on its own.** Make each `NONE` class a fixed, greppable opening phrase in
the `Evidence` string, and say in the notes which phrase selects which class. Mark the
rows that located real text but that nothing upstream calls a failure too — they carry
no `NONE` marker of their own, and without a marker the deliverable cannot be filtered
back to the failure set at all. A reader
who cannot separate findings from base rates will aggregate the two together, and the
reason column read raw is then badly misleading (§1.1).

The bucket names used throughout this document are **the vocabulary of the corpus this
method was built against, used here for discussion only**. §1.2 is how you find the
ones that will actually be scored. The definitions, however, port:

* **`Recruitment issues`** — the trial could not enrol or retain the participants it
  needed: slow, poor, low or insufficient accrual; target sample size not reached;
  no eligible patients; screen-failure rate; loss to follow-up.
* **`Business reasons`** — the residual bucket for every non-scientific,
  non-recruitment, non-pandemic stop. Funding withdrawn or exhausted; sponsor,
  strategic or portfolio decision; drug supply, expiry, manufacturing or product
  stability; protocol redesign, replacement or mis-registration; investigator or staff
  departure; regulatory and administrative holds; technical, assay or logistical
  failure; study never initiated.
* **`Ineffective for purpose`** — the **intervention** failed to do what it was tested
  for in humans: futility, lack of efficacy, primary endpoint not met, no significant
  difference on the trial's own outcome measure, superiority or non-inferiority not
  demonstrated.
* **`Toxic/unsafe`** — an explicit safety statement: toxicity, adverse events,
  mortality or morbidity, a safety signal, a safety-driven hold, intolerability.
* **`Due to COVID-19 pandemic`** — the pandemic is the cause named, not merely a
  factor present (§5.6).
* **residual (`Unknown`, or a blank cell)** — nothing on record gives a reason.
  Whether to emit it is a **metric** decision, not a vocabulary one, and §1.2a is the
  whole of it: under an accuracy computed only over rows gold labelled, emit the §7.2
  prior instead; under a chance-corrected agreement with blank as a category, emit the
  residual. Either way the "nothing was found" fact goes in `Basis` and `Evidence`, so
  the other choice stays one line away.

Four framing rules that change many individual calls:

**The reason is about this trial, not the programme.** A trial stopped because its
sponsor reorganised is a business stop even if the molecule was later shown to be
ineffective elsewhere. Never reason from what the drug eventually became.

**Work from located text, never from recall.** Every row whose `basis` is not `NONE`
must be traceable to a field or sentence quoted in `Evidence`. If no such text was
found, say so in `Basis` and `Evidence` — that is a valid answer, not a failure to try.

**A reason is owed only where the outcome was negative — but every row still gets a
decision.** These two are easy to collapse into each other and must not be. A trial
whose outcome was not negative gets the residual, not a bucket: naming why a trial
failed when nothing says it failed is incoherent however good the located text is.
A trial whose outcome *was* negative but where nothing was found also gets the residual
(or the §1.2a prior) — "no text was found" is a statement about the evidence, never a
reason to skip the row. What is never acceptable is a dropped row or an empty cell:
either scores exactly as badly as a missing row and looks correct on every audit that
does not join to the label file. §1.1 is the long form, and it is the most expensive
rule in this document to get wrong — in both directions.

**A failure bucket is not a judgement of the drug.** The business and recruitment
buckets say nothing about efficacy or safety; keep them clean of inference so that
downstream filtering on "scientific failure" is meaningful.

### 1.1 Which trials get a row, and which get a reason — two different questions

The obvious scope is "one row per trial the outcome table calls a failure". **That gate
is the single largest source of missing answers, and it is invisible in every quality
metric computed inside it.** Three leaks, in descending size:

* the evaluation set contains trials the corpus never covered, so they have no row in
  the outcome table to be selected by;
* the outcome table disagrees with the evaluation set about which trials failed — a
  trial scored as a failure upstream of you may be labelled positive, and a reason
  keyed to the upstream label can never reach it;
* an outcome vocabulary coarser than the evaluation's collapses distinctions the
  reason depends on, most often by having no way to say "ran to term and missed".

*Run 1: gating on the upstream failure label reached 22 of 68 labelled
failures; widening the scope as below reached all 68 and raised agreement from 63% to
85%, with no change to the rules themselves.*

So: **emit a row for every identifier in the outcome table, unioned with every
identifier in any evaluation or label set.** Three properties matter and all are easy
to lose.

**Selection must not consult a gold label.** Adding the trials a label file flags as
failures fits the scope to the answer key; the score stops predicting the held-out set.
Taking the *identifiers* from a label set is fine — that is just coverage. Taking its
*labels* to decide who gets a row, or which bucket they get, is leakage.

**A reason is only required for trials whose outcome is negative.** That is the task,
and it is not the same question as which trials get a row. Keep three decisions apart —
conflating any two of them produces a different bug, and this document has made both
mistakes in consecutive generations:

| decision | rule | the bug when it is wrong |
|---|---|---|
| which trials get a **row** | every identifier in the union of §1.1, selected on nothing | the join silently drops rows, and it is invisible in any metric computed inside the gate |
| which trials get a **reason** | only those whose outcome is negative — plus, see below, those with no outcome determination at all whose registry status says they stopped | rows asserting *why a trial failed* while also saying nothing calls it a failure |
| what every **other** row gets | the residual — `Unknown`, or the §1.2a prior — never an empty cell and never a dropped row | a row with no decision scores exactly as badly as a row that is missing |

**"Failure set"**, used throughout the rest of this document, means exactly the set in
the middle row of that table: the trials a reason is owed for — those whose outcome was
negative, plus any with no outcome determination at all whose registry status says they
stopped. It is a subset of the row set, never the row set itself, and the deliverable
should let a reader recover it without a re-join (§1).

So the bucket is conditional on two things at once, and that belongs in the invariants
(§10.4) because the failure mode is silent and reads as plausible:

> **A non-residual reason asserts both that this trial's outcome was negative and that
> text saying why was located. Emit one only when both hold.**

A located statement is evidence about a *sentence*, not about whether the trial failed.
For a trial that ran to term with a positive outcome, a paper reporting a missed
endpoint somewhere is not grounds for calling the trial a failure. Keep the statement —
quote it in `Evidence`, put its bucket in a sidecar column — so nothing is discarded and
the alternative reading stays derivable.

*Observed in Run 2, generation 3: running the §4 cascade over every row and letting any
located sentence set the bucket left **433 rows naming a failure reason while their own
`Evidence` said nothing upstream called the trial a failure**. Every table invariant
passed, the labelled score was unaffected, and the rows read as confident findings.
Restricting the bucket to negative-outcome trials took AC1 against the stricter
annotator from 0.927 to 0.947 over the whole label set — above the 0.908 human ceiling
— and changed nothing on the scored subset. It also removed a second defect (§6.1's
pooled-evidence trap) that those rows had been carrying.*

**But do not read "outcome is negative" as "the upstream table said Negative".** The
reason is scoped to negative trials; it must not be *keyed* to one fallible label for
them. Two consequences, and the first is the single most expensive finding in this
document:

* **An outcome table disagrees with the ground truth about which trials failed, and
  every such disagreement is a reason you can never reach.** The scope must therefore be
  the union of §1.1, and the reason must reach every trial in it whose outcome is
  negative *by any available determination* — not only the ones one table happened to
  mark. Where a trial has **no** outcome determination at all, fall back to registry
  status: a sponsor who terminated or withdrew a trial did so for a reason, and that
  reason is in scope.
* **Report the disagreement rather than absorbing it.** It caps the achievable score
  however good the rules get (§12), and the §5.3 non-failure count is the cheapest
  evidence that the upstream set is wrong.

*Run 2, measured: of the 69 labelled trials carrying a gold reason, 68 were gold-negative
on outcome, but the upstream outcome table called only 32 of them `Negative` — 11
`Positive`, 2 `Unknown`, and 7 absent entirely among the gold-ineffective slice alone.
Gating the reason on that table reached 37 of 69 and scored 52.2%; scoping it to
negative-outcome trials across the full row set reached 69 of 69 and scored 84.1%. Same
rules, same evidence, same priors — the rules measured 97.3% on the rows they reached
both before and after, so no amount of rule work could have recovered any of it.*

**Over-covering is free when the metric subsets; under-filling is not.** Rows for
trials that did not fail cost nothing and guarantee the join never silently drops to
null — but only if they carry a decision. A row marked "not a failure" with an empty or
residual reason is indistinguishable from a row you failed to reach, and it scores
zero whenever the evaluation disagrees with the upstream table about that trial. Fill
it with the prior and mark it: `Confidence = Low`, `Basis` beginning `NONE`, and an
`Evidence` string that opens by saying no failure is on record.

The cost of this is real and belongs in the notes: the reason column is now populated
for trials that in all likelihood did not fail, so the **table-wide** distribution of
reasons is not an estimate of anything. On the corpus above, 6,132 of 7,917 rows are
prior-filled non-failures, which drags the table-wide mix to 75.6% `Ineffective for
purpose` against 26.2% inside the failure set. Give the reader the one-line filter and
say plainly what happens without it; this is the one property of the table a reader can
misuse badly.

### 1.2 The label vocabulary is not yours to choose

The bucket names used throughout this document are for discussion. **Spell them in the
output exactly as whatever scores the table spells them.** A requester's prose and their
label file routinely disagree — singular against plural, `Due to COVID-19
pandemic` against `due to covid`, title case against lower — and a merge that maps
unrecognised strings to null turns a working annotation into a column of blanks. Diff
the two before writing a row, and when they clash, ask which one is authoritative
rather than guessing.

*Run 1: the requester's own prose listed an `Unknown` bucket, but the
label set never used one — annotators left the cell blank on 7 of 75 failed trials
instead. Re-measured in Run 2 against both annotators, the reason column took exactly
five distinct values per annotator — `business reason`, `ineffective for purpose`,
`recruitment issues`, `due to covid`, `toxic/unsafe` — and never a residual. Note also
that the requester's prose spelled the buckets title-case and plural (`Business
reasons`, `Due to COVID-19 pandemic`) where the label file is lower-case and singular
(`business reason`, `due to covid`): ship the spelling the requester asked for, and put
the conversion map in the notes rather than silently choosing one.*

### 1.2a The residual label is a metric decision, not a vocabulary decision

**A blank cell in the label file is not the absence of an answer. It is an answer —
"no reason is recoverable" — and whether you should give the same answer depends
entirely on input 7.** Getting this backwards costs more than every rule in §5
combined, and it is invisible unless you compute the metric the requester is actually
computing.

Two metrics, pulling opposite ways:

| metric | what it does with blank gold rows | what you should emit where no text was located |
|---|---|---|
| **accuracy on labelled rows** — "of the trials gold gave a reason, how many did we get right" | excludes them | the **§7.2 prior**. Blank-gold rows are not scored, so a guess there is free, and a prior beats a residual on every row that *is* scored |
| **chance-corrected agreement over all rows** — AC1, κ, with blank as a category | **scores them, and the annotators agree with each other on them often** | the **residual label**. A row where both annotators wrote nothing is agreement you forfeit permanently by always asserting a reason |

*Measured in Run 2 — identical rules, identical evidence, one column changed:*

| what the table emitted where no text was located | AC1, scored subset (n=32) | AC1, whole label set (n=488) | accuracy on labelled rows (n=69) |
|---|---:|---:|---:|
| status-conditioned prior | 0.562 | **−0.041** | **84.1%** |
| residual label | **0.709** | **0.927** | 52.2% |
| *the two annotators against each other* | *0.775* | *0.908* | *92.9%* |

*Read the middle column. Scored over the whole label set, the prior-filled table is
**worse than chance** and the residual-filled one is **at the human ceiling** — a swing
of 0.97 from a single design choice, on identical rules and identical located text. No
rule work in this document comes within an order of magnitude of that. And the choice
reverses in the right-hand column, so neither variant is simply better.*

*The mechanism is one count: the annotators were **both blank on 11 of the 32 rows**,
and on roughly 440 of the 488. Those rows are free agreement between two humans, and
they are unreachable for any table that never says "unknown". The prior scored badly
not because its guesses were wrong but because it made guesses at all. Symmetrically,
the prior's 32 extra correct rows are exactly what the residual gives up on the
right-hand column. Both columns are legitimate; only one is being computed.*

So: **settle input 7 before choosing.** Then

* count the distinct reason values in the label set, and count the blanks separately —
  the blank rate is the size of the effect above;
* if the metric excludes blank-gold rows, emit the §7.2 prior and never a residual;
* if the metric scores them with blank as a category, emit the residual wherever
  `Basis` is `NONE`, and keep the prior out of the reason column entirely;
* **emit the residual as an explicit string, not an empty cell**, whenever the scorer
  folds the two together — and ask, because most do. A literal `Unknown` survives a CSV
  round-trip, cannot be confused with a dropped row or a failed join, and is usually
  already in the vocabulary the requester wrote down. An empty cell is indistinguishable
  from missing data at every later step;
* if you do not know, or the requester may change their mind, **ship so that either can
  be derived without a re-run** — see below. This is almost always the right move.

**Shipping for both metrics costs nothing. Do that, and the question stops being
load-bearing.** Two mechanisms, and you want both:

* **In the deliverable:** whichever variant the metric calls for, plus a fixed,
  greppable opening phrase on every `NONE` class in `Evidence` (§1 already requires
  this). One line then converts in either direction with no access to the pipeline:

  ```python
  # residual-filled -> prior-filled needs the prior, so carry it (below).
  # prior-filled -> residual-filled needs only the Evidence prefix:
  reason = 'Unknown' if row['Evidence'].startswith('LOW CONFIDENCE: no') else row['Reason for Failure']
  ```

* **In the sidecar: carry the status prior in its own column**, on every row, whatever
  the reason column says. It is one string per row and it is the only thing that cannot
  be reconstructed later. A table shipped residual-filled without it has thrown the
  other metric away.

Then say in the notes which variant is shipped, which metric it serves, what the other
one scores, and the exact line that converts. The choice belongs to whoever computes
the score, not to whoever built the table — and it will change at least once.

*Run 2 shipped prior-filled against an unstated metric, learned afterwards that the
score was AC1 over all rows, and re-shipped residual-filled with the prior moved to a
sidecar column. The rules were not touched. Asking for input 7 at the start would have
saved the round trip; so would carrying the prior column from the beginning.*

### A note on the residual bucket

`Business reasons` deliberately absorbs a wide range of situations. Keep the
sub-reason inside `Evidence` — it always names which applies (funding, supply,
protocol, investigator, regulatory, technical) — so a finer-grained reading can be
filtered back out without re-running anything.

## 2. Read the corpus shape before designing anything

Do this first, on every new dataset, before designing anything. Four questions, each
answerable in one command against the corpus of input 1:

```
# 1. what sections/fields does a record actually have?
grep -h '^## ' <corpus glob> | sed 's/ ([0-9]*)//' | sort | uniq -c | sort -rn
# 2. how many records are there, and what is the identifier?
grep -hc '^# ' <corpus glob> | paste -sd+ | bc
# 3. is the stop reason present locally AT ALL? (try every spelling)
grep -lioE 'why.?stopped|termination reason|reason for (stopping|termination)' \
     <corpus glob> | wc -l
# 4. what do the sibling tables carry?
for f in <sibling tables>; do echo "== $f"; head -1 "$f" | tr ',' '\n' | nl; done
```

For a corpus that is not section-structured markdown, the equivalents are: list the
keys of one record, count the records, grep the whole corpus for every spelling of the
stop reason, and dump the column names of anything shipped alongside it. The point is
the same — know what is in your hands before you plan around it.

**The finding that usually matters: the corpus does not contain the stop reason.**
Expect this. It has been true on every corpus this method has been run against, and
it is usually true because the stop reason is a registry field that whoever assembled
the corpus had no reason to pull.

This is not a reason to stop; it is the design constraint. Fetch the stated stop reason
from the registry (input 2) and join it back by identifier. Budget for that before
designing anything else.

**Say so explicitly in the deliverable's notes, with the command that shows it.** A
requester who told you "the stop-reason field will be helpful" believes it is in the
files they pointed at, and the single most useful line in your notes is the one showing
it is not. Quote question 3 above and its output.

*Run 1 and Run 2: every record held exactly two sections, neither of them registry
data, and a case-insensitive search for the stop-reason field across the whole corpus
returned zero hits. The sibling table held identifiers, titles, phases, conditions,
interventions and sponsors — nothing about why anything stopped. The field then
supplied ~63% of all located reasons once fetched, making it both the largest single
source and entirely absent from the inputs as given.*

Fetch in batches, with the field list **validated one field at a time first** — on a
field-selecting API a single bad name usually returns an error for the whole batch, and
a retry loop will silently burn minutes on it:

```
curl -s "<registry endpoint>?<id filter>=<one id>&fields=<candidate list>" | tail -3
```

Do not trust a documented short alias to exist. *Run 2: the short aliases for the
results module did not resolve and had to be replaced with full dotted paths, and the
analysis objects sat one level higher in the response than the documentation implied.
Both were found by a single-record call costing seconds; either would have been an
opaque failure at batch scale.*

Minimum useful field set, by role rather than by name — map each to whatever your
registry calls it:

| role | used by |
|---|---|
| identifier, title | everything |
| overall status, last known status | §3 regimes, §7.2 priors |
| **stated stop reason** | §4 tier 1 — the single highest-yield field |
| start / primary completion / completion dates | §6.4 year check, §11 date check |
| phase, enrolment count and type | §11 ranking, §7.2a tests |
| lead sponsor name and class | §11 ranking, §7.2a tests |
| conditions, interventions, primary outcome measures | §5.6 indication guard, §7.3 |
| brief summary, study type | corpus sanity checks |

Then add, for subsets only: the long description for records whose stop reason is a
pointer (§5.1); the results module for posted outcomes and the limitations narrative
(§4.1); and the reference list plus a literature API for cited publications (§6.4).

## 3. The two regimes, and why they decide everything

A "failed" trial is two materially different things, and the reason distribution
differs sharply between them. Separate them before anything else, using registry
status:

| regime | status | what "failure" means | reason distribution |
|---|---|---|---|
| **stopped early** | `Terminated`, `Withdrawn`, `Suspended` | the trial did not run its course | operational: mostly business, then recruitment |
| **completed and missed** | `Completed`, `Active, not recruiting`, `Unknown` | the trial ran and the intervention did not deliver | almost always `Ineffective for purpose` |

*Run 1, on the labelled subset: among stopped-early trials the gold
reasons were 57% business, 26% recruitment, 9% pandemic; among completed-and-missed
trials they were `ineffective for purpose` in 9 of 11 cases.*

Two consequences:

1. **For a stopped-early trial, the stated stop reason is the answer** when one
   exists. Do not reach for publications first; the sponsor already said why.
2. **For a completed-and-missed trial, `Ineffective for purpose` is the principled
   default**, not a residual label. The trial was not stopped for recruitment, business
   or safety reasons — it finished — so what remains is the intervention failing to do
   what it was tested for. That default arrives by one of two routes, and they must not
   be conflated: with a negative result on record it is **evidence** (§6, §7.1), and its
   confidence follows the strength of that result; with nothing on record it is a
   **prior** (§7.2), always `Low` and always marked `Basis = NONE`. Same bucket, very
   different warrant.

If the upstream outcome table collapses both regimes into one label, recover the split
from registry status rather than trusting the label's granularity. If it is coarser
still — no way to express "ran to term and missed" — then it cannot express the
completed-and-missed regime at all, and the trials in that regime will reach you
mislabelled or not at all; §1.1 is the mitigation.

**Use the regimes to choose the prior, not to decide whose outcome was negative.** The
split above is what makes the §7.2 prior informative, and registry status is enough for
that. It is *not* enough to tell a completed trial that missed from one that hit —
nothing in the registry is — which is exactly why the outcome determination is a
separate input (§0, input 3) and why §1.1 insists the reason be scoped to negative
trials without being keyed to a single label for them. Registry status does settle one
case on its own: a trial with no outcome determination at all that was terminated,
withdrawn or suspended stopped for a reason, and that reason is in scope.

## 4. Evidence sources, in order

Try them in this order and stop at the first that yields a bucket. Record which one
fired, so the mix is auditable.

| # | source | typical yield | confidence ceiling |
|---|---|---|---|
| 1 | stated stop reason (`whyStopped`) | the large majority of stopped-early trials | High |
| 2 | **other registry narrative fields** (§4.1) — detailed description, posted-results limitations-and-caveats, participant-flow narrative and disposition types | small but the only route for trials whose `whyStopped` is blank or opaque | Medium |
| 3 | bundle `## Literature` — a trial-level early-stop statement | small | Medium |
| 4 | bundle `## Literature` — an endpoint-miss statement | moderate | High if it names the primary endpoint |
| 5 | registry-listed references, `RESULT` → `DERIVED` → `BACKGROUND` | small | Medium; Low for `BACKGROUND` |
| 6 | posted results — all primary-outcome analyses non-significant | moderate | Low |
| 7 | operational residual for stopped-early trials (§5.4) | small | Medium |
| 8 | a bare monitoring-board stop (§5.7) | very small | Low |
| 9 | external reference (§11) | very small | Medium |
| 10 | status-conditioned prior (§7.2) — **not evidence**; `Basis = NONE` | the remainder | Low |

Tier 10 is where the §1.2a decision lands: the prior if the metric ignores blank gold
rows, the residual label if it scores them. Either way it is **not a finding**, and the
table must keep findings and non-findings distinguishable — that is what `Basis` is
for, and §10.5 scores the two halves separately because they behave completely
differently.

### 4.1 Registry narrative fields beyond `whyStopped`

`whyStopped` is blank for a large minority of stopped trials, and a recognisable
fraction of the entries that exist are pointers or boilerplate. Three further fields
carry the reason and are cheap to fetch for exactly the subset that needs them:

* **detailed description** — resolves the entries that say only *"See termination
  reason in detailed description"*, and often carries a dated termination narrative
  even when `whyStopped` is empty;
* **posted-results limitations-and-caveats** — written to explain why the results are
  thin, so it states the stop reason plainly: *"terminated early because of slow
  enrollment"*, *"after a futility analysis suggested a full sample size would not lead
  to a positive result"*, *"after monitoring early toxicity … in 4/5 patients"*. It
  exists only for trials with posted results, so fetch it for that subset;
* **participant-flow disposition types** — a trial-level reason occasionally appears as
  a per-participant disposition category, e.g. *"Study terminated by sponsor"*.

**Require the stop sentence's subject to be the study.** These are long prose fields
full of protocol boilerplate about stopping the *drug* — *"the drug will be stopped
after 48 hours"*, *"participants will discontinue VPA"*, *"continue until toxicity"* —
which matches any naive terminated/stopped/discontinued pattern and swamps the real
signal. Match on study/trial/protocol/enrolment as the subject, plus an explicit
exclusion list for the dosing boilerplate, and cap sentence length.

Cap confidence from these fields one step below the dedicated field: they are narrative
rather than a sponsor's answer to "why did this stop".

*Run 1: these three fields resolved 29 of the 161 stopped trials whose
`whyStopped` was blank or a pointer — the single cheapest coverage gain available after
fixing the row scope.*

**Expanding evidence coverage is usually not the lever — measure before you buy it.**
Once the row scope is right, the obvious next move is to widen the cheap registry
routes. In Run 2 this was tried uniformly and deliberately: posted results went
from 598 trials to all 2,185 that have them, registry reference lists from 417 trials
to 7,069, and 11,183 reference abstracts were pulled. **The labelled score did not move
by a single row.** The reason is visible in one count: of the eleven remaining misses,
**eight had zero registry references** and only one had posted results. Trials that
reach the last tier are there because nothing was ever published about them, and that
is a property of the trials, not of your fetch coverage.

The expansion is still worth keeping — it decided ~190 reference rows and ~170 results
rows table-wide, and it makes the route mix honest — but budget it after the scope work
of §1.1, never before, and expect it to buy breadth rather than score. Rank the
unresolved by whether a public record can plausibly exist (§11) before spending on it.

*Run 1 route mix on the failed trials: ~63% from the stated stop
reason, ~24% from reported results of a completed trial, ~2% from the other registry
narrative fields, under 1% each from bundle literature and external references, and
~13% left to the prior. The headline: roughly seven rows in eight were decided by
located text, and the remaining eighth carried the great majority of the errors.*

## 5. Reading the stated stop reason

This field carries most of the signal and most of the traps. It is free text written by
sponsors, so it contains denials, boilerplate, typos and non-reasons.

### 5.1 Normalise and resolve pointers

Collapse whitespace. A recognisable minority of entries say only *"See termination
reason in detailed description"* — resolve those by fetching `DetailedDescription`
for exactly that subset and substituting it, labelling the source in `Evidence` as
`whyStopped -> DetailedDescription` so the provenance stays visible.

### 5.2 Strip negated causes — in two passes

Sponsors routinely append a denial: *"Termination was not due to any safety
concerns"*, *"No new safety signals were observed"*, *"safety concerns were not a
factor"*, *"There has been no change in the benefit/risk profile"*. Matched naively,
every one of these produces a false `Toxic/unsafe`.

**Strict pass.** Find a negation marker — `(not|never)` within two words of
`due to | based on | because of | related to | attributable to | influenced by | for`,
or `without any`, or `no (new|unexpected|apparent|additional) (safety|toxicity|adverse)`,
or `there (has|have|was|were) been no`, or `(safety|efficacy) (concerns|issues) (was|were) not`
— and if a safety, efficacy, pandemic or benefit/risk word appears at or after it, drop
from the marker to the end of that sentence. Dropping only to the next comma leaves the
tail of a denied list behind (*"…or changes to the benefit/risk profile"*), which
matches again.

**Gentle second pass.** The strict pass can also discard a real reason stated after the
denial: *"DSMC acknowledged no safety concerns with the trial, recommending that the
trial be terminated due to slow enrollment"* loses its reason entirely. So when the
strict pass yields no bucket, retry with a pass that removes only the negated clause up
to the next comma or semicolon — and **never accept a `Toxic/unsafe` call from the
gentle pass**, since that is exactly the false positive the strict pass exists to
prevent. Note in `Evidence` when a reason came from the second pass.

Also scrub positively-framed safety phrases before matching: a stop *"based on safety
benefit in the experimental arm"* is a favourable finding, not a safety problem.

**Order the denials: pandemic first, then safety, then efficacy.** Each pass replaces
the span it matched, so a pass that runs early can eat the words a later pass needs.
Sponsors deny several causes in one breath — *"the decision was not based on any safety
concerns … or influenced by issues imposed by the pandemic"* — and stripping the safety
clause first removes the `not based on` that the pandemic test depends on, leaving the
pandemic mention live and the trial mis-bucketed. Pandemic denials are the rarest and
the most easily destroyed, so run them first.

**Scope a pandemic denial to causal verbs only.** `(not|nor|never)` followed within a
short window by `based on | influenced by | related to | attributable to | caused by`
is a denial; a bare `not` near a pandemic word is not. *"Study drug not available due
to COVID-19 restrictions"* names the pandemic as the cause and must survive — a loose
pattern reads the `not available` as the denial and drops the one true pandemic case.

**Scope an efficacy denial the same way.** *"The data are not interpretable in terms of
efficacy"* is a statement about the analysis, not a denial that efficacy caused the
stop; treating it as one discards the trial's actual reason.

### 5.3 Reject texts that are not failures

A distinct class of stop text describes an early stop for *sufficient or positive*
data, or a neutral administrative close: *"Met study stopping rules"*, *"end-point
reached"*, *"halted to analyse data"*, *"Study completed"*, *"Finished"*,
*"Administratively complete"*, *"all patients recruited"*, *"adopted as standard of
care"*, *"DSMB recommendation based on safety benefit"*.

These are not failures. Say so in `Evidence` — the stated reason describes a
non-failure stop, so no failure reason is on record — and give the row the residual-or-prior of §1.2a, the residual
label at Low confidence if the target has one, or the §7.2 prior if it does not. Test
this **before** the keyword rules, guarded by a check that the text does not also
report explicit harm — otherwise a bare safety-body mention inside such a text will
pull it into `Toxic/unsafe`.

**Test the pandemic before the non-failure phrasings.** *"Study completed early due to
COVID-19 pandemic regulations"* opens with goal-attainment wording and ends with the
real cause; checked in the wrong order it reads as a trial that simply finished.

*These rows are also a useful signal back to the upstream outcome table: a trial whose
sponsor says it met its stopping rules is probably mis-labelled as a failure. Count
them and report the count.*

### 5.4 Reject texts that carry no reason, but keep the residual

Two further classes must be separated:

**Uninformative** — the text restates the status or says nothing: *"why study
stopped"*, *"Not stated"*, *"Withdrawn"*, *"Terminated"*, *"trial stopped on
<date>"*, *"Unable to complete study"*, and the registry's own boilerplate
*"recruiting or enrolling participants has halted prematurely and will not resume"*.
These carry no reason: give them the residual label, or the §7.2 prior where the target
has none. Match them as whole-string patterns, anchored, so they cannot swallow longer
informative texts.

Be strict about what belongs here. A single word that names a *category* of cause —
`Administrative`, `Operational`, `Funding`, `Per Sponsor`, `Program terminated` — looks
uninformative but rules out every scientific bucket, so it is an operational residual
below, not an uninformative text. `Study never started` likewise: it is thin, but
nothing was attempted, which is a business circumstance (§8).

**Operational residual** — the text describes a real circumstance that matches no
keyword set: *"Transfer of study sponsor"*, *"Under the limited resources, to re-plan
the ongoing clinical trials"*, *"further optimization of the approach to achieve
bioequivalence is required"*, *"Study never started"*. For a stopped-early trial with
a text of three or more words that is not uninformative, file these under
`Business reasons` at Medium confidence, with `Evidence` stating that the bucket was
read from the circumstance described rather than from an explicit business statement.
This matches how human annotators treat them and converts a chunk of `Unknown` into a
defensible call.

### 5.5 Keyword rule sets, and the predicate requirement

Build one pattern list per bucket from the **verbatim texts in the corpus**, not from
imagination. Dump every distinct stop text that the current rules fail to classify and
read them; registry free text contains spellings no generic list anticipates
(`recuit`, `rectruit`, `recruiment`, `recrutment`, `referal`), and each round of
reading yields a handful of real patterns.

The single most important structural rule:

> **A topic word is not a reason. A shortfall predicate must sit next to it.**

*"Recruitment was stopped before start of the pollen season"* contains "recruitment"
but is a seasonal operational decision, not a recruitment failure. So the recruitment
set must not contain a bare `recruit|enrol|accrual`; it must require a shortfall term
within a short window, in either order:

```
shortfall = slow | poor | low | insufficient | inadequate | inability | unable |
            difficult* | challeng* | lack of | zero | 0 | few | too few | limited |
            declin* | diminish* | failure | failed | unsuccessful | infeasib* |
            not enough | issues | problems | shortfall | under-enrol* | protracted | no
topic     = recruit* | recuit* | accrual | accrue* | enrol* | inclusion | screen* |
            participants | subjects | patients | volunteers | centres | sites | referral*
```

plus a small set of high-precision phrases the window cannot reach: *"0 enrollment"*,
*"No recruitment since initiation"*, *"not able to meet recruitment"*, *"not
reachable"*, *"not recruited as intended"*, *"screened but not enrolled"*,
*"incomplete enrollment"*, *"at a standstill"*, *"delays in enrolment"*, *"Accrual
Factor"*, *"lack of appropriate cases"*, *"Under-enrollment"*.

The same rule governs publications, where it is easy to forget: see trap 14 in §10.3.

Apply the same discipline in the other direction, with negative lookaheads: `did not
meet` is an efficacy phrase **unless** an accrual, enrolment, recruitment, sample-size
or target word follows within ~35 characters, in which case *"Did not meet target
patient accrual goals"* is recruitment. Likewise `futility` is efficacy unless it is
*"futility for enrollment"*. When writing such a lookahead, pin the word ending —
`futilit(?:y|ies)\b(?!…)` — because `futilit\w*(?!…)` lets the engine backtrack a
character and escape the lookahead entirely.

### 5.6 Arbitration when several buckets match

Most non-trivial texts match more than one set. Resolve in this order, and record the
rule applied in `Evidence`:

1. **The pandemic, when it is the cause named.** If a COVID term matches and nothing
   else does, the answer is `Due to COVID-19 pandemic`. If a COVID term matches
   alongside another bucket, check for a contributory qualifier —
   `also | partly | partially | in part | additionally | as well as | compounded by |
   exacerbated by | during the | in the context of` immediately before the COVID
   mention. With such a qualifier the pandemic is an aggravating factor and the
   concrete cause wins: *"Difficulty in recruiting patients **also due to** the
   pandemic period"* is `Recruitment issues`. Without one the pandemic wins, even when
   it caused something operational: *"Study drug resupply delayed (Covid-19)"* is
   `Due to COVID-19 pandemic`.
   Also guard against the pandemic as the *disease under study* — *"No longer studying
   long COVID"* names an indication, not a reason.
2. **The clause after a causal marker.** `due to | because of | because | owing to |
   as a result of | in view of | caused by | secondary to` introduces the stated cause,
   and it outranks whatever the rest of the sentence mentions: *"stopped before the
   targeted number of patients was reached **due to lack of support**"* is
   `Business reasons`. Skip a marker that is itself prefixed by a contributory
   qualifier ("also due to"), so the head clause keeps priority.
3. **Inside that clause, the first reason named.** *"terminated due to slow enrollment
   and the transfer of the PI"* is `Recruitment issues`.
4. **With no usable causal clause: safety first, then first-named.** An explicit safety
   statement outranks the rest, because a safety stop is the consequential call.
   Otherwise the first reason named in the text is the primary one — *"Investigator
   left institution. 7 patients accrued and there is insufficient data to analyze"* is
   `Business reasons`.

Fixed global precedence (safety > efficacy > recruitment > business) is the wrong
default here: it mis-assigns any text whose head clause names an operational cause and
whose tail happens to mention patients or data.

### 5.7 Weak signals that must not outrank concrete ones

Some wording names a bucket without stating a finding. Apply these **only when nothing
concrete matched**, and always at Low confidence with the ambiguity written into
`Evidence`:

* **A bare monitoring-board stop** — *"Enrollment was stopped based on the Data
  Monitoring Committee's recommendation"*. Such a stop may be for safety or for
  futility. Keep the board patterns out of the main safety set entirely: as a
  first-class safety pattern they override explicit efficacy text, turning *"terminated
  based on the review by an independent data monitoring committee of the prespecified
  interim analysis of the efficacy data"* into `Toxic/unsafe`. Skip this fallback when
  the text explicitly denies safety.
* **An unexplained regulatory hold** — *"FDA Clinical Hold"*. Usually safety-driven,
  but the text gives no reason.
* **Underpowering** — *"Halted due to lack of statistical power"*. Normally a shortfall
  against the planned sample size, but the text does not name recruitment.

Separately, **demote a bare decision mention**: *"the Sponsor decided to terminate the
study"* names who acted, not why. When the only business signal is a bare
sponsor/decision term and another bucket has a substantive match, the substantive one
is the reason — otherwise a text whose first sentence is "the Sponsor decided to
terminate" and whose second says the drug "was not superior to placebo" is filed as
business.

Finally, **cap confidence at Medium for texts that name a bucket with no substance** —
*"Administrative"*, *"Operational"*, *"Per Sponsor"*, *"Management Decision"*,
*"Trial terminated by Sponsor"*. The bucket is right; the detail is absent.

## 6. Turning a publication into a reason

Only reached when no stop reason exists. The risk here is not polarity alone but
relevance: bundled literature includes reviews, sub-studies and unrelated papers.

### 6.1 Relevance gates

A sentence may support a reason only if it **frames a trial endpoint or a treatment
comparison**: a primary/secondary/composite endpoint or outcome, a comparison with
placebo/control/standard, a between-group or between-arm statement, a named arm, a
hazard/odds/risk ratio, or a p-value. Reject otherwise.

Reject outright, whatever else matches:

* **Favourable negations.** *"did not increase | worsen | raise | exacerbate | impair |
  prolong"*, *"no increase in the incidence of adverse events"*, *"was not inferior"*.
  These report success, not failure. This is the single most common polarity trap.
* **Positive findings** — the mirror of the above, and just as common once the
  literature route is run over a whole corpus rather than a failed subset.
  *"was observed to have significant antiviral activity"*, *"significantly improved"*,
  *"was effective"*, *"met its primary endpoint"*, *"a promising strategy"*. A sentence
  reporting that the intervention worked cannot support any failure bucket, however
  many endpoint words it contains.
* **Study timepoints read as stops.** *"At end of treatment (EOT), the mean decrease
  was 2.82 log10…"* — a results sentence anchored on a protocol timepoint. Pin the stop
  verb `end(ed)` with a negative lookahead for `of treatment | study | therapy |
  follow-up | period | cycle`, or every results sentence becomes a trial-level
  early-stop statement.
* **The "options" sense of a shortfall word.** *"patients with MDR HIV-1 infection who
  have limited **treatment options**"* puts a shortfall term beside a topic word and
  means neither recruitment nor failure; it describes the therapeutic landscape.

*Run 2: these four gates between them were the difference between
97.3% and 100% on the evidence-backed half of the labelled rows. The single remaining
wrong evidence-backed call was a positive-finding sentence.*
* **Methods and review boilerplate.** Sentences about assumptions, regression models,
  "we used / we analysed", "may result in", "statistical analyses", "center effect",
  definitions (*"defined as"*, *"if any of the following"*), inclusion/exclusion
  criteria, meta-analyses, and references to previous studies.
* **Sub-system statements.** *"The original glycemic data collection system was
  discontinued because of safety concerns and replaced…"* is about a glucose meter, not
  the trial.
* **Pooled and other-trial statements.** *"18 studies, 927 participants: RR 5.33"*,
  *"Several clinical trials have shown no benefit or were stopped early for futility"*,
  *"previous trials reported"*. These frame an endpoint and name a bucket, and say
  nothing whatever about the trial in hand. Reject on `\d+ studies|trials`, `I²`,
  `pooled`, `meta-analys`, `systematic review`, and
  `(several|many|other|previous|most) (clinical )?(trials|studies)`. The title gate
  (§6.4) does not catch these — a review whose title is *"The therapeutic horizon of
  acute kidney injury in critical care"* contains none of the reject words. **This trap
  only becomes visible once the literature route runs over a whole corpus rather than a
  failed subset**, which is also when it starts doing damage.

### 6.2 Trial-level stop statements

For an early-stop reason, require the sentence to say that **the trial** stopped — the
grammatical subject must be the trial, study, protocol, enrolment, accrual, dosing or
randomisation, or the sentence must say "stopped/terminated early", "ended
prematurely", "stopped for futility", or report a futility analysis. A generic
"discontinued" verb matches patient dropouts and device swaps.

This gate also prevents a comparative dropout statement from being read as toxicity:
*"17.4% (drug) versus 29.9% (comparator) of patients discontinued due to
treatment-emergent adverse events"* describes the study drug doing **better**.

### 6.3 Scoring and confidence

Rank candidate sentences: naming the primary endpoint outranks a general comparison,
which outranks a secondary-outcome statement. Map to confidence High / Medium / Low
respectively, and when the statement concerns only secondary outcomes say so in
`Evidence`.

### 6.4 Registry-listed references

Where the bundle is silent, the registry's own reference list plus a literature API
fills some gaps. Try `RESULT`, then `DERIVED`, then `BACKGROUND`, and cap `BACKGROUND`
at Low confidence with an explicit caveat that the paper may describe related work.

**Check the publication year against the trial start date.** Registry reference type
labels are unreliable — papers from years before a trial began appear labelled
`RESULT`. A paper published before the trial started cannot report its result; discard
it regardless of its label.

## 7. Inference from registry results and status

### 7.1 Posted results

When every primary-outcome analysis has p ≥ 0.05, record `Ineffective for purpose` at
Low confidence, quoting the outcome titles and p-values and noting that no stop reason
or publication statement was on record. Include the registry's own
limitations-and-caveats note when present. Mixed significance is not evidence of
failure — leave it to the §7.2 prior.

### 7.2 Status-conditioned priors — the last tier, and not evidence

When nothing in §4's tiers 1–9 yielded a bucket, the row still needs a value: the
target may have no residual class (§1.2), and a residual label scores zero wherever
that is true. Fall back to the modal reason **for that registry status**, which is a
real signal — the two regimes of §3 have sharply different reason distributions — while
being explicit that it is a prior and not a finding.

| status | prior | mechanism |
|---|---|---|
| `Completed` | `Ineffective for purpose` | a trial that ran to term has no conduct-related failure mode left, so the intervention is the only thing that can have failed |
| `Unknown` status | `Ineffective for purpose` | no stop was ever recorded; the trial most likely ran on unverified |
| `Terminated`, `Withdrawn`, `Suspended` | `Business reasons` | operational causes are modal among stopped trials that do state one |
| still-recruiting or active | `Business reasons` | a trial nominally ongoing but treated as failed has most likely been abandoned without the registry being updated |

Measure the modes on the label set rather than assuming them, and recheck on each new
corpus; use the aggregate distribution only, never an individual labelled row.

Three requirements, all of which matter more than the prior itself:

* **Confidence is always `Low`**, `Basis` is `NONE - status-conditioned prior`, and the
  `Evidence` string opens by saying no reason was on record and that the class comes
  from a base rate rather than from evidence. Close it with an instruction to treat the
  row as unresolved.
* **Report the prior-based share of the table**, and never quote a single accuracy
  figure that mixes the two halves (§10.5).
* **Do not tune the prior on a handful of rows.** The still-ongoing entry above rests
  on one labelled trial and is barely supported; say so rather than presenting it as
  measured.

*Run 1: priors supplied ~13% of the failed-trial rows and contained
10 of the 10 remaining errors. The evidence-backed 87% was exactly right.*

### 7.2a Before adopting a refinement, test that it separates anything

The prior's errors are concentrated and tempting to chase. Test any candidate
discriminator against the label set *as a contingency table* before building it.

*Run 1: completed trials with no stop reason were labelled
`ineffective for purpose` 18 times and `business reason` 6 times, and the obvious
discriminators — whether results were posted, whether any publication was linked —
split neither group: `ineffective` dominated every cell. There was no rule to find, so
the right move was to stop and report the 6 as irreducible rather than invent a signal.
A refinement that cannot be shown to separate the classes on the labelled data will not
generalise, and it costs real accuracy elsewhere.*

*Run 2, over the 32 prior-decided labelled rows: seven candidates were tabulated
before any was built, and not one separated the classes:*

| discriminator | `ineffective` : `business` |
|---|---|
| posted results absent / present | 17:7 / 3:1 |
| any linked publication absent / present | 9:3 / 11:5 |
| sponsor class industry / NIH / other | 6:3 / 2:1 / 10:4 |
| enrolment under 50 / 50+ | same ratio either side |
| phase 1 / phase 3 | 7:2 / 2:3 *(n=5 — noise)* |

*The one discriminator with real intuition behind it pointed the **wrong way**: among
these rows, `toxic/unsafe` was the gold label twice, and **both** times the primary
outcome measure made no mention of safety or tolerability, while the four rows whose
primary outcome did mention safety were all `ineffective for purpose`. A rule
"completed phase-1 safety study with no reason on record → `Toxic/unsafe`" is the most
tempting refinement available here and it would have been actively wrong. Tabulate
before building, every time.*

### 7.3 What must never be inferred

**Do not infer toxicity from death or adverse-event counts.** In oncology and
critical-care populations, high mortality reflects the disease. In Run 1, a rule
assigning `Toxic/unsafe` at a ≥25% death rate produced about a dozen wrong calls —
trials where 88%, 86% and 85% of participants died of advanced disease — and was
removed.
`Toxic/unsafe` requires an explicit safety statement. The same applies to high
serious-adverse-event fractions in trials whose primary outcome *is* safety.

**Do not infer a reason from the drug's later history.** A programme discontinued years
later for commercial reasons says nothing about why one trial stopped.

**Do not infer a reason from the upstream failure label alone** beyond the §7.2 priors,
and label those honestly as priors rather than findings.

**Do not let a prior masquerade as evidence.** A status-conditioned prior is the right
answer to "what is the best guess here", and the wrong answer to "why did this trial
fail". Both are legitimate; the table must say which one it is giving, on every row.

## 8. Bucket boundaries that cause most disagreement

Write these down for the corpus and apply them consistently; they account for most
annotator-to-annotator and run-to-run variance.

| situation | bucket | why |
|---|---|---|
| competing trial opened at the site | `Business reasons` | an operational decision, even though it affects accrual |
| recruitment stopped for a seasonal or timing reason | `Business reasons` | no shortfall stated |
| preclinical or design work showed the question could not be answered | `Business reasons` | the *design* failed, not the intervention in humans |
| assay, device or data-capture failure | `Business reasons` | operational, not efficacy |
| product withdrawn from market / no commercial availability | `Business reasons` | commercial, even when the molecule worked |
| funding ended before the accrual target was reached | `Business reasons` | funding is the stated cause; accrual is the consequence |
| study never started or never activated | `Business reasons` | nothing was attempted |
| interim analysis of efficacy data triggered the stop | `Ineffective for purpose` | the finding is about efficacy |
| protocol-specified stopping rule on response rate | `Ineffective for purpose` | a futility rule |
| safety complications explicitly unrelated to the study drug | `Toxic/unsafe` | still a safety stop; say "unrelated to study drug" in `Evidence` |
| pandemic named as the cause of a supply or visit failure | `Due to COVID-19 pandemic` | the pandemic is the cause named |
| pandemic named alongside an already-stated shortfall | the shortfall | contributory (§5.6) |

## 9. Confidence

* **High** — a single bucket matched an explicit statement of the reason.
* **Medium** — the text named more than one bucket; or the bucket came from a
  publication rather than a sponsor statement; or the text names a bucket without
  substance; or the bucket was read from an operational circumstance (§5.4) or the
  completed-and-missed pattern (§7.2).
* **Low** — inferred rather than stated: posted p-values only, `Unknown` registry
  status, an external source, a `BACKGROUND` reference, a secondary-outcome statement,
  a weak signal from §5.7, a residual label, or a §7.2 prior.

Every `Low` row's `Evidence` must begin `LOW CONFIDENCE:` and name the gap, so a reader
can tell at a glance which rows not to build on. Assert this as an invariant (§10.4).

`Confidence` and `Basis` answer different questions and both are needed. Confidence
grades how firmly the located text supports the bucket; `Basis` says whether any text
was located at all. A §7.2 prior is the one case where the distinction bites: it is
`Low` like a weak inference, but unlike a weak inference it rests on nothing specific
to the trial, and only `Basis` records that. Scoring that cannot separate the two
(§10.5) will read a table of priors as a table of findings.

## 10. Validation

### 10.1 Audit the patterns for inert regexes — after every edit

A pattern that never fires is invisible. After each rule change, count matches per
pattern across the corpus's stop texts and list the zero-match patterns; some are
genuinely absent from this corpus, but the rest are bugs — a mis-escaped class, a
lookahead the engine can backtrack out of, or a pattern shadowed by an earlier one.

### 10.2 Hand-read the evidence against the source text

Sample each bucket — all of the small ones, 20–30 of the large ones — and read the
`Evidence` string against the quoted source. Repeat after every rule change. Every
error class in §5 and §6 of this document was found this way and not by any aggregate
statistic.

### 10.3 Trap classes — check each explicitly on a new corpus

1. **Negated causes** read as positives (§5.2).
2. **Death/AE counts** read as toxicity (§7.3).
3. **Non-failure stops** read as failures (§5.3).
4. **Favourable negations** in publications (§6.1).
5. **Topic words without predicates** read as reasons (§5.5).
6. **Weak signals outranking concrete ones** (§5.7).
7. **Reference type labels** trusted without a year check (§6.4).
8. **Lookahead backtracking** silently disabling an exclusion (§5.5).
9. **Denial passes mis-ordered**, an early pass eating the words a later one needs, and
   denial patterns scoped to a bare `not` rather than a causal verb (§5.2).
10. **Enrolment vocabulary without a shortfall**: *"enrollment was stopped on the
    monitoring board's recommendation"*, *"enrolment halted prematurely"*, *"terminated
    in advance of targeted enrollment"*, *"closed to accrual pending drug availability"*
    — all name a committee, a supply hold or nothing. Conversely *"futility for
    enrollment"* **is** recruitment, not efficacy, despite the word (§5.6).
11. **A residual label chosen without knowing the metric** (§1.2a) — a residual emitted
    where the score ignores blank gold rows is a guaranteed miss; a prior emitted where
    the score is a chance-corrected agreement forfeits every row the annotators agreed
    was unknown. Both are invisible to every check except the requester's own metric,
    and the two errors look identical from inside the pipeline. Worth 0.15 of AC1 in
    Run 2.
12. **A row set gated on the upstream failure label** (§1.1) — invisible to every check
    including the score, if the score is computed inside the gate.
13. **A bare `for` admitted into the causal-marker set** (§5.6). The marker list is
    closed for a reason. Adding `for` makes *"…leading to a decision to terminate the
    study early **for** enrollment futility"* a causal clause whose head — the slow
    enrolment stated first — is discarded, and the same edit turns *"Lack of
    substantial evidence **for** immune responses"* into a clause containing no
    reason at all. Three trials were mis-bucketed by this one alternative.
14. **A literature sentence that merely enumerates endpoints read as a finding**
    (§6.1). *"The primary outcomes were overall survival and serious adverse events"*
    satisfies any endpoint-frame gate and names a safety topic, and reports neither.
    §5.5's predicate rule has to be applied to §6 as well: reject the enumeration
    verbs (`included | were | comprised | assessed | measured | compared`), reject
    structured-abstract labels (`BACKGROUND:`, `METHODS:`, `OBJECTIVE:`) and the
    objective forms (*"To test whether…"*, *"The aim was…"*), reject protocol papers
    and reviews on the title, and require a **harm predicate** within ~70 characters
    of the safety term before allowing `Toxic/unsafe`. Without these, the safety
    bucket fills up with trials whose primary outcome simply *was* safety: 14 of 41
    `Toxic/unsafe` rows in Run 2, every one of them wrong.
15. **A goal-attainment phrase inside a negation** (§5.3). *"a futility analysis
    suggested a full sample size would **not** lead to a **positive result**"* matches
    the non-failure set and is the clearest possible futility stop. Check for a
    negation in the ~55 characters before each non-failure match, not just for harm.
16. **The reason keyed to one outcome label** (§1.1) — the single most expensive trap
    in this document, and the one most likely to survive a careful reading of it. A
    reason is owed only where the outcome was negative, but taking "negative" from one
    fallible table means every disagreement between that table and the truth is a reason
    you can never reach. Widening the row set is not enough: a negative-outcome trial
    whose row exists but carries no decision scores exactly as badly as one that is
    absent, and it looks fine on every audit. 32 of 33 misses in Run 2. Check it
    directly: count labelled negative trials whose reason came from a "not a failure"
    branch. If that is not zero, fix the scope before reading any other metric.
17. **A positive finding in a publication read as a failure** (§6.1) — the mirror of
    trap 4, and it only becomes common once the literature route runs over a whole
    corpus instead of a failed subset. Also the protocol-timepoint and
    "treatment options" senses in the same section.
18. **A reason asserted where the outcome was not negative** (§1.1) — trap 16's mirror,
    and the one you create by over-correcting for it. The row names why a trial failed
    while its own `Evidence` says nothing calls it a failure. Silent: every other
    invariant passes and the rows read as findings. 433 rows in Run 2 g3, arriving
    precisely because the cascade had been set to run over every row and let any located
    sentence set the bucket. Check directly — count rows with a non-residual reason
    whose outcome was not negative, or whose `Basis` is `NONE`; it must be zero. **Walk
    traps 16 and 18 together**, since each is the natural overshoot of fixing the other.
19. **A pattern referenced by list index.** Inserting a pattern into a list silently
    re-points every index after it. In Run 2 this disabled the §5.1 pointer
    substitution for 11 trials — they fell through to the prior, and the table still
    passed all nineteen invariants and the whole unit list. Give any pattern a caller
    needs its own name, and assert the per-route row counts between runs: a route that
    drops to zero is the only visible symptom.

### 10.4 Invariants on the finished table

```
row set == outcome-table ids ∪ evaluation-set ids        (§1.1; no id dropped, none invented)
identifiers upper-cased and unique
bucket values ⊆ the target vocabulary, spelled as the target spells it   (§1.2)
confidence ⊆ {High, Medium, Low};  Basis non-empty on every row
no empty Evidence;  no embedded newlines
every Confidence == Low row contains "LOW CONFIDENCE"
Basis startswith "NONE" ⟺ Evidence declares that no reason was on record
the residual-vs-prior choice matches the metric of input 7, uniformly  (§1.2a)
a non-residual reason ⟹ outcome was negative AND Basis != NONE           (§1.1)
no row names a reason while its Evidence says nothing calls it a failure  (§1.1)
every negative-outcome row carries a decision, residual or otherwise      (§1.1)
```

Assert the row-set invariant against both inputs by name. It is the one invariant that
fails silently and expensively: a table can satisfy every other check, read perfectly
on audit, and still be missing two thirds of the rows anyone will score.

### 10.5 Scoring against a labelled subset

If a labelled subset exists, score against it — but check three things first, because
each one makes a working annotation look broken.

**Normalise the identifier.** Gold identifiers may be lowercase (`nct01234567`) while
the deliverable uses `NCT…`. An exact join then returns *zero* overlap, which reads as
"none of the labelled trials are in scope" rather than "the join is case-sensitive".
Verify the overlap count is plausible before concluding anything.

**Expect the labelled subset to be mostly out of scope, and treat that as a bug in the
scope rather than a fact about the labels.** If only a fraction of the labelled failures
fall inside the deliverable's failure set, the fix is §1.1 — widen the row set and
re-ship — not scoring on the fraction. Scoring the fraction is actively misleading: it
is computed entirely inside the gate that is losing the answers, so it looks healthy
exactly when coverage is worst. Report coverage (`rows present / rows scoreable`) next
to accuracy, always, and read the two together.

**Score the evidence-backed and prior-based halves separately.** They are different
estimators and a blended figure describes neither; the blend also moves whenever the
prior-based share moves, which makes runs incomparable. Report three numbers: overall,
`Basis != NONE`, and `Basis == NONE`.

*Run 1: 85.3% overall decomposed into 100% on the 35 evidence-backed
rows and 70% on the 33 prior-based ones. The blended figure would have sent effort to
the rules, which were already perfect, instead of to coverage, which was not.*

**Compute the statistic the requester computes, not the one that is convenient.**
Accuracy over gold-labelled rows and a chance-corrected agreement over all rows are
different questions, they rank candidate tables differently, and §1.2a shows a single
design choice moving one up while moving the other down. Ask which it is (input 7); if
you cannot find out, report both.

For a chance-corrected coefficient — Gwet's AC1, Cohen's or Fleiss' κ — three things
have to be stated or the number is uninterpretable:

* **How blank gold cells are handled.** As a category, or excluded? This is the whole
  ballgame (§1.2a). *Run 2: ann1-vs-ann2 on the same 32 rows was 0.775 with blank as a
  category and 0.924 with blank rows dropped. Quoting one and comparing against the
  other is a 0.15 artefact.*
* **Which rows.** "Trials we called failures" is not "trials gold called failures", and
  the two subsets give different coefficients from the same table.
* **The category count**, since `pe` depends on it. A table that never emits the
  residual has one category fewer than the annotators do, which shifts `pe` as well as
  `pa` — the coefficient moves for a reason that has nothing to do with being right.

Compute the human-vs-human coefficient **under exactly the same convention** and quote
it beside yours. It is the only honest denominator, and it is the number that tells you
whether a gap is model error or annotation noise.

**Score against each annotator separately as well as against either.** Annotators
differ in how readily they assign a reason at all; one may label trials the other
leaves blank. Report "matches either annotator" and "matches annotator *n* where that
annotator labelled", and compute the **inter-annotator agreement** on rows both
labelled — that is the ceiling, and a score at it means the remaining misses are
annotation noise, not model error.

Expect the per-annotator figures to differ by much more than the blended one suggests,
and do not chase the gap. *Run 2: 84.1% against either annotator
decomposed into 95.7% (44/46) against annotator 1 where they labelled and 74.5%
(38/51) against annotator 2 — a 21-point spread, on the same rules and the same rows.*
Two annotators who agree 26 times out of 28 where they overlap can still disagree
sharply about which trials deserve a reason at all, and the "either" figure sits
wherever their label counts happen to put it. Fitting to the weaker number fits to one
person's threshold; quote all three and the ceiling beside them.

Then measure in both directions:

* **Accuracy** on labelled failures, with a gold→predicted confusion table. Read the
  off-diagonal cells individually; each is a candidate rule.
* **Over-assignment** on trials the gold leaves blank. If those rows got a reason only
  because the upstream outcome table called them failures, the error is inherited, not
  introduced — report it as such rather than suppressing labels.

*Run 1, across two rounds: agreement against either annotator went
71.0% → 81.2% from rule work in §5 and §7, then 63.2% → 85.3% in a later round where
the gain came almost entirely from §1.1 and §1.2 — widening the row set and matching the
label strings — with the rules barely touched. Rule work and scope work are not
interchangeable, and scope was worth more. Inter-annotator agreement was 26 of 28, so
the ceiling is near 93% on jointly-labelled rows.*

Do not fit to the residue. Two near-identical phase 1 safety/PK studies in that subset
were labelled `toxic/unsafe` and `business reason` respectively, with nothing in either
record to separate them. §7.2a is the discipline: show a candidate discriminator
separates the classes on the labelled data, or drop it.

**Diagnose a disappointing score by route before touching a rule.** Cross-tabulate the
misses by `Basis` and registry status. The shape of that table says which of three very
different problems you have: rows absent entirely (§1.1), rows present with the wrong
string (§1.2), or rows present and genuinely mis-bucketed (§5). Only the third is a rule
problem, and in practice it is the smallest.

### 10.6 Regression discipline — one shared decision function

Put the per-trial decision in a single importable function, and have both the
production writer and the scoring harness call it. Keeping two copies guarantees that
the rules being scored drift from the rules being shipped. Re-run the harness after
every rule change — several fixes in §5 each raised one case and silently regressed
another, which only a standing score caught.

Keep a verbatim unit list of stop texts with expected buckets alongside the harness.
It is faster than the full score and catches the regressions that a 69-row aggregate
hides.

## 11. External sources and cost discipline

External lookup is the last resort, and it is expensive relative to its yield.

**Rank before searching.** Score the unresolved trials by how likely a public record
exists — industry sponsor, phase 2/3, larger enrolment, terminated rather than
withdrawn — and work the top of that list only.

**Expect a low hit rate and stop early.** In Run 1, six searches over the twenty
highest-value unknowns resolved two drug programmes (four trials); the rest returned
the registry record back. At that yield, extending over the remaining unresolved set —
well over a hundred trials — was not justified. Report the count attempted and resolved
so the decision is visible.

**Attribute carefully.** A programme-wide action documented in the press is not a
trial-specific stop reason. Where a programme-level event is the only explanation,
record it at Low confidence, name the external sources in `Evidence`, and state
plainly that the trial-specific reason is not on record and the attribution is
inferred. Check dates line up before asserting a link.

*Run 2 spent three searches on the three highest-ranked unresolved programmes and added
**nothing** to the table, which is the expected outcome and worth recording as such.
One programme-level event was well documented but the trials had ended seven months
before it — the date check killed an attribution that every other signal supported. One
was answerable from a registry field after all, which was the better source. One
produced press coverage of a programme decision but no trial-specific statement, so the
rows stayed unresolved. Budget external search as a formality you will probably not
cash, and record attempts and yield either way.*

**The date check is not a formality.** It is the one test that catches a plausible,
well-sourced, completely wrong attribution, and the failure mode is seductive: a
programme-level event in the press, the right drug, the right sponsor, trials that
stopped — and dates that do not line up. Compare the event date against the trial's
own completion or last-update date before writing a word of it.

**Never substitute recall for a source.** If a search does not produce a citable
statement, the row stays `Unknown`.

## 12. Known limits of what these sources can establish

* A stopped-early trial with an empty `whyStopped` is usually unrecoverable from the
  registry. Sponsors are not required to give a reason; §4.1 recovers a minority and
  the rest fall to the §7.2 prior.
* `Business reasons` is broad by construction; the sub-reason lives only in `Evidence`.
* The completed-and-missed default cannot distinguish an efficacy miss from a safety
  finding in a trial whose primary outcome was safety, nor from a sponsor who simply
  moved on. All three appear as `Ineffective for purpose`, and in Run 1 that last
  case was the largest single error class — six labelled trials where annotators found
  a business reason that no registry field expresses (§7.2a).

  *The same residue, re-measured in Run 2 with the scope fixed and every
  gate in this document applied: 11 misses out of 69, every one a prior-decided row on
  a `Completed` (9) or `Unknown`-status (2) trial, and the shape unchanged — 6 gold
  `business reason`, 3 `toxic/unsafe`, 1 `due to covid`, 1 `recruitment issues`, all
  predicted `Ineffective for purpose`. None of the 11 has a stated stop reason, 8 have
  no registry reference at all, 1 has posted results. 84.1% against a 92.9% ceiling,
  with the evidence-backed half at 100%. Treat roughly this much as the method's floor
  rather than a defect to engineer away: what is missing is not a rule but a record.*
* A bare monitoring-board or regulatory hold cannot be resolved between safety and
  futility from the registry alone.
* **A prior-based row carries no information about its own trial.** It is a defensible
  guess and the best available one, but a count of `Toxic/unsafe` or `Business reasons`
  taken over a table that includes priors is not an estimate of anything; filter on
  `Basis` before aggregating.
* Reasons are inherited from the upstream failure set. If that set is wrong, this table
  is confidently wrong in the same places; the §5.3 non-failure count is the cheapest
  signal that it is, and a disagreement between the upstream set and a label set
  (§10.5) caps the achievable score however good the rules get. That cap belongs in
  the notes as an upstream finding, not absorbed silently here.

## 13. Pipeline

One module per role. The names below are the reference implementation's; the roles are
the point.

**Put the six inputs of §0 in one place.** The reference implementation hardcodes its
paths in every module, which is the single thing that makes it awkward to point at a
new dataset — porting it means editing eight files instead of one. On a new run, put
the corpus glob, the registry endpoint and field list, the failure-signal table and
column, the label-set path, the vocabulary map and the output schema in a single
`config.py` (or a small dict at the top of the rules module) and import it everywhere.
The rules module should contain patterns and arbitration and nothing else — no paths,
no column names, no label strings beyond the vocabulary map.

```
id set             outcome-table ids ∪ evaluation ids   -> the row scope (§1.1)
extract_lit*.py    per-trial bundle ## Literature text, for an arbitrary id list
fetch_ctg.py       registry API, batched  -> status, whyStopped, dates, sponsor, phase
fetch_detail.py    registry API, subset   -> detailed description, participant flow (§4.1)
fetch_results.py   registry API, subset   -> posted outcome analyses, limitations (§4.1)
fetch_refs.py      registry API           -> reference list (pmid, type, citation)
fetch_pubmed.py    literature API         -> abstracts for those references
rules*.py          pattern sets, scrubbers, arbitration — the decision function
build*.py          walks the id set, applies §4's tiers in order, writes the CSV
eval_gold.py       scores the decision function against a labelled subset
units*.py          verbatim stop text -> expected bucket, the fast regression check
audit*.py          per-pattern match counts, to find inert regexes (§10.1)
validate*.py       the invariants of §10.4
manual.json        external overrides, keyed by trial id
```

`eval_gold.py` is not optional once a label file exists, and it must print **coverage
before accuracy**: labelled rows reached by a reason-bearing row, over labelled rows
that carry a gold reason. A run whose accuracy looks mediocre and whose coverage is
below 1.0 has a scope problem, and no rule change will touch it. Cross-tabulate the
misses by `Basis` and registry status in the same output (§10.5), so the diagnosis is
on screen rather than reconstructed by hand afterwards.

The decision function lives in exactly one module, imported by both the writer and the
scoring harness (§10.6). `manual.json` keeps externally-resolved rows out of the rule
set, so they survive rule changes and stay visible as a short, reviewable list.

**Version the rule module rather than editing it in place** once a deliverable has
shipped from it. A later generation changes arbitration and sometimes the label strings,
and a previous deliverable must stay reproducible from the module that produced it. Keep
the generations side by side under distinct names and never let a new one adopt an
existing module's filename — overwriting a shipped pipeline module destroys the only
record of how that table was built.

Put a header on each later generation saying what it changed and what the previous one
scored — `rules_g2.py` opening with "g1 shipped at 52.2%; g2 changes …" is how the next
reader knows which decisions are settled. A side-by-side of two generations' scores on
the same label file is the only honest way to claim an improvement.

Write a companion notes file beside the deliverable recording: scope and row count, the
label distribution, the confidence distribution, the route mix, **the prior-based share
and the instruction to filter on `Basis` before aggregating**, the score against any
labelled subset split into its evidence-backed and prior-based halves with before/after
numbers, and the bucket-boundary decisions from §8. A reader who disagrees with a
boundary can then re-filter rather than re-run.

## 14. Checklist for a new dataset

**Settle the inputs, the scope and the vocabulary first — they are worth more than the
rules.** Steps 0a–0d cost an hour between them and decide most of the score; steps 6–13
are where it is tempting to start and where the smallest gains are.

0a. **Name the six inputs of §0** and write them into the run's notes in the form given
    there. If you cannot fill a line, that is the first thing to go and find out.
0b. **Census the corpus (§2).** Assume the stop reason is not in it; confirm, and quote
    the command and its output in the notes.
0c. **Validate the registry field list one field at a time (§2)** before any batch call,
    and do not trust a documented alias to exist.
0d. **Reuse nothing without re-measuring it.** Pattern sets, priors and thresholds
    carried over from a previous run are hypotheses on a new dataset. The pattern sets
    in §5.5 in particular were built from one corpus's free text and will have both
    dead patterns and missing spellings on yours; §10.1 finds the first kind and §5.5's
    dump-and-read loop finds the second.

Then:

1. Fix the row set: outcome-table ids ∪ evaluation-set ids, never selected on a gold
   label. Then keep the three decisions of §1.1 apart: **a reason is owed only where the
   outcome was negative**, every other row takes the residual, and no row is ever
   dropped or left empty. Verify both directions — count labelled negative trials whose
   reason came from a "not a failure" branch (must be zero), and count rows carrying a
   reason whose outcome was not negative (must also be zero).
2. Diff the requester's label strings against the label file's; count the blank cells;
   and **get the scoring metric** (input 7). Residual or prior follows from the metric,
   not from the vocabulary (§1.2a) — and shipping so either can be derived costs
   nothing. This decides
   §5.3, §5.4 and §7.2.
3. Census the bundle sections and the sibling tables. Confirm whether the stop reason
   is present locally; assume it is not (§2).
4. Validate the registry field list with one call before batching (§2).
5. Split the failed set into stopped-early and completed-and-missed by status (§3).
6. Dump every distinct stop text. Read the unclassified ones. Build the pattern sets
   from what is there, including the typos (§5.5).
7. Implement the scrubbers before the pattern sets — negation in pandemic → safety →
   efficacy order, non-failure, uninformative (§5.2–5.4).
8. Implement arbitration: pandemic-as-cause, causal clause, first-named, safety
   override, weak-signal demotion (§5.6–5.7).
9. Add the other registry narrative fields for the trials whose `whyStopped` is blank or
   a pointer, with the study-as-subject requirement (§4.1).
10. Add the literature route with its relevance gates, not before (§6).
11. Add the posted-results route, and refuse the inferences in §7.3.
12. Measure the status-conditioned priors on the label set and apply them as the last
    tier, marked `Basis = NONE` and `Low` (§7.2). Test any proposed refinement for
    separation before building it (§7.2a).
13. Audit for inert patterns; hand-read a sample of every bucket; walk the nineteen trap
    classes (§10.1–10.3).
14. Assert the invariants, the row-set one by name (§10.4).
15. If labels exist: normalise identifier case, report coverage beside accuracy, score
    the evidence-backed and prior-based halves separately, score per annotator, compute
    the inter-annotator ceiling, and measure over-assignment too (§10.5). Diagnose any
    shortfall by route before touching a rule.
16. Rank the remaining unresolved rows, spend a bounded external-search budget on the
    top, record attempts and yield (§11).
17. Write the notes file: the decisions a reader might disagree with, the prior-based
    share of the table, and the warning that the table must be filtered on `Basis`
    before it is read as a set of findings.

Four diagnostics worth more than the headline:

* **Coverage below 1.0 means stop.** No rule change will touch it, and every accuracy
  figure computed inside the gap is flattering (§10.5).
* **The evidence-backed half near 100% means the rules are done.** Both runs reached it.
  Effort after that point belongs in scope or in honest reporting, not in patterns.
* **A prior-based half scoring much above ~70% deserves suspicion, not celebration.**
  A base rate cannot know anything about an individual trial. If it scores like
  evidence, check that no gold label has leaked into selection or into the prior (§1.1,
  §7.2).
* **The gap between the headline and the inter-annotator ceiling is the honest target**,
  and in both runs it was ~8 points, concentrated entirely in rows where nothing was on
  record. §12 argues that most of it is not recoverable from these sources.
* **A metric change can dwarf every rule change.** The §1.2a rows above differ by 0.147
  of AC1 on the scored subset and by **0.97** over the whole label set, on identical
  evidence and identical rules — one to two orders of magnitude more than the total gain
  from all the §5 and §6 rule work in either run. Before optimising anything, confirm
  which number is being optimised; then ship so that both can be computed.
* **A coefficient near zero or negative is a convention mismatch, not a bad model.**
  Prior-filled scored −0.041 while getting 100% of its located-text rows right. If a
  chance-corrected number collapses, check the residual convention and the label-string
  join before touching a rule — and check what fraction of gold is blank.
