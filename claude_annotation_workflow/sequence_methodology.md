# sequence_10_14_2026.csv — method notes

Scope: all 7,734 NCT records present in `bundles_chunks/*.md`. Input files are fixed;
the revision below changes only how they are read and annotated.

## Revision (2026-10-19): changes to raise agreement with `train_df.csv`
The previous version agreed with the double-annotated training set at Gwet's AC1
≈ 0.51, against a human–human AC1 of ≈ 0.55. It matched 72% of the rows where both
human annotators agree. Nearly all of the misses fell into five groups, each handled by
a rule below (each rule notes which group it addresses):

| # | Failure | Rule that addresses it |
|---|---|---|
| 2 | Named peptide or vaccine left empty although its sequence is published | Steps 2b, 2c, 2d |
| 3 | No peptide drug identified at all | Steps 1a, 1d |
| 4 | Background/comparator peptides added as extra drugs | Step 1e |
| 5 | Sequence filled from weak evidence (bundle ChEMBL names, loose matches) | Steps 1c, 1f |
| 6 | Wrong form of the peptide (species, fragment vs full length) | Step 2e |

The training labels are used only to **evaluate** the rules, never as a lookup table:
no sequence in the output may be copied from `train_df.csv`.

## Pipeline
1. **Peptide-drug identification (per trial).**
   a. **Explicit sequences first.** Before any lexicon matching, search the trial's
      `interventions`, `title` and description text for runs matching
      `[ACDEFGHIKLMNPQRSTVWY]{5,}` and for three-letter chains
      (`Ac-Gln-Gln-Arg-…`). Accept a hit as the trial's sequence when it sits next to the
      drug name or the words peptide/sequence/epitope. Reject brand names, gene symbols,
      database names and trademarks that happen to look like sequences (SYFPEITHI,
      ADCETRIS, TECENTRIQ, VLINIVAL).
   b. **Lexicon match.** A lexicon of canonical peptide drugs (generic names, brand
      names, research codes) is matched against `interventions`, `search_terms` and
      `title` (token-boundary matching on normalised text). Overlapping matches resolve
      to the longest alias. Lexicon additions/corrections in this revision:
      - P11-4 = Curodont / oligopeptide P11-4 / self-assembling peptide P11-4 →
        `(Ac)QQRFEWEFEQQ(NH2)` (a topical dental peptide, **not** a vaccine).
        "phosphopeptide" and "casein phosphopeptide" are no longer vaccine triggers.
      - evuzamitide = p5+14 / "p5 14" / 124I-evuzamitide.
      - LSALT peptide (metablok), omiganan, and the named epitope vaccines (6MHP,
        12-MP, SurVaxM, PR1, gp100, WT1, survivin, NY-ESO-1, HER2/E75/GP2/AE37) each
        get their own lexicon entry and are no longer folded into
        `peptide vaccine unspecified`.
   c. **Specific beats generic, and the trial text beats the bundle.** Generic family
      terms ("GLP-1", "GnRH agonist", bare "insulin", "gonadotropin", "calcitonin")
      are suppressed whenever a specific agent also matched. Specific agents include
      radioligands such as DOTA-TATE, NeoB and PSMA-617; for example, "gonadotro…"
      must not produce gonadorelin in a radioligand trial.
   d. **Research-code resolution.** Unmatched intervention tokens that look like
      research codes (`[A-Z]{1,5}[- ]?\d{2,6}`, or a name ending in -tide/-relin/-pressin/
      -tocin/-glutide) are resolved by name in GSRS, then ChEMBL (see Step 2b).
      This replaces "no peptide drug identified" for codes that can be resolved.
   e. **Experimental-arm restriction.** Annotate only peptides given as an
      investigational intervention in an experimental arm. Drop peptides that appear
      only as:
      - an active comparator or standard-of-care background (e.g. basal insulin in a
        GLP-1 trial, octreotide as background in a PRRT trial);
      - rescue medication;
      - a test, clamp or challenge agent (glucose-clamp insulin, glucagon stimulation
        test, secretin test, a gonadorelin stimulation test). Keep the agent only when
        the trial studies that agent itself, e.g. a CGRP-provocation study;
      - a family name implied by the drug's mechanism (native GLP-2 in a teduglutide
        trial, native GLP-1 or glucagon in an analogue trial).
      Use the arm/intervention-type fields from the CTG record. Do not use `|` for a
      second peptide unless it is itself experimental.
   f. **Bundle ChEMBL fallback is identification-only, and gated.** A ChEMBL
      `pref_name` from the trial's bundle may name a drug only if a lexicon alias or
      research code for that drug also appears in the trial's own text. A ChEMBL name
      with no support in the trial text (e.g. `PR1 LEUKEMIA PEPTIDE VACCINE`,
      `CALCITONIN HUMAN`, `INSULIN HUMAN`) no longer produces a sequence.

