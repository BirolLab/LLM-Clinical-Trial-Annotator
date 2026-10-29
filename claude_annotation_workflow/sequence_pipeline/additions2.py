# -*- coding: utf-8 -*-
"""Second lexicon pass for sequence_10_19_2026.csv (2026-10-22).

Every entry was found by sweeping the rows that step 1a-1d left with *no peptide drug
identified* for a bundle ChEMBL peptide name, then testing step 1f's gate: the drug is
annotated only where a lexicon alias or research code for it appears in the trial's own
ClinicalTrials.gov text.  Sequences come from the step-2b source order.

Deliberately NOT added, because the step-1f gate rejects them (the bundle ChEMBL name has
no support in the trial's own text - these bundles were retrieved by search term):
  INSULIN HUMAN (80 rows), INSULIN LISPRO (77), PR1 LEUKEMIA PEPTIDE VACCINE (65 of 66),
  SVN53-67/M57-KLH PEPTIDE VACCINE / SurVaxM (55), PEPTIDE YY HUMAN (3-36) (4),
  GALLIUM (68Ga) ROFAPITIDE TETRAXETAN (5: the two trials that carry it are
  68Ga-NODAGA-exendin-4 studies and the other three are 68Ga-DOTANOC studies, so the
  rofapitide record is a retrieval artifact in all five).
"""
# key -> (aliases, sequence, source, confidence)
NEW_DRUGS2 = {
 'elpamotide': (['elpamotide', 'vegfr2-169', 'vegfr2 169', 'vegfr2-169 peptide',
   'vegfr2-a24-169', 'ots-102', 'ots102', 'otsgv-101'],
   'RFVPDGNRI',
   'ChEMBL biotherapeutic biocomponent sequence for ELPAMOTIDE (CHEMBL2108295) in the trial '
   'bundles, identified from the epitope code VEGFR2-169 in the '
   "trial's own intervention name; the NCATS GSRS ELPAMOTIDE record (S68632MB2G) is "
   'substanceClass chemical and carries no subunit sequence', 'High'),
 'vegfr1-1084 peptide': (['vegfr1-1084', 'vegfr1 1084', 'vegfr1-a24-1084', 'vegfr1-1084 peptide'],
   'SYGVLLWEI',
   'sequence stated in the ClinicalTrials.gov record of NCT00683358 in this corpus: '
   '"HLA-A*2402-restricted VEGFR1-derived peptide (VEGFR1-A24-1084; SYGVLLWEI)" '
   '(methodology step 2b.1), applied to the other trials naming the same epitope code',
   'Medium'),
 'rm2': (['rm2', 'rm-2', '68ga-rm2', 'ga-68 rm2', 'rm-2 ga-68', 'bay 86-7548', 'bay-86-7548',
   'bay 86 7548', '68ga-dota-bombesin', 'dota-bombesin', 'grpr antagonist rm2'],
   'fQWAVGH(Sta)L(NH2)',
   'NCATS GSRS record RM-2 GA-68 (NPI2H5M36D, = BAY 86-7548) structure decomposed into '
   'residues by the pipeline decomposer, which resolves fQWAVG directly and shows His then '
   'the statine unit and the C-terminal Leu-amide; this reproduces the structure stated '
   'verbatim in the ClinicalTrials.gov record of NCT02559115 in this corpus '
   '("DOTA-4-amino-1-carboxymethylpiperidine-D-Phe-Gln-Trp-Ala-Val-Gly-His-Sta-Leu-NH2"). '
   'Chelator and radionuclide omitted (step 2e); Sta = statine', 'High'),
 'preimplantation factor': (['preimplantation factor', 'pre-implantation factor', 'pif-1',
   'pif 1', 'spif', 's-pif', 'synthetic preimplantation factor',
   'synthetic pre-implantation factor'],
   'MVRIKPGSANKPSDD',
   'PubChem structure of synthetic preimplantation factor (CID 134687212, C67H115N21O23S) '
   'decomposed into residues by the pipeline decomposer (15 residues, coverage 1.0, no '
   'unresolved fragments); the NCATS GSRS PREIMPLANTATION FACTOR record (3K6A6FJ98O) and '
   'the bundle ChEMBL record CHEMBL4298118 are both substanceClass chemical / molecule_type '
   'Unknown and carry no subunit sequence', 'High'),
}
# extra aliases for keys already in the table
ALIAS_ADD3 = {
 # "Thymosin-alpha1" normalises to the token pair "thymosin- 1" because the greek letter is
 # stripped, so the thymalfasin aliases ("thymosin alpha 1") never matched it
 'thymalfasin': ['thymosin- 1', 'thymosin-1', 'thymosin a-1', 'thymosin- a1'],
 # "Calcitonin-Gene Related Peptide" / "calcitonin-gene-related peptide": the hyphenated
 # spellings must reach CGRP and must never be read as the drug calcitonin
 'calcitonin gene-related peptide': ['calcitonin-gene related peptide',
   'calcitonin-gene-related peptide', 'calcitonin-gene related', 'alpha-cgrp', 'cgrp-alpha'],
}

# identified but not annotatable (methodology deliberate empties), with the reason
NEW_EXCLUDE2 = {
 'glutathione': 'gamma-Glu-Cys-Gly: the gamma-glutamyl bond is not a backbone peptide bond, '
   'so the tripeptide is not representable in single-letter code (same reason as carnosine, '
   "whose beta-alanyl bond is excluded); 35 trials name it as the study agent",
}
ALIAS_ADD4 = {
 'glutathione': ['glutathione', 'l-glutathione', 'reduced glutathione', 'gsh',
   'oxidized glutathione', 'glutathione disulfide', 'n-acetyl glutathione'],
}
