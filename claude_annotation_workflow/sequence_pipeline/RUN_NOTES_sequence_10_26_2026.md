# `sequence_10_26_2026.csv` — run notes (built 2026-10-26)

Scope: the **12,372** `# NCT…` headings in `bundles_chunks/*.md` of the primary working
directory (`ncts_10_26.txt`), the same id set and order as `outcome_10_26_2026.csv`.
Method: `../sequence_methodology.md`.

No prior annotation output was read. `train_df.csv` is not present anywhere in this
workspace, so the methodology's Validation section could not be run — the agreement
figures it asks for are **not** reported below.

## The corpus changed
The methodology text and the 10/19 run describe a 7,734-record corpus. This corpus is
different, not merely larger: 7,192 ids are shared, 542 of the old ids are gone and
**5,180 are new**. Everything downstream was rebuilt against the current files.

| Confidence | rows |
|---|---|
| High | 4,963 |
| Medium | 632 |
| Low | 7 |
| n/a (no sequence) | 6,770 |
| **total** | **12,372** |

5,602 rows carry a sequence (433 distinct sequence strings); 863 report more than one
peptide; 2,028 carry in-file corroboration against a bundle UniProt sequence. Of the
6,770 empties, 2,484 name a drug that is a documented deliberate empty, 149 had every
candidate dropped by step 1c/1e, 4,131 identify no peptide drug at all (overwhelmingly
trials whose drugs are antibodies, cytokines or small molecules) and 6 are the step-1a
rejects plus two investigational peptides with no sequence in any step-2b source.

## What was rebuilt, and from what
1. `ncts_10_26.txt` from the current chunk headings; `work26/bundle_parsed.jsonl` via
   `parse_bundles26.py` (12,372 records, 55,602 ChEMBL rows, 43,443 UniProt rows).
2. `work26/ctg.jsonl` — the 7,192 shared ids were reused from the earlier fetch and the
   5,180 new ids fetched with `fetch_ctg26.py`. Every id in scope has a record except
   `NCT07848204`, which the API no longer returns.
