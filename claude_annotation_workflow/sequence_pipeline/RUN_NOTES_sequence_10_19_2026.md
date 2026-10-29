# `sequence_10_19_2026.csv` — run notes (built 2026-10-22)

Scope: the 7,734 `# NCT…` headings in `bundles_chunks/*.md` (`ncts.txt`).
Method: `../sequence_methodology.md`. No prior annotation output and no `train_df.csv`
label was read; the only inputs are the bundle files, the trials' own CTG records, and the
external databases named in step 2b.

## Counts (after the second lexicon pass, 2026-10-22)
| Confidence | rows |
|---|---|
| High | 5,111 |
| Medium | 450 |
| Low | 8 |
| n/a (no sequence) | 2,165 |
| **total** | **7,734** |

5,569 rows carry a sequence (408 distinct sequence strings). Of the 2,165 empties, 1,355
name a drug that is a deliberate empty (not representable, full-length protein, undefined
mixture, class-level naming) and 810 identify no peptide drug at all. 1,541 rows carry
in-file corroboration against a bundle UniProt sequence; 852 report more than one peptide.

The first pass of this run produced High 5,080 / Medium 459 / Low 8 / n/a 2,187
(5,547 with a sequence); it is reproduced exactly by reverting `match2.py` and
`assemble.py` to their `.bak` copies and rebuilding `work/drugs.json` from
`work/drugs.json.gz`.

## What had to be rebuilt
The intermediate state of the earlier run was gone (`work/drugs.json`, `work/ctg.jsonl`,
`work/match2.json`, the GSRS dump). `drug_sequences.tsv` (232 per-drug sequence decisions)
and `curated.py` / `explicit.py` survived, so this run rebuilt:

1. `ncts.txt` from the chunk headings; `work/bundle_parsed.jsonl` via `parse_bundles.py`.
2. `work/ctg.jsonl` — refetched with `fetch_ctg.py` (arm types and `armGroupLabels` are
   needed for step 1e and are absent from `../work/ctg_raw.jsonl`).
3. The drug→alias lexicon (`build_alias.py`), from the bundle ChEMBL synonyms, per-drug
   NCATS GSRS name records (`gsrs2.py`, cached in `work/gsrs_names*.json`) and `curated.py`.
   **Validation:** per-drug trial counts were scored against the `n_trials` column of
   `drug_sequences.tsv` — 224 of 232 drugs reproduce exactly, total hits 8,939 vs 8,921.
   The residual differences are research codes this lexicon resolves and the earlier one did
   not (`ps-341`, `ldp-341`, `zp4207`, `nnc0174-0833`) plus the `parathyroid` alias dropped
   below.

## Rule changes made in this run (all required by the methodology text)
* **Step 1a (explicit sequences).** Re-ran the sequence-token scan over the refetched CTG
  text: 24 candidate trials, 19 already curated, 2 new (`NCT04402957`, `NCT05879432` —
  "LSALT, a peptide drug with the sequence NH3-LSALTPSPSWLKYKAL-COOH", which reproduces the
  GSRS LSALT PEPTIDE record), 3 new rejects (TECENTRIQ, CELLECTRA, PACIENTES).
* **Step 1d/1f/2b (research-code resolution).** Codes and -tide/-pepimut names appearing in
  a trial's own text were resolved against the bundle ChEMBL records (`sweep1.py`,
  `step1d_chembl.py`) and GSRS (`gsrs_resid.py`); see `additions.py`. New annotated drugs:
  dulaglutide, albiglutide, efpeglenatide, supaglutide and romiplostim (peptide portion of
  the fusion/peptibody, step 2d), galinpepimut-S, ombipepimut-S, disitertide and the GP2
  peptide — about 70 trials that previously had no sequence. New documented empties:
  rindopepimut, fluciclatide, SAR425899, NY-ESO-1 (antigen, not an epitope), QS-21,
  cefilavancin, corifollitropin alfa, somatropin, filgrastim.