2. **Sequence assignment.**
   a. **Native/endogenous peptides.** Sequences are taken from the UniProt/EBI precursor
      sequences and feature ranges in the bundle files (e.g. kisspeptin-54, apelin-13,
      GIP(1-42), LEAP2, relaxin-2 chains cut directly out of the bundle precursors).
   b. **Analogues, investigational peptides and named vaccines: external lookup before
      leaving the sequence empty.** "Not verifiable from file" is no longer enough
      reason to leave a row empty. Look up the sequence in this order and record
      the source:
      1. Sequences stated in the CTG record itself (Step 1a).
      2. NCATS GSRS (`protein.subunits[].sequence`, plus structural modifications for
         Aib, acylation and amidation positions).
      3. ChEMBL `biotherapeutic.biocomponents` (best for INN peptide vaccines).
      4. The trial's own protocol/SAP PDF on `cdn.clinicaltrials.gov/large-docs/`
         (peptide-composition tables; converted with `pdftotext`).
      5. UniProt (for epitopes named by protein + residue range, e.g. "HER2 369-377"
         → `KIFGSLAFL`) and the drug's primary publication.
      Leave the sequence empty only if all five sources fail.
   c. **Multi-epitope / multi-peptide vaccines.** List every defined peptide in the
      vaccine, separated by `|`, in the order the protocol lists them (e.g. 6MHP's
      class II helper peptides, 12-MP's epitopes). Leave the row empty only for
      personalised neoantigen vaccines, whose sequences differ by patient and are not
      published.
   d. **Peptibodies and peptide–Fc / peptide–protein fusions.** Report the
      pharmacologically active peptide portion (e.g. romiplostim → `IEGPTLRQWLAARA`),
      not the carrier protein. Antibodies, cytokines and other full-length recombinant
      proteins are still not annotated.
   e. **Choosing the form of the peptide.**
      - Species: use the clinically marketed form unless the trial names another.
        For example, calcitonin defaults to salmon calcitonin
        (`CSNLSTCVLGKLSQELHKLQTYPRTNTGSGTP(NH2)`); human calcitonin only when "human"
        is in the trial text.
      - Length: use the mature, administered peptide. Use a precursor or a longer
        isoform only when the trial names it (e.g. "pro-…", "full-length",
        a residue range).
      - Radiolabelled peptides (DOTATATE, DOTATOC, DOTANOC, NeoB, satoreotide
        and others) are annotated with their peptide portion, as before, when the
        radioligand is the experimental therapy. Chelator and radionuclide are
        omitted.
3. **In-file corroboration.** For every annotated sequence, a natural-amino-acid core of
   ≥8 residues is searched against all sequences in that trial's own bundle. Hits are
   recorded in `Evidence` as `in-file support: ... bundle sequence <acc>`.

## Notation
- Single-letter uppercase codes for natural L-amino acids; D-amino acids lowercase.
- Modifications / non-proteinogenic residues in round brackets, e.g. `(pGlu)`, `(NH2)`,
  `(Ac)`, `(MeLeu)`, `(Mpa)`, `(NHEt)`, `s(tBu)`.
- `X` = Aib (2-aminoisobutyric acid).
- `/` separates the chains of a multi-chain peptide (insulins: A-chain/B-chain; relaxin).
- `|` separates different peptides in the same trial: co-tested experimental drugs,
  or the components of one multi-peptide vaccine.
- Lipid, PEG, chelator (DOTA/DTPA) and cytotoxic conjugates are omitted — peptide only.
- The training annotators write the same peptide several ways (`fCYwKTCT`,
  `dFCYdWKTCT`, `F C Y W K T C T`), and they include modifications only sometimes. The
  output keeps the notation above. Agreement is scored on a **canonical form**:
  remove `(…)`/`[…]` modifications, the `d` prefix before an uppercase residue, and
  whitespace and punctuation; uppercase; sort chains within `/` and peptides within `|`.

## Columns
- `Sequence` — empty where no peptide sequence could be supported by evidence.
- `Confidence` — `High` / `Medium` / `Low` for the weakest sequence reported in the row;
  `n/a` where no sequence is reported.
  - High: sequence stated in the CTG record or protocol, or a GSRS/ChEMBL/UniProt
    record matched by exact name.
  - Medium: taken from a primary publication, or a UniProt residue-range cut.
  - Low: identification or sequence depends on a single indirect source.
  Rows where a co-tested *experimental* peptide has no annotated sequence are
  downgraded to `Low` and flagged (`NOTE: co-tested agent(s) without annotated
  sequence`). Peptides removed by Step 1e do not trigger this note.
- `Evidence` — for each identified drug: the matched string and where it came from
  (trial text, research-code lookup, or gated bundle ChEMBL evidence); the assigned
  sequence; the confidence; the sequence source (CTG text / GSRS / ChEMBL / protocol
  PDF / UniProt / publication); any in-file corroboration. Also lists every peptide
  dropped under Step 1e, with the reason (e.g. `dropped insulin glargine: background`).

## Deliberate empties (`Confidence = n/a`)
- No peptide drug identifiable after Steps 1a–1d (placebo-only arms, imaging/procedure
  arms with no peptide, protein hydrolysates).
- Personalised neoantigen vaccines (patient-specific sequences).
- Antibodies, cytokines, growth factors, gonadotropins, plasma proteins and other
  full-length recombinant proteins (peptibodies are annotated under Step 2d).
- Peptides whose structure is not representable in single-letter code: glycopeptide and
  lipoglycopeptide antibiotics (vancomycin, teicoplanin, telavancin, dalbavancin,
  oritavancin), echinocandins, polymyxins/colistin, daptomycin, bacitracin, bleomycin,
  dactinomycin, romidepsin, carfilzomib, bortezomib, pasireotide.
- Investigational peptides whose sequence is still not found after every source in
  Step 2b. The `Evidence` field names the sources tried.

## Validation
Score `Sequence` against `train_df.csv` (`Sequence_ann1`, `Sequence_ann2`) on the
canonical form above. Report:
1. AC1 against each annotator, next to the human–human AC1 (≈ 0.55), which is
   effectively the ceiling;
2. the match rate on rows where both annotators agree;
3. the match rate restricted to training trials inside the 7,734-trial scope. 183
   training NCT ids have no bundle, so they are empty by construction.

Counts by confidence level will be recomputed when the file is regenerated.