3. The lexicon (`build_alias26.py` → `apply2_26.py` → `apply3.py`). **ChEMBL synonyms now
   come from this corpus's own bundle ChEMBL records**, not from the previous corpus's
   `by_source/chembl.jsonl`, which does not exist here. That alone added 62 aliases the
   old corpus did not carry (carperitide/ANP, BI 456906, BLP-25, …) and dropped 5
   (aprotinin's, whose ChEMBL record is not in these bundles). 270 drug keys, 4,541 aliases.

## Rule changes made in this run (each required by the methodology text)
* **Step 1a — explicit sequences, re-run over the new records** (`explicit_scan26.py`,
  `explicit_filter26.py`): 1,188 trials carry a sequence-looking token, 34 survive the
  context filter, and 7 are new and curated in `additions3.py`'s `EXPLICIT3`. Two of them
  correct a wrong form the lexicon had assigned (failure group 6):
  `NCT00003224` states gp100 [280-288] as **YLEPGPVTA**, not the 288V analogue ovemotide;
  `NCT00951743` names "Monomeric Dala1-peptide T-amide", so **aSTTTNYT(NH2)**, not plain
  peptide T. The others are `NCT00470379` (NY-ESO-1b SLLMWITQC), `NCT01588756`
  ((Ac)SDKP(NH2)), `NCT01658410` (BQ-123, **wdPvL**), `NCT03246659` (111In-CP04,
  eeeeeeAYGWMDF(NH2)) and `NCT02821494` (Hespecta, the two HPV-16 E6 long peptides).
* **Step 1c, generalised from the gonadorelin rule.** A generic family term that a trial
  names only in its title/search terms, and names there at class level — "GLP-1 receptor
  agonist", "angiotensin-converting enzyme inhibitor", "endothelin receptor blockade" —
  names the target or the drug class, not an administered peptide. 64 rows affected. This
  is the failure the methodology calls out for gonadorelin, reappearing for GLP-1,
  angiotensin, endothelin, somatostatin, bradykinin, GIP and CGRP.
* **Step 1e, two fixes.**
  - `TESTRX` matched a bare `clamp`, so "before aortic cross-declamping" demoted
    `NCT00987207`'s own experimental cyclosporine as a clamp agent. The pattern now
    requires the clamp *technique*.
  - The "a demoted peptide is still the trial's peptide drug when no experimental peptide
    remains" fallback was re-admitting peptides that really are background. It now yields
    when the trial's experimental arm(s) carry a drug/biological intervention that is not
    the peptide itself: 106 rows, e.g. cyclosporine under belatacept/sirolimus/JAK3-inhibitor
    arms, oxytocin against misoprostol, teriparatide against ronacaleret and romosozumab,
    terlipressin against ambrisentan, leuprolide against TAK-385. Trials where the peptide
    *is* the experimental agent keep it (DPT-1 insulin, NCT00592410, NCT00686972).
* **Steps 1d/1f/2b — new drugs** (`sweep26.py`, `sweep26b.py`, `gsrs26.py`, `rangescan26*.py`,
  all folded into `additions3.py`): 10 new annotated drugs and 5 new documented empties.
  - From GSRS by research code: **onilcamotide** (RV001V) `ATRAGLQVRKNKRRRGCPIL`,
    **pegtarazimod** (RLS-0071) `IALILEPICCQERAA`.
  - From a residue range stated in the trials' own records, cut from UniProt (step 2b.5):
    telomerase 540-548 `ILAKFLHWL` (O14746), p53 264-272 `LLGRNSFEV` (P04637),
    MART-1 27-35 `AAGIGILTV` (Q16655), NY-ESO-1 157-165 `SLLMWITQC` (P78358),
    PSA 154-163(155L) `VLSNDVCAQV` (P07288 mature numbering, with the 155L substitution
    the record specifies).
  - From the primary literature plus a UniProt cut: **6MHP**'s six class II peptides
    (gp100 44-59, tyrosinase 56-70 and 386-406, Melan-A 51-73, MAGE-A3 281-295,
    MAGE-A1/2/3/6 121-134) — five of the six cuts reproduce the first three residues
    reported for the vaccine; **INGAP peptide** `IGLHDPSHGTLPNGS` (INGAP 104-118, UniProt
    Q92778); **URLC10/LY6K-177** `RYCNLEGPPI`, which is also a contiguous 10-mer of the
    bundles' own UniProt Q17RY6.
  - New documented empties: **sargramostim** (and its aliases Leukine/Prokine/DRG-0012 —
    240 rows that previously read "no peptide drug identified"; 127-aa recombinant GM-CSF),
    **vitespen/HSPPC-96** (782-residue gp96 carrier, patient-specific cargo),
    **vipivotide tetraxetan / PSMA-617** (urea-based peptidomimetic, GSRS substanceClass
    chemical), **enlicitide / MK-0616** (macrocyclic peptide, no protein subunits),
    **collagen peptides** (undefined hydrolysate, 53 rows).
  - Aliases onto existing keys: E75/NeuVax → nelipepimut-S, rhBNP → nesiritide,
    WT-1:126-134 → the WT1 126-134 peptide, "tetanus peptide" → the tetanus helper peptide.
* **Evidence wording.** The per-drug sequence sources were recorded when the ChEMBL
  structures were read from the previous corpus's `by_source/` dump. That path does not
  exist in this corpus, so the ChEMBL record is now cited by its id alone.

## Known remaining gaps (documented, not silently empty)
Epitope and multi-peptide vaccines whose components this corpus does not define and which
no step-2b source resolved: TPIV200 / multi-epitope folate-receptor-alpha vaccine (5),
"HER-2/neu peptide vaccine" (5), mutant ras and p53 peptide vaccines (9 and 7),
CMV pp65 peptide vaccines (7), HPV-16 E7 peptide (3), UV1 (5), EP2101/IDM-2101 (3),
CBX-12/pHLIP-exatecan (3), EpiVacCorona (3), GM604 (2), BCD-201 (4), MSP-3 LSP (3),
and all personalised neoantigen and warehouse-selected vaccines (e.g. iVAC-CLL01
`NCT02802943`), which are deliberate empties by the methodology.

## Reproducing
```
python3 parse_bundles26.py      # work26/bundle_parsed.jsonl
python3 fetch_ctg26.py          # work26/ctg.jsonl (resumable)
python3 build_alias26.py        # work26/drugs.json
python3 apply2_26.py            # + additions2.py
python3 apply3.py               # + additions3.py
python3 match2_26.py            # work26/match2.json
python3 assemble26.py ../sequence_10_26_2026.csv
python3 check.py ../sequence_10_26_2026.csv
```
`cfg.py` holds the corpus paths; new files this run: `cfg.py`, `parse_bundles26.py`,
`fetch_ctg26.py`, `build_alias26.py`, `apply2_26.py`, `apply3.py`, `additions3.py`,
`match2_26.py`, `assemble26.py`, `explicit_scan26.py`, `explicit_filter26.py`,
`rangescan26.py`, `rangescan26b.py`, `sweep26.py`, `sweep26b.py`, `gsrs26.py`,
`classlevel_probe.py`, `show.py`.