* **Step 1c (generic family terms).** The lexicon's gonadorelin family aliases
  ("gonadotropin-releasing hormone", "luteinizing hormone-releasing factor") were producing
  native GnRH in 40 trials that name a specific agonist/antagonist or another study peptide
  — the failure the methodology calls out ("'gonadotro…' must not produce gonadorelin in a
  radioligand trial"). A gonadorelin hit matched only through a family name is now dropped
  when any other peptide drug is identified, and a class-level mention (GnRH/LHRH agonist,
  antagonist or analogue) is treated as not determinable. 21 genuine native-GnRH trials
  (pulsatile GnRH therapy, GnRH tests, Gonadorelin/Lutrepulse) keep the sequence.
* **Wrong form (failure group 6).** The loose alias `parathyroid` was assigning PTH(1-84) to
  three PTHrP(1-36) trials, a calcitonin trial and a thymus-transplant trial; it is dropped
  and `parathyroid hormone-related protein` / `pthrp` now resolve to the PTHrP entry.
* **Notation.** The joined `Sequence` field de-duplicates at the peptide level, so a trial
  that matches DSP-7888 together with its two components reports the three peptides once.
* Aib stays `X` per the methodology's notation key (confirmed with the requester).

## Files
`additions.py` (this run's lexicon additions, with per-entry evidence), `build_alias.py`,
`gsrs2.py`, `gsrs_resid.py`, `sweep1.py`, `step1d_chembl.py`, `resid_review.py`,
`check.py` (output notation/consistency checks), patched `assemble.py` and `explicit.py`.
`work/` keeps the GSRS caches, `drugs.json.gz` and `match2.json.gz` so the run can be
reproduced without refetching.

## Second lexicon pass (2026-10-22, `additions2.py` + `apply2.py`)
The rows left with *no peptide drug identified* were swept for a bundle ChEMBL peptide name,
then re-tested against step 1f's gate (the drug is annotated only where a lexicon alias or
research code for it appears in the trial's own CTG text). 29 rows changed; every one was
read individually against its CTG record.

**New drugs (step 1d/1f/2b).** `elpamotide` → `RFVPDGNRI` (ChEMBL biotherapeutic
CHEMBL2108295, from the epitope code VEGFR2-169 in the trial text); `vegfr1-1084 peptide` →
`SYGVLLWEI` (stated in NCT00683358's own record in this corpus); `rm2` →
`fQWAVGH(Sta)L(NH2)` (GSRS RM-2 GA-68 / BAY 86-7548 structure decomposed, reproducing the
structure stated verbatim in NCT02559115's record); `preimplantation factor` →
`MVRIKPGSANKPSDD` (PubChem CID 134687212 decomposed, 15 residues, coverage 1.0). GSRS has
no sequence for any of the four — all are `substanceClass: chemical`.

**Correction found by this pass.** NCT02624518 is a 68Ga-RM2 trial that was annotated with
the native gastrin-releasing peptide precursor fragment, because GRP is generic and no
specific agent had matched. Adding `rm2` makes step 1c suppress GRP and gives the
GRPR-antagonist sequence instead.

**Glued-token matching (`match2.py`).** The n-gram matcher splits only on spaces, so a
peptide name glued into a radioligand or salt name was never seen
(`68Ga-NODAGA-exendin-4`, `Lu-177-DOTA-Octreotide`, `[225Ac]Ac-DOTATATE`,
`Cyclosporine-A`, `Insulin-plus-pramlintide`). A hyphen-delimited sub-run of a compound
token may now name a drug, under four guards, each of which was needed by an observed
false positive:
1. a family/class alias never matches this way (the gonadorelin synonyms above all);
2. the following hyphen-part must not be a word that changes the entity — `glucagon-like`
   is GLP-1, `angiotensin-converting` is an enzyme, `calcitonin-gene` is CGRP,
   `luteinizing-hormone` is a class phrase;
3. the alias must be ≥5 characters and contain a run of ≥4 letters, so a research or
   protocol code never matches from inside a token: `FP-001-IM` is the study code of a
   **parathyroid-hormone** trial (NCT00365456) and the lexicon carries `fp-001` as a
   leuprolide code;
4. a drug found *only* this way yields to any drug the trial names directly, because the
   parent peptide's name sits inside its own derivative's name —
   `1-deamino-8-D-arginine-vasopressin` is desmopressin (NCT00337766),
   `90Y-DOTA-3-Tyr-octreotide` is edotreotide (NCT03044977), `LAPS-exendin-4` is
   efpeglenatide (NCT02057172). Plain octreotide additionally yields to a conjugated
   somatostatin analogue named in the same token (NCT04917484).

**Deliberately not added**, because the step-1f gate rejects them — the bundle ChEMBL name
has no support in the trial's own text, these bundles having been retrieved by search term:
INSULIN HUMAN (80 rows), INSULIN LISPRO (77), PR1 LEUKEMIA PEPTIDE VACCINE (65 of 66),
SVN53-67/M57-KLH PEPTIDE VACCINE / SurVaxM (55), PEPTIDE YY HUMAN (3-36) (4) and
GALLIUM (68Ga) ROFAPITIDE TETRAXETAN (5 — the two trials carrying it are
68Ga-NODAGA-exendin-4 studies and the other three are 68Ga-DOTANOC studies, so the
rofapitide record is a retrieval artifact in all five). SurVaxM and PR1 keep the sequences
they already had in the trials that do name them.

**New documented empty.** `glutathione` (37 trials): gamma-Glu-Cys-Gly, whose
gamma-glutamyl bond is not a backbone peptide bond, so it is not representable in
single-letter code — the same reasoning the methodology applies to carnosine's beta-alanyl
bond. These rows previously read "no peptide drug identified".

## Reproducing
```
gunzip -c work/drugs.json.gz > work/drugs.json   # first-pass lexicon
python3 parse_bundles.py                         # work/bundle_parsed.jsonl
python3 fetch_ctg.py                             # work/ctg.jsonl (arm types; resumable)
python3 apply2.py                                # fold in additions2.py
python3 match2.py                                # work/match2.json
python3 assemble.py ../sequence_10_19_2026.csv
python3 check.py ../sequence_10_19_2026.csv
```
`match2.py.bak` / `assemble.py.bak` are the first-pass versions.
