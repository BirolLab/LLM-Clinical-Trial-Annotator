# Delivery-mode annotation methodology

How the `Delivery Mode` / `Confidence` / `Evidence` columns in
`delivery_mode_10_15_2026.csv` were produced, written so the same process can be
run on a new set of peptide-drug trials.

Run of record: 2026-10-15, 7,734 interventional trials (every NCT id in
`bundles_chunks/`). Code and data tables: `delivery_mode_pipeline/`.

---

## 1. Label scheme

| Label | Covers |
|---|---|
| `injection/infusion` | SC, IV, IM, ID, intrathecal, intraperitoneal, intravitreal, intratumoral, intra-arterial, intralesional, intrapleural, epidural, depot injection, pump/CSII, local infiltration |
| `Oral` | tablets, capsules, oral solution/suspension, sachets, gummies, drinks, foods, enteral/NG formula |
| `Topical` | skin cream/ointment/gel/lotion, transdermal patch, ophthalmic drops/emulsion, dental application to enamel, wound/cavity irrigation |
| `Other` | inhaled/nebulised, intranasal, implant (non-syringe), vaginal, rectal, sublingual/buccal, intravesical, surgically placed peptide graft/scaffold, ex-vivo/in-vitro use |
| `Unknown` | no delivery wording anywhere in the record and no external route established |

Judgement calls fixed up front, applied consistently:

- Ophthalmic drops count as `Topical` (topical to the ocular surface); intravitreal
  injection is `injection/infusion`.
- Transdermal patches are `Topical`; subcutaneous implants placed with a syringe
  (e.g. goserelin depot) are `injection/infusion`, while implants placed surgically
  or by trocar (histrelin, peptide-coated bone graft) are `Other`.
- A peptide used ex vivo to load a cell product that is then infused is
  `injection/infusion`, flagged in `Evidence`.
- Peptides measured as biomarkers rather than administered are not drugs; they end
  up `Unknown` with that stated.

`Confidence` is `High` / `Medium` / `Low` / `Unknown`, set by which evidence tier
fired (§5). Every row carries its provenance in `Evidence`, prefixed with the
peptide drug(s) identified, so any row can be re-checked without re-running.

---

## 2. Inputs, and why the bundle files are not enough

Check this first on a new dataset — it drove the whole design.

The per-trial bundles in this dataset (`bundles_chunks/*.md`, `bundles_md/`,
`bundles.jsonl`) hold only molecular evidence (ChEMBL, UniProt, PDB/PDBe, IntAct,
IUPHAR, EBI proteins) plus bundled publication abstracts. **They contain no
intervention text, so delivery mode is essentially absent from them.**
`trials.csv` carries intervention *names*, which yield a route keyword for only
**1,899 of 7,734** trials (25%).

Three local signals are still worth extracting:

| Source | What it gives |
|---|---|
| `records_long.csv`, column `query` | the drug names the pipeline searched per trial — the candidate drug list (one `awk` pass over 6.4 GB) |
| `by_source/chembl.jsonl` | per-drug `oral` / `parenteral` / `topical` boolean flags, `molecule_type`, `pref_name` |
| `bundles_chunks/*.md` abstracts | occasional route wording ("superimposed infusion of…") — weakest tier |

Everything else comes from the trial's own ClinicalTrials.gov record (§4), which is
the authoritative statement of how the drug was given.

---

## 3. Step 0 — build the trial list and candidate-drug index

```bash
cd <dataset>
# unique (nct_id, searched drug name) pairs -> work/nq.tsv   (~3 min on 6.4 GB)
awk -F',' 'NR>1{print $1"\t"$3}' records_long.csv | sort -u -S2G \
  | awk -F'\t' '$1 ~ /^NCT[0-9]+$/' > work/nq.tsv

# per-drug ChEMBL route flags and molecule types -> work/chembl_terms.tsv
DM_DATA=<dataset> DM_WORK=<dataset>/work python3 -I delivery_mode_pipeline/chembl_terms.py
```

Run of record: 14,536 pairs over 7,734 trials, 4,481 distinct drug-name strings
(1,777 with ChEMBL records). The name distribution is worth eyeballing — it tells
you which drugs dominate and therefore where lexicon work pays off (here: oxytocin,
GLP-1 RAs, insulins, cyclosporine, vancomycin, teriparatide, GnRH and somatostatin
analogues, peptide vaccines).

Note the ChEMBL flags aggregate across salt forms and products, so they are only
usable when exactly one of the three is set (liraglutide → parenteral only; cyclosporine
sets all three and is useless). They are the last-resort tier for that reason.

---

## 4. Step 1 — fetch the trial's own text

```bash
DM_WORK=<dataset>/work python3 -I delivery_mode_pipeline/fetch_ctg.py
```

ClinicalTrials.gov API v2, `filter.ids=` in batches of 50, fields
`NCTId, BriefTitle, OfficialTitle, InterventionType, InterventionName,
InterventionOtherName, InterventionDescription, ArmGroupLabel, ArmGroupDescription,
ArmGroupInterventionName, BriefSummary, DetailedDescription`.

Writes one JSON object per trial to `work/ctg_raw.jsonl`; resumable (skips ids
already present), retries 4× with backoff, and writes `{"missing": true}` for ids
the API no longer serves. 7,734 trials ≈ 155 requests, ~4 min, 25 MB.

This text carries explicit route wording for the peptide arm in ~85% of trials — the
single highest-value step, and it costs no model tokens because the parsing is done
by script.

---

## 5. Step 2 — annotate

```bash
DM_DATA=<dataset> DM_WORK=<dataset>/work DM_OUT=<dataset>/delivery_mode_<date>.csv \
  python3 -I delivery_mode_pipeline/annotate_delivery_mode.py
```

### 5.1 Identify the peptide drug

The route must belong to the *peptide*, not to a chemo partner or comparator, so each
intervention is tested against `lex.py` in this order:

1. **Curated alias table** (~700 entries): INN names, trade names and research codes
   mapped to a canonical drug (`victoza`/`saxenda`/`nn2211` → `liraglutide`), including
   code-named investigational peptides (`pvx 410`, `ucpvax`, `ltx 315`, `cat pad`, …).
   Names are matched after normalisation (lowercase, non-alphanumerics → single space),
   first whole-string, then over 3/2/1-token windows so that
   "subcutaneous semaglutide 1.0 mg" still resolves.
2. **Radiopeptide pattern** — isotope (`68Ga`, `177Lu`, `111In`, `64Cu`, `90Y`, `99mTc`,
   `18F`) adjacent to a peptide chelator/target (`DOTA*`, `NODAGA`, `PSMA`, `FAP-2286`,
   `RM2`, `JR11`, `exendin`, `PentixaFor`, `bombesin`, …).
3. **Peptide-vaccine pattern** — `peptide vaccine`, `multi-epitope`, `synthetic long
   peptide`, `neoantigen peptide vaccine`, etc., minus a negative list (`DNA vaccine`,
   `mRNA`, `plasmid`, `dendritic cell`, `lysate`, `whole cell`) so nucleic-acid and
   cell products are not counted as peptides.
4. **INN morphology** — stems `-tide`, `-relin`, `-relix`, `-actide`, `-pressin`,
   `-tocin`, `-fungin`, `-vancin`, `-kinin`, `-zomib`, or the literal word *peptide*.
   `oligonucleotide`-type words and the non-peptide `-golix` antagonists are excluded.

Every candidate is first screened against a not-a-drug list (placebo, saline, vehicle,
sham, radiation, surgery, exercise, diet, questionnaire, imaging, specimen collection…).
If no CTG intervention resolves, the drug names from `nq.tsv` are tried; if that also
fails, the row is annotated from the trial's interventions as a whole and capped at
`Low` with `peptide drug not resolvable from record` in `Evidence` (89 rows in the run
of record).

### 5.2 Route keyword extraction, and the masks that matter

Four regex families (`INJ`, `ORAL`, `TOP`, `OTH`) are run over a text field after a
**mask** pass that blanks phrases which look like routes but are not the drug's route.
The masks were derived by auditing results (§6) and are the part most worth porting:

| Mask | Why |
|---|---|
| `oral glucose tolerance`, `OGTT`, `oral antidiabetic/agents/medications`, `oral mucositis`, `oral care/hygiene/cavity`, `nothing by mouth` | OGTTs and background oral comparators appear constantly in GLP-1/insulin trials |
| `skin and soft tissue`, `skin infection/test/cancer/lesion/biopsy/graft/prick` | *skin* as an indication, not an application site |
| `nasal cannula/congestion/symptom/oxygen/CPAP/swab/carriage/polyp/mucosa` | oxygen delivery and AEs, not intranasal dosing |
| `vaginal delivery/birth/labour/exam/bleeding`, `transvaginal` | obstetric trials would otherwise all read as vaginal administration |
| `cochlear/dental/breast/valve implant`, `implant pocket/site/surface`, `device implantation`, `embryo implantation` | *implant* as a device or event |
| `intravenous line/access/fluid/catheter/hydration` | IV access, not IV drug |
| `Foley`, `balloon catheter`, `cervical ripening balloon` | "balloon instilled with saline" misread as instillation |
| `I. II. III. IV. V.` followed by whitespace | **Roman-numeral outline headings matched `IV`** |
| `gel electrophoresis`, `ultrasound/lubricating gel`, `gel pad`, `agarose` | lab and procedural gels |
| `patch test`, `patch clamp`, `injection site reaction`, `injection drug use`, `pump failure/function`, `bolus of saline/contrast`, `inhalation anaesthesia` | assorted |

Word-boundary traps that must be written carefully, not as bare substrings:

- `otic` → `\botic\b`, else it matches car**otic**, atheroscler**otic**, antibi**otic**.
- `dermal` → `(?<![a-z])dermal`, else it matches epi**dermal** (so "human epidermal
  growth factor receptor 2" read as topical).
- `instill` → only as `instill(ed|ation) … drop(s)` or `drops in/into the eye`, else
  Foley-balloon instillation reads as ophthalmic.
- `IV` / `SC` / `IM` / `PO` need `\b` and the Roman-numeral mask above.
- `depot` counts as injection; `implant` alone counts as `Other`, and injection wins
  when both appear (SC depot implants).

### 5.3 Evidence hierarchy

The first tier that yields a route wins; the tier sets `Confidence`. Within a tier,
multiple matched categories are resolved by count, ties broken
`injection/infusion > Other > Topical > Oral`, and the competing categories are listed
in `Evidence` with the confidence knocked down one step.

| # | Evidence | Confidence |
|---|---|---|
| 1 | Route word in the peptide intervention's **own name** | High |
| 2 | …in its **description** | High |
| 3 | …in its **other names** | High |
| 4 | …in an **arm description** whose `interventionNames` include it | High |
| 5 | …in the **brief/official title** | Medium |
| 6 | …in **summary/detail sentences that name the peptide** | Medium |
| 7 | **Web-verified drug-level route** (§5.4), route absent from the record | Medium (`v` source) / Low (class inference or multi-route) |
| 8 | …anywhere in the **study description** (not drug-specific) | Low |
| 9 | …in a **bundled publication abstract** | Low |
| 10 | **Context class** (§5.5) | Low |
| 11 | **ChEMBL flags** with exactly one of oral/parenteral/topical set | Medium |
| 12 | nothing | Unknown |

Tier 7 deliberately outranks tiers 8–9: a verified drug-level route beats a route word
found loose in a study description. Putting the generic text first produced wrong calls
(an insulin trial labelled `Oral` from "…receive TA-7284 100 mg orally…").

### 5.4 Drug-level route table (`drug_routes.tsv`)

Format: `drug ⇥ mode ⇥ evidence phrase ⇥ source ⇥ quality`, where `mode` is one label or
`Multiple:<label>|<label>…` most-common-first, and `quality` is `v` (label, SmPC,
protocol or peer-reviewed source retrieved) or `i` (class inference or weak source).
`v` → `Medium`, `i` and `Multiple` → `Low`. 243 entries as of the run of record,
covering ~190 drugs that the trial text left unresolved, plus class keys
(`peptide vaccine`, `radiolabelled peptide tracer`) used as fallbacks.

**This table must be built from retrieved sources, not from model recall.** The run of
record used five parallel web agents, each given one drug family, this prompt skeleton:

> Verify the human route of administration for these peptide drugs. Use web search —
> do not answer from memory; every line must be backed by something you retrieved
> (FDA/EMA label, DailyMed, drugs.com monograph, trial protocol, or a peer-reviewed
> review). Batch your searches (one review can cover a whole class). Classify into
> `injection/infusion` / `Oral` / `Topical` / `Other`; if two routes are genuinely
> common write `Multiple:<label>|<label>` most common first, and say in the evidence
> phrase which indication goes with which route. Output only TSV:
> `drug ⇥ label ⇥ evidence phrase (≤12 words) ⇥ source`.

Families used: (1) insulins + incretins/metabolic, (2) hormone analogues
(oxytocin/vasopressin/GnRH/somatostatin/PTH/ACTH), (3) antimicrobial, antifungal and
cytotoxic peptides, (4) peptide vaccines and code-named investigational peptides,
(5) radiopeptides and miscellaneous. Agents flag their own weak lines ("route not
retrieved, inferred from class") — record those as `i`, do not promote them.

**Multi-route drugs** are resolved per trial from the indication, always at `Low`, with
the reasoning written into `Evidence`:

| Drug | Rule |
|---|---|
| cyclosporine | dry eye / keratitis / ocular surface → `Topical`; dermatology → `Oral`; transplant, GVHD, haematology → `Oral` (predominant) |
| vancomycin | *C. difficile* / colitis / diarrhoea → `Oral`; otherwise → `injection/infusion` |
| colistin | cystic fibrosis / chronic airway infection → `Other` (nebulised); otherwise → `injection/infusion` |
| desmopressin | nocturia / enuresis → `Oral`; bleeding, vWD, surgery → `injection/infusion`; diabetes insipidus → `Oral` (oral and intranasal both used) |
| semaglutide, octreotide, glutathione | predominant route, stated as such |

### 5.5 Context classes

Applied only when no route wording was found for the drug, and only when no injection
keyword appears anywhere in the record:

| Trigger | Label |
|---|---|
| enamel / white-spot / caries / tooth / varnish / periodontal / remineralisation | `Topical` |
| supplement, gummies, smoothie, pasta, enteral or infant formula, beverage, dietary, milk/dairy/soy/hemp/silk/surimi peptide, hydrolysed casein/collagen | `Oral` |
| bone graft, ceramic granules, scaffold, spinal fusion, surgically placed | `Other` |
| vaccine, immunisation, Montanide, incomplete Freund's, GM-CSF, poly-ICLC | `injection/infusion` |
| dendritic cell, NK cells, pulsed with, ex vivo, culture medium | `injection/infusion` (noted as ex-vivo loading) |

These closed out 42 of the 54 trials that were otherwise `Unknown`, each at `Low`.

---

## 6. QA protocol

Non-negotiable: **stratified manual review**, not aggregate counts. Sample 5–8 rows from
every (label × confidence) cell, print `Evidence`, and ask whether the quoted wording
really describes the peptide. Each pass in the run of record found a distinct class of
systematic error, every one of them invisible in the totals:

| Pass | Found | Fix |
|---|---|---|
| 1 | nothing wrong at High tiers; lexicon missed ~270 code-named peptides | extended alias table + class patterns (§5.1) |
| 2 | `otic` inside "carotic/atherosclerotic", `dermal` inside "epidermal", `IV` from Roman-numeral headings, "vaginal delivery", Foley "instilled" | word boundaries + masks (§5.2) |
| 3 | generic study text outranking verified drug routes | moved drug table above tiers 8–9 |
| 4 | "implant pocket/valve implantation" → `Other`; estrogen **patch** in a depot-leuprolide arm → `Topical` | more masks; `depot` → injection |

`Other` fell from 625 rows to 462 across passes 2–4, almost entirely false positives.
Treat a large `Other` or `Topical` count as a symptom until proven otherwise.

Also sanity-check: the count with no peptide resolved (89 here — should be dominated by
adjuvant-only and comparator-only records), and the `Unknown` list read end-to-end (11
here — small enough to eyeball, and that is the point).

---

## 7. Output

`delivery_mode_<date>.csv` — one row per NCT id, sorted:

```
NCT Number,Delivery Mode,Confidence,Evidence
NCT00000392,Other,High,"peptide drug(s): peptide | description of arm ""Peptide T"": ""Peptide T given intranasally at a dosage of 2mg 3 times a day for 6 months"""
```

`Evidence` always names the peptide drug(s) identified, the evidence source, the quoted
snippet, and any downgrade reason in brackets.

Run of record: injection/infusion 6,151 · Oral 877 · Other 462 · Topical 233 ·
Unknown 11; confidence High 5,214 · Medium 1,885 · Low 624 · Unknown 11.

---

## 8. Porting to a new dataset — checklist

1. Confirm what the new bundles actually contain (§2). If they carry intervention text,
   read routes from them first and keep the CTG fetch as corroboration.
2. Build `work/nq.tsv` (or any `nct_id ⇥ drug name` list) and `work/chembl_terms.tsv`.
3. Fetch CTG text (`fetch_ctg.py`); non-CTG registries (EudraCT, jRCT, CTRI) need their
   own fetcher writing the same JSONL shape:
   `{nct, brief, official, interventions[{name,description,otherNames}], arms[{label,description,interventionNames}], summary, detail}`.
4. Print the top ~300 drug names by trial count and extend `lex.py` for anything frequent
   and unrecognised. Peptide/non-peptide is a chemistry call and can be made directly;
   **routes may not be** — they go through §5.4.
5. Extend `drug_routes.tsv` with web agents for the drugs the trial text leaves
   unresolved, ranked by trial count. Keep the `v`/`i` quality flag honest.
6. Run `annotate_delivery_mode.py`, then do the QA passes in §6 and re-run. Expect two
   or three rounds; each one is cheap and each one finds something.
7. Review the `Unknown` rows individually and leave them `Unknown` if the record really
   is silent — a wrong label costs more than a blank one.

Known limitations, carried forward: route words in a multi-drug arm description can be
attributed to the wrong agent (flagged via the "also mentions" note and a downgrade);
dose-escalation trials that switch route mid-study get a single label; trials comparing
two routes of the same peptide (oral vs SC semaglutide) get the dominant one with the
other listed in `Evidence`; 66 ids present in `trials.csv` have no bundle and are out of
scope for this run.

---

## 9. Run 2 — `delivery_mode_10_14_2026.csv` (pipeline rebuilt 2026-10-15)

`delivery_mode_pipeline/` had been cleared since run 1, so the pipeline was rebuilt
from this document on the same 7,734 trials. What changed is worth carrying forward.

### 9.1 Step 0 is now much cheaper

`bundles_chunks/ctg-studies-peptide-seqs.csv` (written by the peptide-sequence
annotation run) already holds, per NCT id, the **identified peptide drug(s)** plus the
intervention names each was read from (`[interventions: …]` inside its `Evidence`).
That replaces the 6.4 GB `records_long.csv` pass **and** most of `lex.py`'s alias
table: 241 canonical drug names instead of 4,481 raw name strings, and the drug↔
intervention link comes free for 5,767 trials. `build_index.py` turns it into
`work/trials_drugs.tsv` in seconds. Check for that file first on any future dataset.

The §5.1 lexicon is still needed as a fallback: peptide morphology, the radiopeptide
isotope+chelator pattern and class wording (`gonadotropin releasing hormone`,
`somatostatin analog`, …) resolve the interventions for trials the identification run
left as `unidentified peptide product` (190 rows end up annotated from the trial's
interventions as a whole, flagged in `Evidence`).

### 9.2 New: `trial_routes.tsv` (tier 0)

A few products' routes are established per *trial*, not per drug (a peptide skin
adhesive, thymosin β4 as eye drops in one trial and IV in another, an enteral formula).
Eight such rows carry a retrieved source keyed by NCT id, checked before the record
text and capped at `Medium`. Keep it small — it is not a place for guesses.

### 9.3 The masks and guards added this run

Run 1's mask list missed these, each found by stratified review (§6):

| Found | Fix |
|---|---|
| **`sub-cutaneously` / `intra-dermal` did not match the injection family**, and bare `cutaneous` then matched the tail → ACTH and vaccine trials labelled `Topical` | every `intra`/`sub`/`trans`/`naso` prefix takes `[\s-]?`; `cutaneous` needs `(?<![a-z])(?<!-)` |
| **`Carbapenemase` contains "enema"** → `Other` | `enema` → `\benemas?\b` |
| **Acthar Gel is injected** (IM/SC), not a topical gel | mask `(?:acth|acthar|adrenocorticotropic hormone|corticotropin)[^a-z]{0,25}gel` |
| `cutaneous T-cell lymphoma`, `metastatic cutaneous melanoma` | mask *cutaneous* + indication words |
| `DPP-IV` matched `\bIV\b`; `Sub Cut` matched nothing | mask `DPP[\s-]?(IV|4)`; add `\bsub[\s-]?cut\b` |
| oral background drugs named explicitly (`plus oral metformin`, `CellCept 2g po`, `Oralen Kontrazeptiva`) | mask `oral <drug>` for ~50 common non-peptide oral agents |
| `skin hydration/elasticity/firmness` as the *outcome* of an oral collagen supplement | mask skin/dermal + outcome words |
| `rectal carriage`, `nasal screening`, `carriage of` | mask swab/carriage sites |
| `patch test` spelled `bacitracin-patch`, `blood patch`, `post-implantation`, `cardiac implant` | more masks |
| "in vitro activity", "in vitro fertilisation" read as a route | `ex vivo`/`in vitro` removed from the `Other` family; in-vitro use is caught by a context class instead |

**Nearest-drug-wins proximity guard** (the single most useful addition). A route word
is discarded when a *co-administered* drug is named closer to it than the peptide is:
tokens of the trial's non-peptide intervention names are compared with the peptide's
within ±60 characters of the match. This fixed "NPH insulin once daily plus **oral**
metformin" (→ insulin detemir, injection) while keeping "**Oral** Colistin and
Neomycin" (→ colistin, oral) and "Zoladex 3.6 mg **Sub Cut**" (→ injection). It moved
162 labels on first application. Applied to tiers 2, 4, 5 and 6.

Two further ordering refinements:

- An intervention **description** that names a different drug and not the peptide is
  downgraded to `Medium` with that said in `Evidence` (CTG records sometimes attach
  the wrong description to an arm — e.g. a semaglutide intervention described as
  "Dapagliflozin oral once daily").
- For a **vaccine or cell product**, the §5.5 context class is checked *before* the
  generic study-description tiers; loose "oral" wording in those records is almost
  always a background drug. The food/supplement context class was also demoted below
  the vaccine classes ("vaccination is supplemented by …" was reading as `Oral`) and
  is additionally run in a name-only scope, where `supplement`/`diet`/`formula` in an
  intervention name is reliable.

### 9.4 Result

`delivery_mode_10_14_2026.csv`, 7,734 rows:

injection/infusion 6,253 · Oral 876 · Other 392 · Topical 207 · Unknown 6
confidence High 4,789 · Medium 2,128 · Low 811 · Unknown 6

Evidence tiers: intervention description 3,769 · drug-level route 1,779 ·
intervention name 723 · arm description 574 · study text naming the peptide 421 ·
other names 113 · titles 205 · context class 82 · generic study description 47 ·
trial-level route 8 · abstract 8.

`drug_routes.tsv` holds 161 lines (152 drugs plus class/alias keys) from six web-agent
families — the five of §5.4 plus one sweep over the products the record left unresolved
(PuraStat, EO2401, DGX-001, TS-104, FSR peptide, HSP70-peptide complexes, Kate Farms
Peptide 1.5, P-4/P-15 adhesive, Pep19, …). 14 lines are `i`-quality; everything else
cites a retrieved label, SmPC, protocol or paper.

The six `Unknown` rows are right to be blank: four trials measure a natriuretic
peptide or vasoactive-peptide polymorphism as a **biomarker** rather than giving a
drug (said so in `Evidence`), one gives no peptide at all, and one (preimplantation
factor, NCT03593460) states no route anywhere and no external source was retrieved.

---

## 10. Run 3 — `delivery_mode_10_14_2026.csv` (pipeline rebuilt again 2026-10-15)

`delivery_mode_pipeline/` had been cleared a second time. Everything in `work/`
survived (`trials_drugs.tsv`, `ctg_raw.jsonl`, `abstracts_by_nct.tsv`,
`chembl_terms.tsv`, `dm_pass1-14.csv`), so steps 0 and 1 did not need re-running
and no CTG fetch was repeated.

### 10.1 Recovering the route tables instead of re-researching them

`drug_routes.tsv` and `trial_routes.tsv` were gone, but §5.4's format writes the
retrieved **evidence phrase and source verbatim into every `Evidence` string
that uses them**, so both tables rebuild losslessly from any output CSV of the
previous run: `recover_routes.py work/dm_pass14.csv drug_routes.tsv
trial_routes.tsv` returned 151 drugs and 8 trial-level rows, with `v`/`i`
quality inferred from the confidence the row carried. **Keep that property** —
it is the reason a cleared pipeline costs minutes rather than six web-agent
families. Only 19 products needed new web work this run.

### 10.2 New guards (each found by the §6 stratified review)

| Found | Fix |
|---|---|
| **A co-intervention named "Placebo nasal spray" out-competed the peptide for its own "intranasally"** — the guard counted `nasal` as a rival drug token | `lex.ROUTE_WORDS`: route words and not-a-drug names are stripped from the rival-token set |
| "insulin SC … whereas group A receive tablets of metformin **orally**" → `Oral`; metformin was not a listed intervention, so the guard could not see it | `lex.CO_DRUGS`, ~110 common non-peptide co-administered agents, added to the rival-token set from free text |
| The guard used a ±60-char window; in a summary paragraph *both* drug names fall outside it, so "400 microgram misoprostol **rectally**" survived in an oxytocin trial | distances are now measured over the whole field; the window is only the slack the peptide gets before the rival wins outright |
| An arm labelled **"Misoprostol group"** was read for the oxytocin arm (CTG lists every intervention under every arm) | an arm whose *label* names another agent and not the peptide is skipped |
| **"Alcoholic Drinks in Diabetes"** → `Oral` | bare `drink`/`beverage`/`smoothie`/`shake` removed from the ORAL family; they belong to the food/supplement *context class*, which is scoped correctly |
| An in-line enteral lipase cartridge hydrolysing formula "**ex vivo**" → `injection/infusion` | the cell-product class needs a real cell noun; bare `ex vivo`/`culture medium` no longer trigger it |
| **"CD4+ T cell counts"** and a stray **"GM-CSF"** diverted cyclosporine, enfuvirtide and glutathione trials into the vaccine/cell-product class, which §9.3 runs *ahead* of the drug-level route — 33 cyclosporine transplant trials were labelled `injection/infusion` instead of `Oral` | `is_vaccine_like` is computed from the **peptide's own** name/description/drug name, not the whole record; `t cells?`/`lymphocytes` alone dropped from the class |
| "those in **stage III or IV**", "grade III-IV" matched `\bIV\b` | the Roman-numeral mask handles `III or IV`, `III-IV`, `I to IV` |
| `Thymosin-α1` normalised to `thymosin 1`, missing its `thymosin alpha 1` route entry | `norm()` maps greek letters to their latin names before stripping non-alphanumerics |
| `Gallium-68 labelled DOTA-conjugated` did not match the radiopeptide pattern (only `68Ga` did) | isotope pattern accepts element-name-first and symbol-first forms |
| Trials whose drug was left unresolved never reached tier 7, because the lookup keyed on the drug name only | tier 7 falls back to matching `drug_routes` keys, then class keys (`radiolabelled peptide tracer`, `octreotide`, `peptide vaccine (unspecified)`, `leuprolide`), against the trial's own intervention names |

Two additions to `Evidence` rather than to the labels:

- A peptide **measured as a biomarker** now says so explicitly, tested on the
  peptide intervention's own text and only when it carries no dose/administration
  wording (an early version scoped to the whole record and swallowed a real
  Thymosin-α1 dosing trial).
- §9.4's known limitation — a trial comparing two routes of one peptide gets a
  single label — is now recorded: 120 rows carry
  `[trial also includes <label>: "<intervention>"]`, e.g. NCT02470039 is
  `injection/infusion` for insulin glargine and notes the oral insulin 338 arm.

### 10.3 Web work this run

19 products the record left unresolved, in two agent families (investigational
peptides; imaging tracers, grafts and dental/periodontal peptides), using the
§5.4 prompt skeleton. 18 came back with a retrieved source (`v`); **TS-104** is
`i` — no human route is published, only preclinical IV dosing, and the agent
flagged it rather than guessing. `drug_routes.tsv` now holds 169 lines.

### 10.4 Result

`delivery_mode_10_14_2026.csv`, 7,734 rows, one per `# NCT…` heading in
`bundles_chunks/` (verified set-equal):

injection/infusion 6,263 · Oral 847 · Other 411 · Topical 208 · Unknown 5
confidence High 4,875 · Medium 2,040 · Low 814 · Unknown 5

Evidence tiers: intervention description 3,842 · drug-level route 1,492 ·
arm description 770 · intervention name 627 · study text naming the peptide 588 ·
titles 223 · context class 128 · other names 32 · generic study description 12 ·
trial-level route 8 · abstract 7 · none 5.

The five `Unknown` rows are right to be blank: four measure a natriuretic or
vasoactive peptide as a **biomarker** rather than giving a drug, and one
(NCT04508725) gives no peptide at all. sPIF (NCT03593460), Unknown in run 2, is
now `injection/infusion` on a retrieved source.

Regression cases to re-check after any lexicon change: NCT07582471 (insulin SC vs
oral metformin → injection), NCT02472600 (Oral Colistin and Neomycin → Oral),
NCT01056965 (davunetide intranasal → Other), NCT02518022 (alcoholic drinks →
injection), NCT02750501 (enteral peptide formula → Oral), NCT03680339 (misoprostol
rectal in an oxytocin trial → injection), NCT00571662 (cyclosporine transplant →
Oral).

---

## 11. Run 4 — `delivery_mode_10_14_2026.csv` (QA-only pass, 2026-10-15)

`delivery_mode_pipeline/` had been cleared a third time and the deliverable CSV
with it, but all of `work/` survived, including run 3's final output
`work/rb_pass12.csv`. That file reproduces §10.4's distribution exactly
(6,263 · 847 · 411 · 208 · 5 and 4,875 · 2,040 · 814 · 5), so steps 0–2 were
**not** re-run: no CTG fetch, no `records_long.csv` pass, no web-agent families.
The run was a §6 QA pass on top of run 3.

### 11.1 Route tables recovered again, and `recover_routes.py` kept

§10.1's property held: `recover_routes.py work/rb_pass12.csv` rebuilt
`drug_routes.tsv` (125 drugs) and `trial_routes.tsv` (8 rows) from the Evidence
strings alone. Two notes for next time:

- The trial-level tier writes `trial-level verified route:`, not
  `trial-level route:` — run 3's recovery regex missed all 8 rows until the
  `(?:verified )?` was added. The script in `delivery_mode_pipeline/` now has it.
- 125 drugs recovered against the 169 lines §10.3 reports, because a table entry
  only survives in a CSV if some trial actually used it. Recovery is lossless for
  *used* entries, not for the whole table. Unused entries (`insulin glulisine`,
  `linaclotide`, `plecanatide`, `insulin tregopil`) are gone and would need
  re-retrieval if a future trial needs them. **The table itself is still worth
  keeping under version control** — recovery is a backstop, not a substitute.

### 11.2 The error class this pass found: co-drug route attribution, again

§10.2's nearest-drug-wins proximity guard fixed this for rivals it can *see* —
listed interventions plus `lex.CO_DRUGS`. The stratified review found 63 rows
where it could not: the rival agent was named only inside the quoted snippet, or
was not a drug at all. All 63 were non-injection labels on peptides that the
record or a retrieved label puts on a needle.

| Sub-class | Rows | Example |
|---|---|---|
| Oral antidiabetic / OGTT / meal beside an insulin or incretin | 31 | NCT01135992 `OAD (oral anti-diabetic drug)` → insulin degludec was `Oral`/**High** |
| Oral endocrine agent or add-back patch beside a GnRH analogue | 18 | NCT05439499 `FCN-437c … capsules for oral administration` → goserelin |
| Oral melphalan/prednisone/dexamethasone/thalidomide beside a proteasome inhibitor | 6 | NCT01208766 `Melphalan … p.o.` → bortezomib |
| Oral co-drug beside glatiramer acetate | 3 | NCT00451204 estriol capsule; `Copaxone — Injection, once a day` |
| CTG record states a route the drug does not have | 2 | NCT01240941 `Goserelin 3.6 mg **orally** monthly`; NCT00102934 enfuvirtide `90 mg **tablet** taken orally` |
| Route word is not a route | 3 | NCT06624956 **PATCH** is the trial acronym (the drug is a GIK *infusion*); NCT00542126 preembryos `fail to **implant**`; NCT02189395 `Nil **per os**` |

Two mask gaps worth porting, both near-misses on existing masks: §5.2 masks
`oral glucose tolerance` but the records also say **`oral glucose solution`**, and
`nothing by mouth` but not **`nil per os`**. §9.3's `oral <drug>` mask list needs
`anti-diabetic` spelled with the hyphen and in the plural, and needs the
abbreviations `OAD` / `OGLD` / `oral antihyperglycemic`.

`NCT02944110` became the 6th `Unknown`: the only administered agents are oral
**LY2409021**, a small-molecule glucagon receptor antagonist, and placebo —
glucagon itself is the endogenous hormone under study, so no peptide is given.

### 11.3 How the corrections were evidenced

`apply_review_fixes.py` does not assert a route from model knowledge. For each
row it prefers the trial's own record — the peptide's own intervention text
(12 rows, `High`), else a summary/detail sentence naming the peptide (5 rows,
`Medium`, §5.3 tier 6) — and otherwise cites the recovered `drug_routes.tsv`
entry verbatim with its source, at `Medium` for `v` and `Low` for `i` (45 rows).
Only `NCT04025372` rests on a class inference (`gnrh analogue (unspecified)`,
quality `i`) and is `Low` accordingly. Every corrected row carries
`[corrected on review: was <label>; <reason>; superseded wording: …]`, so the
label it replaced stays auditable.

Two script bugs found while doing this, both worth avoiding on a port:

- Taking `Evidence.split(' | ')[0]` as the drug list **truncates it**, because
  multiple peptide drugs are themselves `' | '`-separated. Parse segments up to
  the first evidence-tier marker instead (`split_head`).
- Quotes lifted from CTG text carry literal newlines, which put embedded
  newlines in the CSV. All Evidence text is now whitespace-collapsed; the file is
  7,735 physical lines for 7,734 rows.

A generalized detector (does the quoted snippet name a non-peptide oral co-drug
while *not* naming the peptide?) was run over every non-injection row afterwards
and returns 10 hits, all confirmed correct: self-assembling peptide P11-4 and
CPP-ACP are genuinely topical dental peptides, nafarelin is genuinely intranasal,
and the cyclosporine rows follow §5.4's indication rule.

### 11.4 Result

`delivery_mode_10_14_2026.csv`, 7,734 rows, set-equal to the `# NCT…` headings in
`bundles_chunks/`:

injection/infusion 6,325 · Oral 789 · Other 410 · Topical 204 · Unknown 6
confidence High 4,850 · Medium 2,062 · Low 816 · Unknown 6

Net of run 3: +62 `injection/infusion`, −58 `Oral`, −4 `Topical`, −1 `Other`,
+1 `Unknown`. §6's warning generalises — treat a large `Oral` count on an
injectable-drug corpus as a symptom too, not just `Other` and `Topical`.

Regression cases to re-check after any lexicon change, in addition to §10.4's:
NCT01135992 (insulin degludec + OAD → injection), NCT05439499 (goserelin +
FCN-437c capsules → injection), NCT01240941 (goserelin "orally" record error →
injection), NCT00102934 (enfuvirtide "tablet" record error → injection),
NCT06624956 (PATCH acronym, GIK infusion → injection), NCT02189395 (nil per os →
injection), NCT05107219 (linaclotide/plecanatide "Given PO" → **Oral**, must not
regress), NCT02807363 (leuprolide oral tablet → **Oral**), NCT04064411
(abaloparatide transdermal → **Topical**), NCT02944110 (glucagon antagonist →
Unknown).

---

## 12. Run 5 — `delivery_mode_10_14_2026.csv` (pipeline rebuilt again, 2026-10-22)

`delivery_mode_pipeline/` had been rebuilt and `work/` repopulated earlier the
same day (CTG fetch, `trials_drugs.tsv`, `chembl_terms.tsv`, `abstracts_by_nct.tsv`
and `dm_pass1-13.csv`), but no deliverable had been written. `drug_routes.tsv`
(126 lines) and `trial_routes.tsv` (8 rows) survived from 2026-10-15, so **no web
agents were run this time**; `recover_routes.py` was not needed either. The run
re-verified reproducibility (`dm_pass14` reproduces `dm_pass13` byte-for-byte),
then did §6 stratified review and §8.6 iteration.

### 12.1 The error class that dominated this run: who owns the route word

Six of the eight defects found were the same shape — a route word read for the
wrong agent — but each needed a different fix, and three were *caused* by the
machinery meant to prevent it.

| Found | Fix |
|---|---|
| **`intradermal` was in the mask list** (added to stop the TOP family's `dermal`), so every "administered intradermally" vanished from the INJ family too — Vacc-4x read as `Unknown`/`Oral` | drop the mask; §9.3's `(?<![a-z])(?<!-)dermal` lookbehind already excludes epi-/intra-/trans- |
| **`is_not_a_drug("PEX168 or placebo")` was True** — one substring match dropped the trial's only peptide intervention | the name must be *nothing but* non-drug terms; a real agent before or after a connective (`or`, `vs`, `and`) survives. `Placebo intravaginal ring` is still not a drug |
| **`resolve_peptide_ivs` matched on `trials_drugs.tsv`'s `interventions:` column, which lists *every* intervention of the trial** — nivolumab, salbutamol, imiquimod and bicalutamide were all "the peptide", and their routes were read for it | match on the drug name first, then peptide morphology, and use the intervention list only as a last resort — and ignore it when it selects everything. The old proximity guard had been silently compensating for this |
| A **salt or class word in the peptide's own name** (`leuprorelin **acetate** 3.75 mg injection`) counted as a rival drug sitting on top of its own route word | `rivals -= GENERIC_PEP` (acetate, acid, hormone, human, recombinant, analogue, peptide, vaccine, product) |
| The **record's own shorthand** for the peptide (DDAVP, GSH, CsA, Lantus, Zoladex, HOE901, NATPARA, Restasis) is not in the canonical drug name, so the guard could not find the peptide at all and discarded its route | `lex.PEP_ALIAS`, ~30 entries, added to `pep_tok` |
| The peptide's own description refers to it **generically** ("one mg of each **peptide** will be administered by subcutaneous injection"), with a co-drug named later in the same field | `SELF_REF` (peptide, vaccine, immunotherapy, study drug) is added to `pep_tok` for the peptide's own description only |

Two attempts were tried and **rejected**, both worth recording because they look
right:

- *Exempting every token of the peptide intervention's name from the rival set.*
  It fixes GB001 and VEGFR2-169 but clears genuine co-drugs out of combination
  names (`teriparatide and raloxifene`, `Anti-Androgen Therapy: Bicalutamide`) —
  76 labels moved, roughly half of them wrong.
- *Tightening `SLACK` from 10 to 0* so a strictly nearer rival always wins. It
  moved 12 rows, fixed neither case that motivated it, and broke three
  (over-encapsulated oral GLP-1, oral peptide absorption, a vaccine title).

What did work for the residue is **clause-level attribution** (§12.2): distance
is the wrong instrument once two agents are within a few characters of each other.

### 12.2 New: clause attribution in `contradiction_pass.py`

The pass now splits the quoted snippet on `and / plus / vs / versus / compared
to / ; / + / followed by / whereas / while` and asks which agent shares the
*clause* with the route word, falling back to distance only when the clause test
is silent. `Alogliptin 12.5 mg, tablets, orally, once daily and insulin for up to
26 weeks` splits into an alogliptin clause that owns "tablets, orally" and an
insulin clause that owns nothing — the row corrects from `Oral`/High to
`injection/infusion`. The pass also now runs on `Topical` and `Other` rows, but
outside `Oral` only on that clause trigger, which is self-protecting: a genuinely
topical peptide names itself in its own clause (`local antibiotic irrigation with
vancomycin`, `Curodont Repair applied topically`) and is left alone.

**`head_drugs` was truncating the drug list** exactly as §11.3 warns — the regex
`(.*?)(?= \| )` stops at the first separator, so a 3-drug trial looked
single-drug and passed the pass's single-drug gate. Eight wrong corrections came
from that one character class (over-encapsulated oral GLP-1 → injection, "Oral
Administration of Peptides" → injection). Parse segments up to the first
**tier marker**, not to the first `' | '`. Corrections: 22 → 14.

### 12.3 Other guards added this run

| Found | Fix |
|---|---|
| A description that gives one route then **switches** ("CsA 2.0 mg/kg **intravenous** Q12h on days -1,0,+1 then **converted to oral** … until day+80") was labelled by the induction route | `switch_route`: on `convert/switch/change/transition/step down/roll over **to**` + route word within 25 chars, and only when the switch sits within 120 chars of the peptide, the maintenance route wins. `followed by` is deliberately **not** a switch verb — it usually introduces a successor *agent* ("followed by oral administration of anti-resorptive drug"). 4 rows |
| A **comparator's dosage form** read as the peptide's route (`placebo-matching tablets, orally`, `placebo pill`, `TAK-385 placebo tablet`) | mask `(placebo\|dummy\|sham)[-\s]?(matching)?[-\s]?(pill\|tablet\|capsule\|drops\|gel\|cream\|spray\|solution\|syrup)` and `(matching\|matched\|dummy) placebo` |
| `vaginal repair/surgery/prolapse`, `cervical or vaginal cancer` → `Other` | extend the vaginal mask to surgery and indication words |
| `Pd-103 brachytherapy **implant**` → `Other` | mask `(brachytherapy\|seed\|radioactive\|Pd-103\|I-125\|titanium)[-\s]implant` |
| `intranasally … using a **syringe** with a Mucosal Atomization Device` → `injection/infusion` | mask `syringe` when an atomiser/mucosal/enteral/feeding word is within 30 chars either side — it is an applicator, not a needle |
| **`ACTHER GEL`** (a record's spelling of Acthar) escaped §9.3's Acthar mask | `acth\w*` instead of `acth\|acthar` |
| Oral co-drugs the §10.2 rival set did not know | ~30 added to `lex.CO_DRUGS`: glucophage, casodex, arimidex, femara, nolvadex, xtandi, zytiga, palbociclib/ribociclib/abemaciclib, laquinimod, raloxifene, alendronate and the other bisphosphonates, the checkpoint antibodies, imiquimod, salbutamol, delafloxacin, omarigliptin, giredestrant, fulvestrant, trimethoprim/sulfamethoxazole |
| A **peptide-vaccine trial whose intervention names are bare epitope codes** (`PCLUS 3-18 MN`, `Tyrosinase, MAGE-3, GnTV`, HPV16 E6/E7 peptides) never reached the §5.5 vaccine class, which §10.2 had correctly scoped to the peptide's own text | a record-level vaccine check **as the last branch of `context_class` only** (it receives `whole` only from the tier-10 call, so the early §9.3 call is unaffected). Triggers on peptide-vaccine wording, or on `vaccin\|immunisation` in the record plus `peptide` in the peptide's own intervention name |
| A peptide listed as a `DIAGNOSTIC_TEST` and described in measurement terms was not read as a biomarker, because `DOSEWORD`'s `treatment with` matched "Biomarker monitored **treatment with** measurement of NT-proBNP" | type-scoped branch in `is_biomarker`: diagnostic-test-only interventions with measurement wording and no administration verb are biomarkers whatever dose words the sentence carries |

### 12.4 Result

`delivery_mode_10_14_2026.csv`, 7,734 rows, set-equal to the `# NCT…` headings in
`bundles_chunks/`, sorted by NCT id, 7,735 physical lines (no embedded newlines):

injection/infusion 6,340 · Oral 792 · Other 394 · Topical 201 · Unknown 7
confidence High 4,888 · Medium 2,034 · Low 805 · Unknown 7

Evidence tiers: intervention description 3,730 · drug-level route 1,619 ·
arm description 704 · intervention name 612 · detail sentence naming the peptide
377 · summary sentence naming the peptide 181 · context class 164 ·
brief title 141 · official title 104 · other names 63 ·
generic study description 14 · trial-level route 8 · biomarker/no-peptide 7.

14 rows carry `[corrected on review: …]`, 4 carry
`[route switches mid-course; maintenance route taken]`, 45 carry
`[trial also includes <label>: …]`. 133 rows could not resolve the peptide from
the record and are capped at `Low`.

The seven `Unknown` rows were read individually and are right to be blank: four
measure a natriuretic or vasoactive peptide as a **biomarker** (NCT01820780,
NCT04000815, NCT05160779, NCT05406635), two give only a small-molecule receptor
antagonist against an endogenous peptide (NCT02944110 glucagon, NCT03733145
angiotensin II), and one (NCT00448136) administers no peptide at all —
bevacizumab, 5-FU, streptozotocin and capecitabine.

The `Other` bucket was audited by trigger rather than by count: intranasal 309,
inhaled 41, implant 17, vaginal 8, graft/scaffold 6, sublingual/buccal 4,
rectal 3, in-vitro 2, 4 unclassified (all checked by hand and correct). That
distribution is the shape to expect — §6's warning is about `Other` rows that
*cannot* be traced to a trigger.

### 12.5 Regression set

All of §10.4's and §11.4's cases pass. Add these, which this run's changes
turn on:

NCT00659789 / NCT01712256 (Vacc-4x **intradermally** → injection),
NCT01965509 (`PEX168 or placebo` → injection),
NCT00639925 ("each peptide … subcutaneous injection" → injection),
NCT06429566 (GB001 oral spray → Oral),
NCT03817125 (vancomycin trial, nivolumab description must **not** win),
NCT01535027 (`teriparatide and raloxifene` → injection, not Oral),
NCT01452685 / NCT03931915 / NCT07015268 (leuprorelin + oral placebo tablet → injection),
NCT00571662 (CsA IV then converted to oral → **Oral**),
NCT05018637 ("followed by oral anti-resorptive" must **not** switch → injection),
NCT00286429 (`Alogliptin … tablets, orally … and insulin` → injection),
NCT07249554 (over-encapsulated oral GLP-1 → **Oral**, must not be "corrected"),
NCT00468884 (Oral Administration of Peptides → **Oral**),
NCT00001386 / NCT00153569 / NCT00002916 (bare-epitope peptide vaccines → injection),
NCT05406635 (natriuretic peptides as a diagnostic test → **Unknown**, biomarker),
NCT02424708 (intranasal GSH via atomiser syringe → Other),
NCT02155803 (ACTHER GEL → injection).

---

## 13. Run 6 — `delivery_mode_10_14_2026.csv` (QA pass on run 5, 2026-10-22)

`delivery_mode_pipeline/` and all of `work/` survived from run 5 earlier the same
day, but **no deliverable CSV had been written**. Run 5's final output
(`work/final_b.csv` = `work/dm_pass34.csv`) reproduces §12.4's distribution
exactly, and the pipeline reproduces it byte-for-byte:

```bash
DM_DATA=. DM_WORK=work DM_OUT=work/dm_pass35.csv python3 -I delivery_mode_pipeline/annotate_delivery_mode.py
python3 -I delivery_mode_pipeline/contradiction_pass.py work/dm_pass35.csv work/dm_pass36.csv
python3 -I delivery_mode_pipeline/apply_review_fixes.py  work/dm_pass36.csv delivery_mode_10_14_2026.csv
```

So steps 0–1 were not re-run: no CTG fetch, no `records_long.csv` pass, and no
web-agent families (`drug_routes.tsv` survived, 126 lines). The run was §6
stratified review plus §8.6 iteration. Six defect classes, all found by review
and invisible in the totals.

### 13.1 The error class that dominated this run: a lossy route table

§11.1 warned that `recover_routes.py` is lossless only for *used* entries. It is
also lossy in a way that is silent: **`Multiple:` collapses to a single mode**,
because an output row records the mode that was *resolved*, not the options. By
run 5 all four multi-route entries had become single-mode, which disabled
§5.4's indication rules completely — `resolve_multi` is only reached when the
table says `Multiple:`. Every cyclosporine trial was `Oral` (dry-eye and
eye-drop trials included), every vancomycin trial `injection/infusion`
(*C. difficile* and FMT trials included), every desmopressin trial injection
(nocturia and enuresis included). 35 rows, and nothing in the counts showed it.

Restoring the four `Multiple:` modes needed the triggers tightened too, because
§5.4's rules were written to be read against a whole record and are not specific
enough for that:

| Trigger | Problem | Fix |
|---|---|---|
| `c.?\s?diff\w*` | matched **"c differentiation"** (osteogenic differentiation) | `\bc\.\s?diff\w*`, plus `\bcdi\b`/`\bcdad\b` |
| bare `colitis`, `diarrh` on vancomycin | matched any record mentioning them | `ulcerative colitis`, `f[ae]cal microbiota`, `microbiota transplant`, `gut microbiot\w*` |
| C. difficile named as an **adverse outcome** of surgical prophylaxis | NCT02285140, NCT04401553 read as oral-vancomycin trials | `MULTI_VETO`: a prophylaxis/SSI/perioperative title vetoes a trigger found only in the body |
| bare `ocular`, `sjögren` on cyclosporine | systemic CsA for ocular Behçet's (NCT00167583) and Sjögren (NCT01693393) read as `Topical` | the ocular branch needs an ophthalmic *formulation* word (`eye drop`, `ophthalmic`, `Restasis`, `ocular surface`, dry eye) |
| `ventilator-associated` on colistin | VAP colistin is IV; only CF/bronchiectasis is the nebulised regimen | trigger reduced to `cystic fibrosis\|bronchiectasis` |

`resolve_multi` also now reads the indication from the **title first and then
from text within ±250 characters of a mention of the drug**, not from the whole
record — the same scoping lesson as §10.2, applied to indications instead of
routes.

### 13.2 Clause attribution moved from the contradiction pass into the guard

§12.2 added clause-level attribution to `contradiction_pass.py`, where it only
reaches rows that survive that pass's narrow gate. The same instrument belongs
in `guard_ok` itself, ahead of the distance test: **a route word whose own
clause names a rival and not the peptide is not the peptide's, however close the
peptide sits in the next clause.** `SLACK` was letting those through, and §12.1
had already shown that tightening `SLACK` is not the answer.

`or` is a clause separator here although §12.2 deliberately left it out of the
contradiction pass: "cultured gut microbiota **rectally** or oral vancomycin"
(NCT02857582) needs it. 13 label changes, every one verified by hand — nine were
a co-drug's route read for cyclosporine in a transplant regimen (MMF IV,
treosulfan/fludarabine iv, IL-2 subcutaneously, luspatercept subcutaneously),
which is §11.2's error class reaching rows the review had not sampled.

### 13.3 Other guards added this run

| Found | Fix |
|---|---|
| **An arm label carries the route its description omits** ("Apraglutide subcutaneous (SC) injections, once weekly" / description "Peptide analogue of GLP-2") | tier 4 prepends the arm label to the arm description when the label names the peptide. 4 rows; the label is already required not to name a rival alone |
| An **opaque product name with a self-describing description** ("Purastat Arm" / "an aqueous self-assembling peptide solution … RADA16") never resolved, so the comparator arm's sucralfate enema was read as the peptide's route | a 4th resolution stage: peptide morphology over the intervention's **description**, between morphology-over-name and the `ivnames` last resort, and only when it singles out a strict subset |
| A co-intervention named only in its **otherNames** (`Standard Care Arm` / `["Sucralfate enemas — …"]`) was invisible to the rival set | otherNames join the rival tokens — but **never for the peptide's own interventions**, where the trade name sits on top of its own route word (`Ciclosporin`/`CicloMulsion`, `Polymyxin B in Normal Saline`/`Antibiotic`) |
| Class and housekeeping words (`antibiotic`, `therapy`, `standard`, `care`, `arm`, `group`) acted as rival agents | `GENERIC_CLASS`, subtracted from the rival set. Saline, water and placebo are deliberately **not** in it — they are things actually given, and a route word beside them is theirs (NCT02937896, nasal desmopressin + IV saline) |
| **`Aerosolized`** did not match `\baerosol\b` | `\baerosoli[sz]\w*\b`. The §5.2 word-boundary lesson, once more |
| **Intrawound antibiotic powder** (vancomycin powder placed in a surgical bed) had no route word at all, so it fell through to the drug table and came back `injection/infusion` | TOP gains `intra-?wound`, `local wound`, `powder … applied/placed/packed/sprinkled/poured`, `applied/placed/packed/instilled … wound/surgical bed/fracture site/incision`, `wound … packed/filled`, `administered/applied locally`. Not bare `powder`: it is equally a dosage form for inhalers, injections and sachets |
| `closing the **subcutaneous tissue** and skin` read as an SC injection | mask `sub[\s-]?cutaneous (tissue\|fat\|layer\|space\|pocket)` — anatomy, not a route |

### 13.4 Run 4's manual corrections had been silently dropped

`apply_review_fixes.py` (§11.3, 63 hand-verified rows) stopped being part of the
chain when run 5 rebuilt the pipeline, and §12 did not notice: the generic
guards reproduce 46 of the 63 but **17 were back to the wrong label**, every one
of them §11.2's co-drug class on a peptide that is injected (saxagliptin tablets
beside insulin, Glucophage tablets beside Victoza, abiraterone beside
leuprolide, an estradiol patch beside leuprolide, melphalan beside carfilzomib).

The script now takes its input and output as `argv[1]`/`argv[2]` and **skips any
row the pipeline already gets right**, so it re-evidences only the residue (5
from the trial's own record, 12 from the retrieved drug table) and the assertion
checks the final labels rather than the correction count. Keep it in the chain:
a hand-verified correction list is not reproduced for free by the next
generation of guards, and the only way to know which ones survive is to re-run
it as a check.

### 13.5 Result

`delivery_mode_10_14_2026.csv`, 7,734 rows, set-equal to the `# NCT…` headings in
`bundles_chunks/`, sorted by NCT id, 7,735 physical lines (no embedded newlines):

injection/infusion 6,324 · Oral 797 · Other 391 · Topical 215 · Unknown 7
confidence High 4,903 · Medium 2,027 · Low 797 · Unknown 7

Evidence tiers: intervention description 3,725 · drug-level route 1,630 ·
arm description 721 · intervention name 612 · detail sentence naming the peptide
373 · summary sentence naming the peptide 177 · context class 168 ·
brief title 122 · official title 102 · other names 62 ·
generic study description 14 · trial-level route 8 · abstract 7 ·
biomarker / no peptide / no wording 7.

312 rows carry `multi-route resolved by indication` (245 `Oral`, 57
`injection/infusion`, 10 `Topical`), 27 `[corrected on review: …]`, 44
`[trial also includes <label>: …]`, 4 `[route switches mid-course]`. 120 rows
could not resolve the peptide from the record and are capped at `Low`.

The seven `Unknown` rows are unchanged from §12.4 and still right to be blank.
The `Other` bucket still audits by trigger (intranasal 306, inhaled 44,
implant 17, vaginal 7, graft/scaffold 6, sublingual/buccal 4, rectal 1,
in-vitro 1); the residue is hyphenated `intra-nasal` spellings, all checked.

### 13.6 Regression set

All of §10.4's, §11.4's and §12.5's cases pass. Add these, which this run's
changes turn on — they are now carried as a 65-case suite:

NCT02857582 (microbiota given rectally, vancomycin given orally → **Oral**),
NCT04918758 (PuraStat, comparator's sucralfate enema must not win → **Topical**),
NCT05018286 (apraglutide, route only in the arm label → injection),
NCT02478710 (Aerosolized vancomycin → **Other**),
NCT01085760 (vancomycin 125 mg orally in PSC → **Oral**),
NCT02397213 (ciclosporin IV injection; CicloMulsion is its own trade name → injection),
NCT02186457 ("Antibiotic" is its own otherName, not a rival → **Topical**),
NCT02937896 (nasal desmopressin + IV saline → **Other**),
NCT02786992 (sublingual misoprostol + oxytocin IVI → injection),
NCT01190163 (dinoprostone vaginal pessary vs oxytocin → injection),
NCT00477763 / NCT00502073 / NCT04597762 (cyclosporine eye drops → **Topical**),
NCT00167583 / NCT01693393 (systemic cyclosporine, ocular indication → **Oral**),
NCT02285140 / NCT04401553 / NCT06527131 (vancomycin surgical prophylaxis → injection),
NCT07004049 (colistin in severe gram-negative infection → injection),
NCT01266499 (PO colistin → **Oral**),
NCT02400112 / NCT02631408 / NCT05959603 / NCT01372371 (intrawound vancomycin powder → **Topical**),
NCT00862875 / NCT02483299 / NCT01813227 (run 4's corrections, re-applied → injection).

The suite is now a script — `python3 -I delivery_mode_pipeline/regression.py
delivery_mode_<date>.csv` — and exits non-zero on any failure. Run it after
every lexicon or guard change, before looking at the totals.

---

## 14. Run 7 — `delivery_mode_10_14_2026.csv` (grown dataset, 2026-10-26)

**The dataset changed under the pipeline.** `bundles_chunks/` now holds
**12,372** `# NCT…` headings, not 7,734: 5,180 trials were added and 542 of the
old ones dropped. `delivery_mode_pipeline/` and `work/` both survived
(`trials_drugs.tsv`, `ctg_raw.jsonl` — already fetched for all 12,372 —
`abstracts_by_nct.tsv`, `chembl_terms.tsv`, `drug_routes.tsv` 126 lines,
`trial_routes.tsv` 8 rows), but no deliverable had been written and no
`dm_pass*.csv` from a prior run was left.

On the 7,192 surviving old trials the pipeline reproduced run 6 exactly, which
is what made the rest of the run tractable: **every change below was checked by
re-diffing the old cohort, and the old cohort ends the run with four changed
labels, all of them verified improvements.** Do that diff on any future port —
it separates "the new data needs work" from "I just broke something".

### 14.0 Two port bugs to fix before anything else

| Found | Fix |
|---|---|
| `apply_review_fixes.py` asserts that every hand-verified correction id carries its expected label. 5 of the 65 ids are no longer in the trial set, so it died on `StopIteration` **after** writing its output — easy to miss | check only ids present, and print the absent ones. `regression.py` had the same problem and reported them as failures ("got None"); it now skips and names them |
| `apply_review_fixes.py` hardcoded `DATA='/projects/btl/ezhang/ctg_lookup/ctg_api_out'` — **a different dataset's directory**, which exists. It was re-evidencing corrections from another run's `drug_routes.tsv` and `ctg_raw.jsonl` | `DM_DATA`/`DM_WORK` env with `PIPE` from `__file__`, like every other script. Two corrections silently fell back to `unsourced`/`Low` before this was fixed |

### 14.1 What the 5,180 new trials are, and why identification was the whole job

`trials_drugs.tsv` (the §9.1 shortcut) has **no peptide drug for any of them** —
the peptide-sequence run that produced `bundles_chunks/ctg-studies-peptide-seqs.csv`
never covered them, and that CSV is gone. So §5.1's lexicon, which §9.1 had
demoted to a fallback, became the only identification path, and the first pass
showed what that costs: 2,888 rows capped at `Low` with
`peptide drug not resolvable`, 538 `Unknown`, and 967 `Oral` in a cohort whose
drugs are almost all injected.

Printing the intervention names of the unresolved trials (§8.4) explains it. The
new half of the corpus is **recombinant protein biologics**, not classic
peptides: filgrastim (775 trials), etanercept, aldesleukin/IL-2, sargramostim,
abatacept, anakinra, darbepoetin alfa, somatropin, the interleukins and
interferons, gonadotropins, coagulation factors, enzymes and antibodies — plus a
large block of **ACE-inhibitor and ARB trials** (valsartan, enalapril,
lisinopril, sacubitril/valsartan) that are in the corpus because the search
matched *angiotensin*, and that administer no peptide at all.

None of those biologics carries an INN peptide stem, so `PEPTIDE_STEMS` never saw
them and the route of a chemotherapy partner was read instead.

**Three things were tried for identification; only the third is worth keeping.**

1. *The bundles' ChEMBL block.* `bundle_molecules.py` extracts, per trial, the
   molecules the corpus search matched with their `pref_name` and
   `molecule_type`. Intersected with the trial's own intervention names it
   resolves 2,083 new trials, and it is the corpus's own statement of why a trial
   is in scope — **keep it, as a late stage**. Two cautions: restrict to
   `molecule_type` in {Protein, Antibody, Enzyme, Antibody drug conjugate}
   (`Unknown` covers excipients and foods — METFORMIN GLYCINATE, MALTODEXTRIN,
   DIANEAL, all of which became "the peptide"), and drop `pref_name`s over 60
   characters (they are cell-product descriptions).
2. *`molecule_type` as a **veto*** — "no protein-typed match ⇒ no peptide drug".
   **Rejected.** The ChEMBL matches are too fuzzy: a pegfilgrastim trial, a
   sargramostim trial, a darbepoetin trial and a `copolymer 1` (glatiramer)
   trial all come back `Small molecule` only. It would have blanked ~1,750 rows,
   many of them wrongly.
3. *A biologic lexicon* (`lex.BIOLOGIC_STEMS`, `BIOLOGIC_WORDS`,
   `BIOLOGIC_NAMES`, `BIOLOGIC_NEG`). This is the one that worked: morphology
   resolves 3,306 new trials, and it discriminates cleanly — filgrastim,
   aldesleukin, IL-3, rHuEPO, r-metHuG-CSF, copolymer 1, casein hydrolysate and
   ovotransferrin are peptide drugs; metformin, sitagliptin, enalapril,
   verapamil, levothyroxine, resiquimod, xylitol, melatonin, vitamin D3,
   ertugliflozin, beta-alanine and "breakfast tray" are not. Stems used:
   `-grastim -gramostim -plostim -poetin -tropin -leukin -feron -mab -fusp
   -ermin -glucerase -sidase -sulfase -uronidase -plase -kinase -asparaginase
   -dornase -uricase -cerase -lipase`, plus `recombinant human|methionyl`,
   `rhEPO/rhGH/rhCSF`-style shorthand, the cytokine/CSF/EPO/GH/gonadotropin/
   coagulation-factor words, and ~190 names.

Negative list matters as much as the stems: `kinase[\s-]?\d*\s*inhibitor`,
`receptor-associated kinase`, `dipeptidyl peptidase`, `DPP-4` and
`receptor antagonist` keep tyrosine-kinase inhibitors, DPP-4 inhibitors and
small-molecule receptor blockers out.

### 14.2 The error classes this run found (each by §6 stratified review)

| Found | Fix |
|---|---|
| **`ivnames` resolution on a trial the identification run never covered.** `build_index.py` falls back to writing *every* intervention into the `interventions:` column, so §12.1's "last resort" made **enalapril**, **sitagliptin**, **verapamil** and a **breakfast tray** "the peptide" — 1,007 new trials | the stage runs only when the index actually named a drug (`if not hits and dnorm`) |
| **An antibody's IV route read for the trial's oral peptide.** Counting antibodies and Fc-fusion proteins equally flipped 8 old-cohort cyclosporine trials to `injection/infusion` (rituximab, belatacept, rasburicase, secukinumab, ATG…) | `lex.peptide_rank`: 1 = peptide, 2 = recombinant protein/hormone/enzyme, 3 = antibody or Fc-fusion. Resolution keeps only the **best non-zero rank** present in the trial. 11.2's error class, prevented structurally rather than by distance |
| **`ciclosporin` (British spelling) was not in `PEPTIDE_CLASS_WORDS`**, so it ranked 0 and rabbit ATG became the peptide of a trial whose ciclosporin is explicitly `3-5 mg/kg/d orally` | `c[iy]closporin` |
| **A generic `-cept` stem matches the trade name CellCept** (mycophenolate mofetil), which then outranked the real peptide in two transplant regimens | the Fc-fusion proteins are listed by name (`_CEPT`), not by stem |
| **CTG `otherNames` are not aliases.** A prednisone arm lists `["oral antidiabetic agents", "insulin"]`; metformin XR lists `"Biguanide-insulin sensitizer"`; **talazoparib** lists `"Combination product: 177Lu-DOTA-Octreotate"`; **vadadustat** lists `"Darbepoetin alfa"`. All four became the trial's peptide | rank on the intervention's **own name** first; consult `otherNames` only when no name ranks **and** the name is *opaque* (`lex.opaque_name`: a research code with a letter+digit token, a short or internally-capitalised abbreviation, or a placeholder word). That keeps the cases the stage exists for — `hCRF`→corticorelin, `SMS995`→octreotide, `CTLA-4 Ig`→abatacept, `hLF1-11`, `PTHrP (1-36)`, `p946` — and drops the rest. The same gate is applied to the §13.3 description stage |
| **Tier 7 and tier 11 keys were built from every intervention of the trial**, so tier 11 answered a filgrastim trial with the ChEMBL flags of **"total body irradiation"** (`oral=1`) and an LHRH-analogue trial with **darolutamide**'s | keys come from `drugs` plus the **peptide's** own names/otherNames. §12.1's lesson, applied to the drug tables instead of the route words |
| **The record-level food/supplement context class fired on injected proteins** — a pegfilgrastim trial read as `Oral` from background nutrition wording | `lex.INJECTED_PROTEIN` vetoes the whole-record `FOOD` branch. Dietary peptide products (hydrolysates, collagen peptides, whey) are deliberately absent from it |
| **Nutrition is an intervention, not a route**: an arm named "ustekinumab and semi enteral nutrition" read as `Oral`; `total parenteral nutrition` reads as an infusion of the study drug | mask `(semi-)(total/partial) enteral|parenteral nutrition`, `nutritional support`, `TPN`, `nutrition therapy` |
| **`oral` as an anatomical site** in abstracts and indications ("Oral and Cutaneous Squamous Cell Carcinomas", "Radioactive Oral **Mucitis**" — note the record's misspelling) | extend the oral mask with squamous/carcinoma/epithelium/microbiome/biofilm/plaque/ulcer/leukoplakia/graft/appliance/immunotherapy, `mucitis`, and `(oral|dental|periodontal) (health|hygiene|disease)` |
| **A mouthwash is not an oral dose.** Etanercept mouthwash and "Candida Mouthwash with Curolox Peptide" read as `Oral` | `mouthwash`, `mouth/oral rinse`, `gargle`, `swish` join the `TOP` family and are masked out of `ORAL`: swish-and-spit is topical to the oral mucosa (§1) |
| **Three-letter drug names never matched.** `named()` requires ≥4 characters, so `GIP` was invisible and a **placebo arm's** description was read for a GIP infusion trial | word-boundary match for 3-character names, plus ~35 endogenous-peptide abbreviations in `PEPTIDE_CLASS_WORDS` (`GIP, GLP-1/2, PYY, GHRH, CCK, VIP, ACTH, PTH, PTHrP, CGRP, NPY, ANP, CNP, AVP, DDAVP, TRH, CRH, xenin, kisspeptin, apelin, urocortin, motilin, neurotensin, enkephalin, …`) |
| **`drug_routes` keys matched as bare substrings**, so the key `interleukin 1` answered for interleukin-**11** and `il 2` would answer for IL-**21** | leading word boundary and **no digit may follow** (`\b<key>(?![0-9])`) — a trailing plural ("…nanofiber **hydrogels**") must still match, and did not under a plain `\b…\b` |
| **`contradiction_pass.py` corrected a row it should have left alone**: "Ingested Interferon Alpha" → `injection/infusion`. `names_itself` only sees wording `ORALW` matches, and `ingest` was not in it | `ORALW` gains `ingest/swallow/sachet/gummy/pill/drink/enteral/syrup/lozenge`. **Any oral wording missing from `ORALW` is a false correction waiting to happen** — keep it in step with the `ORAL` family |
| Two rows where a CSF's route came from the chemotherapy regimen described in the same arm (sargramostim with an FLAC/dexrazoxane arm, pegfilgrastim with an R-CHOP arm), found by re-running §11.3's generalized detector over **every** non-injection High/Medium row (it returns exactly these 2) | added to `apply_review_fixes.py` as the `chemo` class, re-evidenced from the retrieved drug table |

### 14.3 Web work this run

The record leaves ~45 biologic families without any route wording. Three agent
families using §5.4's prompt skeleton: (1) colony-stimulating factors,
erythropoiesis agents, interleukins, interferons, growth-hormone axis,
gonadotropins; (2) Fc-fusion proteins, antibodies, immune globulins, enzymes,
coagulation factors; (3) peptide vaccines by code name and miscellaneous
products. **134 of 136 lines came back with a retrieved source** — the openFDA
`/drug/label.json` API and the DailyMed v2 API were the workhorses (drugs.com
returns 403 to a fetch); two are `i` (cilmostim, interleukin-23, both flagged by
the agent rather than guessed). `drug_routes.tsv` goes 126 → 299 lines,
including the trade names, misspellings and abbreviations the records actually
use (`aranesp`, `enbrel`, `neulasta`, `erythropoetin`, `darbepoietin`, `rfsh`,
`il 3`, `interferon alpha` with a *ph*, `antithymocyte immunoglobulin`).

Non-injection answers are the ones that matter and were checked individually:
**dornase alfa** `Other` (SPL route "RESPIRATORY (INHALATION)"), **stem
bromelain/NexoBrid** `Topical`, **becaplermin/Regranex** `Topical`,
**cenegermin** `Topical` (eye drops), **lucinactant** `Other` (intratracheal
instillation), **thymosin β4/RGN-259** `Topical` (eye drops), protein
hydrolysates and A1/A2 β-casein milk `Oral`. Note **collagenase clostridium
histolyticum** is `injection/infusion` (Xiaflex, intralesional) — the topical
collagenase is the unrelated Santyl ointment.

One trial-level row was added (`trial_routes.tsv`, 9 rows): NCT00668850, whose
study drug's `otherNames` say `"buccal Insulin spray"` (Generex Oral-lyn) —
`Other`, with injected insulin as the comparator.

Two classes were added as keys rather than per-drug rows, each on a retrieved
source: the CSF class keys (`g csf`, `gm csf`, `colony stimulating factor`) and
the **glucose/insulin clamp** (`clamp`, `euglyc(a)emic clamp`,
`hyperinsulinaemic clamp`) — a clamp study infuses insulin intravenously at a
fixed rate (DeFronzo, *Am J Physiol* 1979;237:E214), which closed out the clamp
trials that state no route anywhere. A bare `insulin` key was tried and
**removed**: on an unresolved trial the keys come from every intervention, so it
fired far too widely.

### 14.4 Result

`delivery_mode_10_14_2026.csv`, 12,372 rows, set-equal to the `# NCT…` headings
in `bundles_chunks/`, sorted by NCT id, 12,373 physical lines, no embedded
newlines, no empty fields:

injection/infusion 9,575 · Oral 1,670 · Other 463 · Topical 294 · Unknown 370
confidence High 6,598 · Medium 3,116 · Low 2,288 · Unknown 370

Evidence tiers: intervention description 5,505 · drug-level route 2,198 ·
arm description 1,119 · intervention name 904 · detail sentence naming the
peptide 794 · context class 429 · biomarker / no peptide / no wording 370 ·
summary sentence naming the peptide 317 · brief title 176 · official title 176 ·
generic study description 172 · abstract 102 · other names 75 ·
ChEMBL flags 26 · trial-level route 7.

1,840 rows could not resolve the peptide from the record and are capped at
`Low`; 309 carry `multi-route resolved by indication`, 58
`[trial also includes <label>: …]`, 30 `[corrected on review: …]`, 5
`[route switches mid-course]`.

`Other` still audits by trigger: intranasal 326, inhaled 61, implant 29,
sublingual/buccal 9, graft/scaffold 9, vaginal 8, in-vitro 5, rectal 3,
intratracheal 1, 12 unclassified (all Low-confidence generic-description rows).

**The 370 `Unknown` rows are the shape to expect on this corpus, not a defect:**
314 identify no peptide drug among the trial's interventions — the ACE-inhibitor,
ARB, calcium-channel-blocker, DPP-4-inhibitor, procedure and blood-sampling
trials that the *angiotensin* and *glucagon* searches pulled in (the evidence
string now lists the interventions, so each is checkable at a glance); 22 give
only a small-molecule receptor blocker against an endogenous peptide; 10 measure
a natriuretic or vasoactive peptide as a biomarker; 19 name a peptide the record
and the retrieved sources leave without a route (emfilermin, baminercept alfa,
panitumumab, tagraxofusp in one arm, `csa with steroid minimization`). The first
group is the one to re-check if the corpus grows again: it is large because the
new half of the corpus was selected on molecular matches, not on peptide dosing.

### 14.5 Regression set

The suite is now **96 in-scope cases** (3 of the earlier ids are no longer in the
trial set and are skipped by name). Run 7 adds the protein-biologic half:

NCT00407888 (filgrastim "Given SC" → injection), NCT00276029 / NCT00118638
(etanercept, darbepoetin — drug table only), NCT00001269 (IL-3 abbreviation key),
NCT03720340 (rhIL-11 must cite *interleukin 11*, not *interleukin 1*),
NCT00040521 (orally administered rhIL-11 → **Oral**),
NCT00005665 ("Ingested Interferon Alpha" → **Oral**, must not be corrected),
NCT00002719 (rHuG-CSF trial whose "oral schedule" is the chemo arm → injection),
NCT00514215 / NCT00901511 (inhaled sargramostim → **Other**),
NCT00673179 / NCT03943901 (CSF beside a chemo regimen → injection),
NCT05170828 (filgrastim; TBI's ChEMBL flags must not answer),
NCT06709495 (pegfilgrastim; food class must not fire),
NCT00506948 / NCT01790594 (thymoglobulin / belatacept, not oral MMF — CellCept is
not a `-cept`), NCT05996393 / NCT03180723 (oral ciclosporin; ATG's and
rituximab's IV must not win → **Oral**), NCT05716009 (tagraxofusp → injection),
NCT01951729 (GIP infusion, 3-letter drug name), NCT03516773 (EB612 oral PTH
tablet → **Oral**), NCT00668850 (Generex Oral-lyn buccal spray → **Other**),
NCT00031551 / NCT02308436 (etanercept and Curolox peptide mouthwash →
**Topical**), NCT02999776 (topical etanercept → **Topical**), NCT00034788
(Regranex → **Topical**), NCT05967325 (nanofiber hydrogel**s**, plural key match
→ **Other**), NCT06912815 (ustekinumab + enteral nutrition → injection),
NCT04739371 (intranasal insulin spray → **Other**), NCT00000547 / NCT00170937 /
NCT01228279 (enalapril, valsartan+HCTZ, peritoneal dialysate → **Unknown**).

```bash
DM_DATA=. DM_WORK=work python3 -I delivery_mode_pipeline/bundle_molecules.py
DM_DATA=. DM_WORK=work DM_OUT=work/final_a.csv python3 -I delivery_mode_pipeline/annotate_delivery_mode.py
python3 -I delivery_mode_pipeline/contradiction_pass.py work/final_a.csv work/final_b.csv
DM_DATA=. DM_WORK=work python3 -I delivery_mode_pipeline/apply_review_fixes.py work/final_b.csv delivery_mode_10_14_2026.csv
python3 -I delivery_mode_pipeline/regression.py delivery_mode_10_14_2026.csv
```

`work/nq.tsv` was rebuilt from `records_long.csv` this run (§3, ~6 min on 21 GB;
the naive `awk` works, but the file has embedded newlines in quoted fields, so
filter on `$1 ~ /^NCT[0-9]+$/` rather than on `NR>1`). It turned out **not** to
help: its `query` column is just the intervention names, so it carries no
peptide↔intervention link for trials the identification run never covered. Skip
it on the next port and go straight to §14.1's lexicon work.

---

## 15. Run 8 — `delivery_mode_10_14_2026.csv` (QA pass on run 7, 2026-10-26)

`delivery_mode_pipeline/` and all of `work/` survived from run 7 earlier the same
day, on the same 12,372 trials (`bundles_chunks/` unchanged, set-identical to
`work/ncts.txt`), but **no deliverable CSV had been written**. The pipeline
reproduces run 7 byte-for-byte — `annotate_delivery_mode.py` rewrote
`work/final_a.csv` exactly, the contradiction pass reproduced `final_b.csv`
exactly, and the chain reproduced §14.4's distribution (9,575 · 1,670 · 463 ·
294 · 370). So steps 0–1 were not re-run: no CTG fetch, no `records_long.csv`
pass. The run was §6 stratified review plus §8.6 iteration, and it needed four
rounds rather than two.

### 15.1 The error class that dominated this run: a fallback sized for the wrong corpus

§5.1 ends with "if that also fails, the row is annotated from the trial's
interventions as a whole and capped at `Low`". That was written when the
residue was 89–133 trials, where a peptide clearly *is* given but cannot be
named. On this corpus the residue was **1,840 trials**, and §14.4 had already
identified what most of them are: the *angiotensin* / *glucagon* / *insulin*
molecular searches pulled in ARB, ACE-inhibitor, gliptin, diet, exercise and
procedure trials that administer **no peptide at all**. 328 of them reached
tier 12 and were `Unknown`; the other **1,512 carried a label read off a
non-peptide** — melatonin → `Other`, rosuvastatin → `Oral`, whole-grain bread →
`Oral`, pea protein → `Oral`, `"36h fasting"` and `"CEST MRI sequence at 3T"` →
`injection/infusion`, `"test meal (500 kcal)"` → `Topical`.

Nothing in the totals showed it, and the distinction between the two groups was
**not about the peptide at all** — only about whether a route word happened to
be somewhere in the record.

So the fallback now requires positive evidence that a peptide product is given.
Any one of these is enough, and each is evidence the methodology already
trusts elsewhere:

| Signal | Why it counts |
|---|---|
| some intervention **ranks** under `lex.peptide_rank` on its **own name** | §5.1's chemistry call |
| an intervention's **description defines itself** as a peptide (§15.2) | the record's own statement about that product |
| `description`/`otherNames` rank for an **opaque** name (`lex.opaque_name`) | §14.2's gate, unchanged |
| the record names a **peptide product in an administration context** (§15.2) | §5.5's record-level classes, which the gate was firing ahead of |
| the record frames the trial as **peptide vaccination** | §12.3 |
| §5.1's **radiopeptide pattern** (isotope **and** chelator) | §5.1 |
| an intervention name matches a **retrieved route-table key** | §5.4 — the tables are the record of products verified to be peptide drugs |

Otherwise the row is `Unknown` with the interventions listed, exactly as
§14.4's 314 rows already were, so each is checkable at a glance. 1,145 labels
moved; `Unknown` goes 370 → 1,498 and the capped-at-`Low` residue 1,840 → 312,
which is the size §5.1 was written for. **§8.7 is the governing principle: a
wrong label costs more than a blank one.**

Two things were tried and **rejected**, both worth recording:

- *Blanking whenever the peptide is unresolved, full stop.* It is simpler and
  it is what the first implementation did. It blanked peptide-pulsed
  dendritic-cell vaccines, "Vaccines made from peptides", virosome-formulated
  peptides, an altered peptide ligand, milk- and collagen-derived peptides and
  ~30 code-named products — because it returned **before** §5.5's record-level
  context classes could run. The exemption table above is what that cost.
- *A letter+digit "research code" test* as the discriminator ("an unidentifiable
  code might be a peptide; a named non-peptide is not"). It cannot separate a
  code from a dose: `[A-Za-z]{2,}[-\s]?\d{2,}` matches `RLS-0071` and `SP16` but
  equally `ramipril 10 mg`, `Aliskiren 300 mg` and `Forxiga 10mg`. 182 rows, most
  of them not peptides. Peptide status has to come from §5.4, not from spelling.

### 15.2 The guards the gate's own first version exposed

Tightening identification moved trials from the whole-trial fallback into
tiers 1–6, where route words have owners — so each fix below was *found* by the
gate and would have been invisible without it.

| Found | Fix |
|---|---|
| **Insulin analogues and brands are routinely the only name an intervention carries** — `Lispro`, `Degludec`, `Glargine`, `Aspart`, `Detemir`, `Insulatard`, `NovoMix 30`, `Wosulin`, `Protaphane` — and none contains the word *insulin*. They ranked 0, so the commonest peptide drug in the corpus went unidentified in 60+ trials | ~30 analogue and brand names in `PEPTIDE_CLASS_WORDS`. `aspart` needs `(?!ate|ame|ic|yl|ase|hous)` or it eats aspartate, aspartame and asparaginase |
| **The record names the intervention by the distinctive half of the canonical drug name.** `named()` tested only "is the whole drug name inside the intervention name", so drug `insulin lispro` never matched intervention `Lispro` | a long (≥6), alphabetic, distinctive token of the drug name matches as a whole word. `DRUG_CLASS_TOK` (insulin, human, recombinant, hormone, factor, alpha…) and `lex.ROUTE_WORDS` are excluded — otherwise `insulin` makes any insulin "the" insulin, and `exubera (inhaled human insulin)`'s token *inhaled* matches on a route word |
| **A meal is ingested, not the drug.** As soon as the insulin trials' own descriptions were read, `"0.10 U/kg immediately before ingestion of a standard meal"` and `"GLP-1 ... secreted by gut in response to nutrients ingestion"` put three subcutaneous-insulin trials and a GLP-1 infusion trial on `Oral` | mask `ingest… (a) standard/mixed/test meal | breakfast | food | nutrients | carbohydrate | glucose | drink`, and the mirrored `meal/food/nutrient[-\s]ingestion`. Same shape as §14.2's enteral-nutrition mask |
| **`ORAL` was missing the bare and third-person forms of `ingest`** that `ORALW` already had, so `"subjects ingest 15 grams of collagen peptides daily"` carried no oral wording at all | `\bingest(?:ed|ion|s|ing)?\b`. §14.2's warning runs **both ways** — the two families have to stay in step |
| **INN stems with Latin/French endings.** `Terlipressinum` and `Triptoreline` are the sponsor's registered spellings; a trailing `\b` after the bare stem missed every one | one optional inflection after the stem (`e|a|o|i|um|us|es|en|ul`) |
| **`\bpeptide\b` matched neither `Polypeptides` nor `Multiplexed heptapeptides`** | `(poly|oligo|di|tri|…|hepta)[\s-]?peptide(s)`. `PEPTIDE_NEG` still vetoes `dipeptidyl peptidase`/DPP-4 |
| **`CHELATOR`'s `tate\b` and `toc\b` were bare substrings** — `tate` matched ace**tate**, so a formoterol inhalation trial with an ¹⁸F sub-study read as a radiopeptide trial | `(?:dota|octreo)tate\b`, `(?:dota|edo)toc\b`. §5.2's lesson, in a pattern that predates the mask list |
| **`DTPA` was not in `CHELATOR`** at all, so a di-DTPA-¹³¹I peptide trial had no radiopeptide evidence — and the **radioiodines were missing from `ISOTOPE`** | `\bdtpa\b`; `12[345]i`, `131i`, `iodine-12[345]`, `iodine-131` |
| **A description that merely mentions a peptide is not evidence that one is given.** The gate's first version read name+description for every intervention, so a sitagliptin arm whose description mentions insulin kept its `Oral` label | §14.2's gate applied here too: description/otherNames only for an **opaque** name… |
| …but that is **too strict** for deciding *whether* a peptide is given, because records define plainly-named products in their own descriptions: `"Dalargin is a synthetic analog of the endogenous opioid peptide leucine-enkephalin"`, `"a novel cross-linked HA hydrogel incorporating proline-rich peptides"`. Both were blanked | `description_calls_itself_a_peptide`: the peptide word must sit in a **defining clause about this intervention** — its own name (or `it`/`the study drug`) followed within ~70 characters by `is`/`consists of`/`contains`/`incorporating`/`derived from` + peptide. Sitagliptin's description never says sitagliptin is a peptide. This is the general rule that replaced three rounds of keyword patterns |
| **A virosome-formulated peptide vaccine took `Oral` from a bundled abstract** about an *"orally transmitted virus"*. §9.3 runs the vaccine class ahead of the generic tiers, but §10.2 scopes it to the peptide's own text — which an unresolved trial does not have | the record-level scope is used for that early call too when the record names a peptide product; §12.3's last branch also accepts `vaccin…` + any record-level peptide-product wording, not only its own phrasings. Plus a mask for `orally transmitted` / `oral transmission` |
| The record-level peptide test needed a **measurement veto** or it would fire on most of the corpus: 582 of the blanked rows mention *peptide* somewhere, nearly all of it C-peptide, NT-proBNP and the natriuretic peptides, CSF amyloid-β, or "gut peptides" as an outcome | `PEPTIDE_MEASURED`, checked in a ±60-character window around each match rather than over the whole record |

### 15.3 Web work this run

The gate needs **peptide status**, which §8.4 allows as a chemistry call but
which the user's brief requires to be evidenced — so it went through §5.4 with
the same rule: nothing from recall. 23 products, picked as the recurring
code-named interventions among the rows the gate would otherwise blank
(ranked by trial count) plus every such row in the surviving old cohort.
All 23 came back with a retrieved source:

**TPX-100** 23-aa chondrogenic peptide, intra-articular (Arthritis Res Ther
2021;23:234) · **MSI-78 / pexiganan** 0.8% cream, `Topical` (Dipexium OneStep-1/2;
Clin Infect Dis 2008) · **pemziviptadil / PB1046** and **PB1023 / Glymera**
VIP- and GLP-1–elastin-like-polypeptide fusions, weekly SC (NCT01658501,
NCT01478399, PhaseBio) · **HSPPC-96 / Oncophage / vitespen** gp96 heat-shock-
protein–peptide complex, intradermal (NCT03018288 protocol; J Transl Med
2010;8:9) · **UB-311** UBITh Aβ1-14 peptide vaccine, IM (eBioMedicine 2023) ·
**cenderitide / CD-NP** chimeric natriuretic peptide, continuous SC infusion
(NCT01316432, NCT03091998) · **GSK2586881** recombinant human ACE2, consecutive
IV doses (Crit Care 2017;21:234; Eur Respir J 2018;51:1702638) · **SP16**
α1-antitrypsin-derived LRP1 agonist peptide, SC (PLoS ONE 2021, PMC8101931) ·
**GM604 / GM6** 6-aa MNTF analogue FSRYAR, IV (US 8673852; NCT01854294) ·
**VIAject** rapid-acting insulin, SC (Diabetologia 2008) · **SHR20004 /
noiiglutide** GLP-1 peptide, SC (NCT06137469 title) · **TENDU** tetanus-epitope-
targeting PAP/PSMA/NY-ESO-1 peptide vaccine (NCI drug dictionary; Mol Ther Oncol
2025) · **LEAP-2** 40-aa peptide, continuous IV (Cell Rep Med 2022;3:100582) ·
**PACAP38** 38-residue polypeptide, 20-min IV at 10 pmol/kg/min (J Headache Pain
2017;18:110) · **PepGNP** peptide–gold-nanoparticle vaccine, intradermal
microneedle (NCT07394426; PepGNP-Dengue phase 1) · **DPX-Survivac** five
HLA-restricted survivin peptides in a lipid depot (PMC4570133) · **dalargin**
Tyr-D-Ala-Gly-Phe-Leu-Arg, IV/IM lyophilisate (Dalargin-Pharmsynthesis label).

**PEN-221** (SSTR2 peptide–DM1 conjugate), **RLS-0071 / pegtarazimod** (15-aa
EPICC peptide), **CM3.1-AC100 / AC-100 / Dentonin** (23-aa MEPE peptide),
**MOD-6031** (PEGylated oxyntomodulin) and **FAM-NP41 / NP41** (nerve-binding
peptide) came back as peptides on a retrieved source but **without a published
human route**; they are listed in `lex.VERIFIED_PEPTIDE_PRODUCTS` for peptide
status only and their trials' own records supply the route. `drug_routes.tsv`
goes 324 → 352 lines (315 `v`, 30 `i`); the two `Multiple:` pairs plus
cyclosporine and colistin are intact, so §13.1's regression has not returned.

**`Pep19` was searched for and not found**, and its trial (NCT06359327) is
therefore `Unknown` — the one old-cohort row this run blanks. That is the right
outcome, and it is the honest shape of the residue.

### 15.4 Result

`delivery_mode_10_14_2026.csv`, 12,372 rows, set-equal to the `# NCT…` headings
in `bundles_chunks/`, sorted by NCT id, 12,373 physical lines, no embedded
newlines, no empty fields:

injection/infusion 9,219 · Unknown 1,498 · Oral 993 · Other 425 · Topical 237
confidence High 6,671 · Medium 3,126 · Low 1,077 · Unknown 1,498

Evidence tiers: intervention description 5,187 · drug-level route 2,186 ·
no peptide / biomarker / no wording 1,498 · arm description 984 ·
intervention name 761 · detail sentence naming the peptide 746 ·
context class 267 · summary sentence naming the peptide 257 ·
official title 163 · brief title 159 · other names 70 ·
generic study description 56 · abstract 26 · trial-level route 7 ·
ChEMBL flags 3.

312 rows could not resolve the peptide and are capped at `Low` (1,840 in run 7);
309 carry `multi-route resolved by indication`, 255 `[competing: …]`, 48
`[trial also includes <label>: …]`, 29 `[corrected on review: …]`, 5
`[route switches mid-course]`.

`Other` audits by trigger: intranasal 306, inhaled 58, implant 24,
sublingual/buccal 7, vaginal 7, in-vitro 5, graft/scaffold 3, intratracheal 1,
rectal 1, 13 whose wording the audit regex does not catch (nearly all intranasal
oxytocin written as *puffs* / *each nostril*, checked by hand).

**The `Unknown` bucket is now the largest change from run 7 and the one to read
first on any future port:** 1,456 identify no peptide drug among the trial's
interventions, 22 give only a small-molecule receptor blocker against an
endogenous peptide, 13 name a peptide the record and the retrieved sources leave
without a route (emfilermin, baminercept alfa, CLS12311, interleukin-23, plus
five interventions that are procedures or assays the identification run read as
drug names), and 7 measure a peptide as a biomarker. The first group is 12% of
the corpus because the newer half was selected on molecular matches, not on
peptide dosing — §14.4 said so, and this run acted on it.

**The old cohort is the control, and it ends the run with six changed labels.**
Five are verified improvements (NCT00356421 Exubera, NCT01445951 Technosphere
insulin, NCT05243628 Afrezza — the inhaled study drug now wins over an injected
comparator; NCT00982254 and NCT02004366 — subcutaneous and basal-bolus insulin
that had been `Oral`). The sixth is the Pep19 blank. Do that diff on any future
port, before looking at the totals.

Carried-forward limitation, narrowed but not gone: ~312 rows still take a label
from the trial's interventions as a whole, and a handful of those are trials
where the record-level peptide test fires on background wording while the route
word belongs to a non-peptide (a mosapride tablet in a mixed-meal trial, a
probiotic drink). They are capped at `Low` and every one says
`peptide drug not resolvable from record`, so they are separable. Tightening
further re-blanks genuine rows — that trade-off is what rounds 2–4 of this run
were spent measuring.

### 15.5 Regression set

All of §10.4's, §11.4's, §12.5's, §13.6's and §14.5's cases pass. The suite is
now **139 in-scope cases** (4 ids are no longer in the trial set and are skipped
by name). Run 8 adds the identification gate, the products verified for it, and
the masks its own first version exposed:

NCT05660941 / NCT03336528 / NCT00699686 (bare `Lispro` / `Degludec` / `Glargine`
/ `Aspart` / `Detemir` must resolve → injection), NCT00562133 / NCT00849576 /
NCT03414333 ("before ingestion of a standard meal", "nutrients ingestion" must
not read `Oral` → injection), NCT00982254 / NCT02004366 (SC and basal-bolus
insulin → injection), NCT05220371 ("ingest 15 grams of collagen peptides" →
**Oral**), NCT00005665 ("Ingested Interferon Alpha" → **Oral**, ORAL/ORALW in
step), NCT00356421 / NCT01445951 / NCT05243628 (inhaled insulin study drug →
**Other**), NCT03352349 (`Terlipressinum`) / NCT04242017 (`Triptoreline`) →
injection, NCT05933720 (`Polypeptides`) → injection, NCT03589443
(`Multiplexed heptapeptides`) → **Topical**, NCT05121831 (DGX-001, route table
names the product → **Oral**), NCT01925261 (TPX-100) / NCT05778188 (RLS-0071) /
NCT01854294 (GM604) / NCT03651089 (SP16) / NCT04701021 (TENDU) / NCT05603598
(LEAP-2) / NCT01236404 (PB1023) / NCT01416038 (DPX-Survivac) → injection,
NCT00107211 / NCT00243529 (peptide-pulsed DC vaccines, record-level class) /
NCT00445419 (virosome-formulated peptides, must **not** take `Oral` from an
"orally transmitted virus" abstract) / NCT00079495 (altered peptide ligand
NBI-5788) / NCT00467506 (di-DTPA-¹³¹I peptide) → injection, NCT07404358
(Dalargin, self-definition in its own description) → injection, NCT07581613
(HA hydrogel incorporating proline-rich peptides) → **Topical**, and the blanks:
NCT00853944 / NCT02148978 (sitagliptin, saxagliptin — a description mentioning
insulin is not self-definition), NCT07435090 (rimegepant ODT), NCT04283318
("12h/36h fasting"), NCT06669273 ("CEST MRI sequence at 3T"), NCT06333717
(whole-grain bread), NCT02370927 (pea protein), NCT05319301 (melatonin),
NCT06105060 (rosuvastatin), NCT02020395 ("test meal (500 kcal)", was `Topical`),
NCT05553184 (formoterol with an ¹⁸F sub-study) → **Unknown**.

```bash
DM_DATA=. DM_WORK=work python3 -I delivery_mode_pipeline/bundle_molecules.py
DM_DATA=. DM_WORK=work DM_OUT=work/r8a.csv python3 -I delivery_mode_pipeline/annotate_delivery_mode.py
python3 -I delivery_mode_pipeline/contradiction_pass.py work/r8a.csv work/r8b.csv
DM_DATA=. DM_WORK=work python3 -I delivery_mode_pipeline/apply_review_fixes.py work/r8b.csv delivery_mode_10_14_2026.csv
python3 -I delivery_mode_pipeline/regression.py delivery_mode_10_14_2026.csv
```

## 16. Run 9 — `delivery_mode_10_14_2026.csv` (QA pass on run 8, 2026-10-26)

`delivery_mode_pipeline/` and all of `work/` survived from run 8 on the same
12,372 trials (`bundles_chunks/` unchanged, set-equal to `work/ncts.txt`), but
**no deliverable CSV had been written**. §2 was re-checked against the bundles
first and still holds: they carry molecular evidence (ChEMBL, UniProt, PDB,
IntAct, IUPHAR, EBI proteins) plus abstracts and **no intervention text**, so
the route still comes from the trial's own CTG record. The pipeline reproduced
run 8 byte-for-byte — `annotate_delivery_mode.py` rewrote `work/r9a.csv`
identical to `r8a.csv`, the contradiction pass reproduced `r8b.csv`, the chain
reproduced §15.4's distribution (9,219 · 1,498 · 993 · 425 · 237), and
139/139 regression cases passed. So steps 0–1 were not re-run: no CTG fetch and
no `records_long.csv` pass. The run was §6 stratified review plus §8.6
iteration, over eleven annotate rounds.

### 16.1 The error class that dominated this run: a procedure's route read as the drug's

Five of the defects were one shape, and §5.2's mask list had no entry for any of
them: **the route word belongs to a procedure or a device, not to any drug.**
The masks to date cover route words owned by a *rival drug*; these are owned by
nothing that is administered at all.

| Found | Fix |
|---|---|
| **A cell or marrow infusion is not the peptide's route.** "Administration will commence no later than at least 36 hours before **marrow infusion**" made a cyclosporine GVHD-prophylaxis trial `injection/infusion` at **High**; "Non-Myeloablative Allogeneic Stem Cell Transplantation and **Donor Lymphocyte Infusions**" and an arm that simply lists "stem cell transplantation, …, cyclosporine, methotrexate" did the same. 5 rows, two of them High | mask `(stem cell\|bone marrow\|marrow\|platelet\|donor lymphocyte)[\s-]?(product )?(infusion\|transplant…)`. §1's ex-vivo rule is untouched: a peptide that loads a cell product which is then infused is still `injection/infusion`, by the §5.5 cell-product class, which does not depend on this wording |
| **An imaging tracer is infused alongside the study drug.** "a continuous **infusion of FDG** will be started" outranked the trial's own intranasal insulin spray | mask `(infusion\|injection\|bolus) of (18F\|FDG\|fluorodeoxyglucose\|contrast\|gadolinium\|tracer\|radiolabel…)`. §5.2 already masked `bolus of saline/contrast`; this is the same idea for the agent named after the preposition |
| **"A venous line will be installed"** — §5.2 masks `intravenous line/access`, but the record drops the *intra* | mask `venous (line\|access\|catheter\|sampling)` |
| **A surgical patch is tissue, not a dosage form.** The "P" of the **HOP bundle** is a teres **ligament patch**; with hydrocortisone and octreotide in the same `otherNames`, the trial read `Topical` at **High**. Its peptide, octreotide, is subcutaneous | mask `(teres\|ligament\|omental\|falciform\|tissue\|fascial\|mesh\|graft\|…)[\s-]?patch`. §9.3's `blood patch` was the first member of this family; genuine transdermal patches (abaloparatide, estradiol) still match |
| **A product label's dosage-form enumeration is not a route.** The intervention name "Teicoplanin Sandoz 200 mg powder and solvent for solution for **injection or infusion or oral solution**" is the marketing authorisation naming itself — in a trial of **inhaled** teicoplanin, which the title states | `form_enumeration`: three or more route words from two or more families strung together with "or" in an intervention *name* ⇒ skip tier 1 and let the title speak. → `Other` |

### 16.2 The peptide's own description, when the peptide is not named in it

§9.3 ruled that an intervention description naming another drug and not the
peptide is **downgraded**. The §10.2 proximity guard got there first and
*discarded* the route outright, because with the peptide absent from the field
it has no distance to measure: `10mg/kg/24h i.v.(intravenous) for 2-3 weeks
with/or without rifampin`, on an intervention named **Daptomycin**, lost its
route and the trial fell to a summary sentence about "exchange of the
**implant**" — `Other`/Medium for an IV antibiotic.

CTG attaches the description to that intervention, so it describes it by
construction. The fallback is tight, and the two limits were measured on the
14 rows the first version moved rather than argued:

- the intervention must be the peptide's own — a description hanging off an
  intervention *named* for another drug ("Laquinimod 0.6") is that drug's;
- only a route word standing **ahead of every rival mention** counts. Once a
  rival has been named the dosing block is its own: "Prednisone: 5mg；Oral
  tablets", "Dapagliflozin oral once daily" (a semaglutide intervention —
  §9.3's mis-attached description, verbatim), "Letrozole 2.5mg orally daily +
  abemaciclib … +/- LHRH analogs", "0.2-0.6mg po … in combination with
  nitroglycerin **transdermal**". Distance and clause tests both keep these;
  position does not.

§9.3's downgrade then applies as written, so every such row says
`[description names another drug and not the peptide]`.

### 16.3 Other guards added this run

| Found | Fix |
|---|---|
| **A combination drug name exempts its own non-peptide half from the guard.** With the drug recorded as "Etanercept plus tacrolimus", *tacrolimus* sat in `pep_tok`, so "Comparison of **Topical** Tacrolimus 0.1%" in the title was the peptide's own clause — `Topical`/Medium for a trial whose summary says "etanercept 50 mg **subcutaneously** weekly". `lex.peptide_rank` already separates the halves (etanercept 3, tacrolimus 0) | split a drug name on `plus/and/with/+/&`, keep only the ranked parts in `pep_tok`, and make the rest ordinary rivals. **Do it on the `pep_tok` fallback too** — that is where it mattered: this trial has no drug in `trials_drugs.tsv`, so `pep_tok` came from the intervention names. Also fixed "dex combined with rtx, **csa** and ivig", where IVIG's route was read for oral cyclosporine |
| **Tier 1 was unguarded.** §9.3 applied the rival guard to tiers 2 and 4–6 on the assumption that an intervention *name* is the peptide's own. A combination name breaks it: "Glucophage **tablets** and Victoza" → liraglutide `Oral`/High; "20mg **oral** propranolol and oxytocin" → oxytocin `Oral`/High; "**Intraarticular** betamethasone" → cyclosporine injection | clause attribution only on the name field — distance is the wrong instrument in a four-word name (§12.1). With one correction: `rival_tokens` carries the peptide's **own** name words into the rival set whenever the peptide was identified through `otherNames`, so "**basal** bolus" discarded its own "Bolus". Inside this field a token of this very name counts only if it is independently a drug — in `CO_DRUGS`, a route-table key, or peptide-ranked. `glucophage`, `propranolol`, `betamethasone` qualify; `basal` does not |
| **Records bullet a regimen instead of punctuating it.** "\* Bicalutamide is administered **orally** on a daily basis \* GnRH Agonist as prescribed" was one clause, so §12.2's attribution could not separate them | `*`, `•`, `·` and newlines join `CLAUSE_SEP` |
| **§12.3's placebo dosage-form mask had no `ointment`.** "vs. Placebo **Ointment**" survived as a Topical hit in a clause with no rival | add `ointment/lotion/patch/foam/paste/suppository/sachet/powder/inhaler` to it |
| **`PEP_ALIAS` never reached the route-table keys.** §12.1 added the record's own shorthand to `pep_tok`, but the tables are keyed on canonical names, so an intervention the record calls only "**CsA** with steroid minimization" matched no key and the trial blanked, though its arm says "Ciclosporin A (CsA) plus MMF" | alias → canonical, as a whole word, when the tier-7/11 key set is built. Short aliases (`csa`, `gsh`, `acth`) are matched on word boundaries, not as substrings |
| **An oral powder taken as a drink carried no oral wording.** "300 mg of powder form **dissolved in one cup of tap water** prior to breath test" — a ¹³C dipeptide pancreatic-function substrate — was `Unknown` | `dissolv… in … cup/glass/mug … water/juice/milk` joins `ORAL`. **The container is load-bearing**: the first version omitted it and read vaccine *formulation* as administration ("100 ug PD-L2 peptide dissolved in DMSO and water mixed with 500ul montanide" → `Oral`/High for two injected peptide vaccines) |
| **§9.3's skin-outcome mask stops at the first item.** "support skin hydration, **elasticity, firmness, dermal collagen content**, and wrinkle reduction" outvoted the record's own "consumed **orally**" — `Topical` for an ingested collagen supplement | mask the comma-run of outcome words that follows `skin`, and `dermal collagen content` |
| **A peptide coupled to red cells ex vivo was not in the cell-product class.** CLS12311 is "autologous **peptide-coupled red blood cells**", §1's ex-vivo case, but §5.5's class lists only dendritic/NK/T cells | `peptide-coupled`, and `(coupled\|conjugated\|loaded) … (red blood cells\|RBCs\|erythrocytes)` join `CELLPROD` |

### 16.4 The biomarker test was unreachable, and it is an identification question

§10.2's biomarker check sat **after** tier 8 ("anywhere in the study
description"), so it could never fire for a biomarker trial whose study text
happened to carry a route word. A PCOS ovulation-induction trial whose only
"peptide" is the `OTHER`-typed intervention *"day 3: follicle stimulating
hormone (FSH), luteinizing hormone (LH), thyroid stimulating hormone (TSH),
total testosterone"* — described as "baseline hormonal **assay** … will be
done" — was `Other` off the detail text.

Whether a peptide is given at all is an identification question, which run 8
settled before the route tiers (§15.1), so the check moved to **just before
tier 8**: tiers 1–7 keep their precedence, because a trial that really doses
the peptide says so in the peptide's own text or has a retrieved route, and a
measured peptide never does. §10.2's caution was about *scope*, and `pep_scope`
is the peptide's own text; the dose and monitoring guards inside `is_biomarker`
are what protect a real Thymosin-α1 dosing trial. 4 rows blanked, each read by
hand: the hormone panel, a **GlutenDetect home urine test**, "Measurement of
amyloid and pTau blood biomarkers", and a continuous glucose monitor.

§12.3's type-scoped branch also needed widening. It admitted only
`DIAGNOSTIC_TEST`/`OTHER` interventions, but a record will type an assay
`BIOLOGICAL`: *"assessment of interleukin 23 in Sera of patients using ELIZA"*
(the record's spelling) is a measurement whatever CTG calls it. The new branch
requires assay wording with **no dose word and no administration verb**, which
is what keeps a dosing description out of it.

### 16.5 Web work this run

Only the Unknown bucket's named-peptide blanks — §15.4 said that group was the
one to read first, and 13 rows named a peptide with no route established. Nine
were resolved from the record or an existing table once §16.3's alias and class
keys were in; four needed retrieval, plus one class key, using §5.4's rule that
nothing comes from recall. openFDA `/drug/label.json` remains the workhorse.

**panitumumab** `injection/infusion` — "6 mg/kg every 14 days as an intravenous
infusion", Vectibix label, SPL route INTRAVENOUS · **emfilermin** (r-hLIF)
`injection/infusion` — 150 µg subcutaneously twice daily for 7 days, population-PK
study, PAGE meeting abstract · **baminercept alfa / BG9924**
`injection/infusion` — "subcutaneous BG9924 or placebo every other week for
12 weeks" from the parent trials of the same 104RA program (NCT00458861,
NCT00664716); NCT00664573 is their long-term extension and its own record says
only "as per Biogen-Idec protocol" · **interleukin-23 monoclonal antibody**
`injection/infusion` as a **class key** — Skyrizi SC/IV, Omvoh SC/IV,
ustekinumab SC, for a record whose drug is named only "Interleukin 23" with the
official title "Interleukin-23 **Monoclonal Antibody** in Inflammatory Bowel
Disease" · **human menopausal gonadotropin / hMG** and **recombinant FSH**
`injection/infusion` — Menopur 225 IU/day subcutaneously, Gonal-f SPL route
SUBCUTANEOUS. §14.3's warning was respected: bare `fsh` and bare `follicle
stimulating hormone` were **not** added as keys, because FSH is far more often
measured than given — the §16.4 trial is exactly that case.

`drug_routes.tsv` goes 352 → 362 lines (325 `v`, 30 `i`); the two `Multiple:`
pairs plus cyclosporine and colistin are intact, so §13.1's regression has not
returned.

### 16.6 Two attempts rejected

Recorded because both look right, in §12.1's spirit:

- *Applying §14.2's otherNames gate to the drug-name stage too* — "an
  intervention that matches on its own name wins; consult `otherNames` only
  when none does". It fixes four rows (a GW677954 capsule arm whose
  `otherNames` say `["Insulin"]` had been the peptide of an insulin trial that
  also lists a plain "Insulin"; an inhaled Afrezza study drug; teriparatide;
  goserelin) and **breaks three**: "Basal Bolus" stops being the peptide
  because a *"Linagliptin + 50% Glargine"* arm ranks on its own name instead —
  a §12.5 regression case — and two cyclosporine transplant trials start
  reading **Simulect®**'s "sterile water for injection". Rejected; NCT00437164
  stays `Oral` and is the known limitation below.
- *Falling back to the unguarded hits whenever the guard emptied the peptide's
  own description*, without §16.2's position test. 14 rows moved, 7 of them to
  `Oral` and 5 of those wrong.

### 16.7 Result

`delivery_mode_10_14_2026.csv`, 12,372 rows, set-equal to the `# NCT…` headings
in `bundles_chunks/`, sorted by NCT id, 12,373 physical lines, no embedded
newlines, no empty fields, every `Evidence` string naming the peptide drug(s):

injection/infusion 9,219 · Unknown 1,495 · Oral 1,001 · Other 423 · Topical 234
confidence High 6,648 · Medium 3,158 · Low 1,071 · Unknown 1,495

Evidence tiers: intervention description 5,237 · drug-level route 2,187 ·
no peptide / biomarker / no wording 1,495 · arm description 974 ·
intervention name 754 · detail sentence naming the peptide 733 ·
context class 263 · summary sentence naming the peptide 250 ·
official title 159 · brief title 158 · other names 69 ·
generic study description 55 · abstract 26 · trial-level route 7 ·
ChEMBL flags 2.

313 rows could not resolve the peptide and are capped at `Low`; 313 carry
`multi-route resolved by indication`, 244 `[competing: …]`, 48
`[trial also includes <label>: …]`, 26 `[corrected on review: …]`, 5
`[route switches mid-course]`.

**28 labels changed from run 8**, every one of them read against the trial's own
record before being accepted: 9 injection→`Oral` (the cell/marrow-infusion
mask, §16.1), 5 `Unknown`→injection (the products retrieved in §16.5), 2+2+2
into injection (the tier-1 and combination-name guards), 2 `Unknown`→`Oral`
(the `CsA` alias key and the dissolved-in-water pattern), 4 into `Unknown`
(§16.4's biomarker move), 1 injection→`Other` (inhaled teicoplanin) and 1
`Topical`→`Oral` (the collagen supplement).

`Other` still audits by trigger, which is the shape to expect (§12.4):
intranasal 322 · inhaled/aerosol 57 · implant 21 · sublingual/buccal 7 ·
vaginal 7 · graft/scaffold 4 · in-vitro 2 · intratracheal 1 · rectal 1 ·
1 whose wording the audit regex does not catch (NCT01093768, intranasal
oxytocin and vasopressin, checked by hand).

§11.3's generalized detector — does the quoted snippet name a non-peptide
co-drug while *not* naming the peptide? — was re-run over all 1,214
non-injection High/Medium rows and falls from 5 hits to **2**, both confirmed
correct: NCT01718652 is cyclosporine's own 400 mg oral capsules in a
canagliflozin interaction study, and NCT01093768 is the intranasal row above.

The `Unknown` bucket is 1,495 rows: 1,455 identify no peptide drug among the
trial's interventions (the ARB, ACE-inhibitor, gliptin, diet, procedure and
blood-sampling trials the *angiotensin*/*glucagon*/*insulin* molecular searches
pulled in, each listing its interventions so it is checkable at a glance), 22
give only a small-molecule blocker against an endogenous peptide, 12 measure a
peptide, and **6 name a peptide the record and the retrieved sources leave
without a route** — down from 13 in run 8, which is what §16.5 bought.

Carried-forward limitations: NCT00437164 takes `Oral` from an "Oral GW677954
Capsules" arm whose `otherNames` falsely claim "Insulin" (§16.6 — the clean fix
costs three correct rows); ~313 rows still take a label from the trial's
interventions as a whole, capped at `Low` and each saying `peptide drug not
resolvable from record`; a trial that switches route mid-course or compares two
routes of one peptide still gets one label, with the other in `Evidence`.

### 16.8 Regression set

All of §10.4's, §11.4's, §12.5's, §13.6's, §14.5's and §15.5's cases pass. The
suite is now **172 in-scope cases** (4 ids are no longer in the trial set and
are skipped by name). Run 9 adds:

NCT01144000 (daptomycin's own "i.v." description, rifampin named after it →
injection), NCT02867800 / NCT00741455 / NCT00001880 / NCT00005941 / NCT00006233
/ NCT00209859 / NCT00806598 (cyclosporine; a marrow or stem-cell infusion,
donor lymphocyte infusion or intraarticular betamethasone must **not** be its
route → **Oral**), NCT02834468 (`dex combined with rtx, csa and ivig` → Oral,
IVIG's route must not win), NCT01002339 (`CsA with steroid minimization`, alias
→ route table → Oral), NCT01259544 (¹³C dipeptide dissolved in one cup of water
→ **Oral**), NCT03381768 / NCT04051307 (peptide dissolved in DMSO and water with
montanide → injection, must **not** read Oral), NCT07516756 (collagen peptides,
skin-outcome run → **Oral**), NCT02571140 (Entera **oral** PTH(1-34) with a
subcutaneous teriparatide comparator → **Oral**), NCT07039747 (marine-peptide
dietary supplement → **Oral**), NCT00134394 (`Etanercept plus tacrolimus`;
topical tacrolimus must not win → injection), NCT05251610 (oxytocin beside oral
propranolol → injection), NCT02130414 (CyCol® capsules study drug, Sandimmun® IV
comparator → **Oral**), NCT04025372 (bullet-separated bicalutamide clause →
injection), NCT07262957 (HOP bundle; a teres **ligament patch** is not a dosage
form → injection), NCT04176328 (product-form enumeration; **inhaled**
teicoplanin → **Other**), NCT00460382 (enfuvirtide → injection), NCT00504608 /
NCT00664573 / NCT00664716 / NCT01288339 / NCT00669786 (emfilermin, baminercept
alfa ×2, panitumumab, hMG/rFSH — retrieved this run → injection), NCT06430671
(CLS12311 peptide-coupled red cells, §1 ex-vivo → injection), and the blanks:
NCT06713187 (interleukin 23 by ELISA), NCT01909141 (day-3 FSH/LH/TSH panel),
NCT05119322 (GlutenDetect home urine test), NCT05427448 (amyloid/pTau
measurement), NCT07061301 (continuous glucose monitor) → **Unknown**.

```bash
DM_DATA=. DM_WORK=work python3 -I delivery_mode_pipeline/bundle_molecules.py
DM_DATA=. DM_WORK=work DM_OUT=work/r9_annotated.csv python3 -I delivery_mode_pipeline/annotate_delivery_mode.py
python3 -I delivery_mode_pipeline/contradiction_pass.py work/r9_annotated.csv work/r9b.csv
DM_DATA=. DM_WORK=work python3 -I delivery_mode_pipeline/apply_review_fixes.py work/r9b.csv delivery_mode_10_14_2026.csv
python3 -I delivery_mode_pipeline/regression.py delivery_mode_10_14_2026.csv
```
