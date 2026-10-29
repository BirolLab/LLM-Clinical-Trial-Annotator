# -*- coding: utf-8 -*-
"""Lexicon additions produced by this run's step 1d / 1f / 2b sweeps.

Every entry comes from resolving a research code or -tide/-pepimut name that appears in the
trial's own ClinicalTrials.gov text (step 1d) against the bundle ChEMBL records
(step 1f / 2b.3) or NCATS GSRS (step 2b.2).  Aliases are the synonym sets of the resolved
record.  Peptide-Fc / peptide-albumin fusions are cut to their active peptide portion as
required by step 2d.
"""
# key -> (aliases, sequence, source, confidence)
NEW_DRUGS = {
 'disitertide': (['disitertide', 'disitertida', 'p-144', 'p144',
   'peptide 144 tgf beta-1-inhibitor'],
   'TSLDASIIWAMMQN',
   'ChEMBL biotherapeutic biocomponent sequence for DISITERTIDE in the trial bundle '
   '(by_source/chembl.jsonl) and NCATS GSRS record DISITERTIDE subunit (14 residues), '
   'identified from the research code P144 in the trial text', 'High'),
 'galinpepimut-s': (['galinpepimut-s', 'galinpepimuts', 'galinpepimut', 'sls-001', 'sls001'],
   'YMFPNAPYL|SGQAYMFPNAPYLPSCLES|PGCNKRYFKLSHLQMHSRKHTG|RSDELVRHHNMHQRNMTKL',
   'ChEMBL biotherapeutic biocomponents for GALINPEPIMUT-S in the trial bundle: the four WT1 '
   'heteroclitic peptides, identified from the research code SLS-001 in the trial text', 'High'),
 'ombipepimut-s': (['ombipepimut-s', 'ombipepimuts', 'ombipepimut', 'dsp-7888', 'dsp7888'],
   'WAPVLDFAPPGASAYGSL|CRMFPNAPYL|CYTWNQMNL',
   'ChEMBL biotherapeutic biocomponents for OMBIPEPIMUT-S in the trial bundle, read from the '
   'three-letter strings H-Trp-Ala-Pro-Val-Leu-Asp-Phe-Ala-Pro-Pro-Gly-Ala-Ser-Ala-Tyr-Gly-Ser-Leu-OH, '
   'H-Cys-Arg-Met-Phe-Pro-Asn-Ala-Pro-Tyr-Leu-OH and H-Cys-Tyr-Thr-Trp-Asn-Gln-Met-Asn-Leu-OH; '
   'the helper peptide reproduces the adegrapepimut-s entry and the two killer peptides the '
   'elatipepimut-s entry', 'High'),
 'dulaglutide': (['dulaglutide', 'dulaglutida', 'trulicity', 'ly-2189265', 'ly2189265'],
   'HGEGTFTSDVSSYLEEQAAKEFIAWLVKGGG',
   'ChEMBL biotherapeutic sequence for DULAGLUTIDE in the trial bundle, corroborated by NCATS '
   'GSRS DULAGLUTIDE (550 residues); methodology step 2d - the GLP-1 analogue portion is '
   'reported, cut at the (GGGGS)3 linker that precedes the IgG4 Fc '
   '(...LVKGGG | GGGGSGGGGSGGGGS | AESKYGPPCPPCPAPEAAGG...)', 'High'),
 'albiglutide': (['albiglutide', 'albiglutida', 'albiglutide genetical recombination',
   'tanzeum', 'eperzan', 'gsk-716155', 'gsk716155'],
   'HGEGTFTSDVSSYLEGQAAKEFIAWLVKGR',
   'NCATS GSRS record ALBIGLUTIDE (5E7U48495E) subunit: two identical tandem copies of the '
   '30-residue GLP-1(7-36) analogue followed by human serum albumin (DAHKSEVAHRFKDLGEENFKA..., '
   'identified in-file as bundle UniProt P02768 Albumin); methodology step 2d - the peptide '
   'portion is reported, and the two copies are identical so the sequence is given once',
   'High'),
 'efpeglenatide': (['efpeglenatide', 'hm-11260c', 'hm11260c', 'langlenatide',
   'sar-439977', 'sar439977'],
   'HGEGTFTSDLSKQMEEEAVRLFIEWLK(PEG)NGGPSSGAPPPS(NH2)',
   'NCATS GSRS record EFPEGLENATIDE (3M1V5Z2270) subunit 3: the 39-residue exendin-4 analogue, '
   'with the record\'s structural modifications - SERINAMIDE at Ser39 (C-terminal amide) and a '
   'LYSYL-PEG-PROLYL linker at Lys27 (PEG) to the IgG4 Fc subunits 1-2, which are omitted under '
   'step 2d', 'Medium'),
 'supaglutide': (['supaglutide', 'efsubaglutide alfa', 'efsubaglutide'],
   'HGEGTFTSDVSSYLEEQAAKEFIAWLVKGGGSSGAPPPS',
   'NCATS GSRS record Efsubaglutide Alfa (7MFJ5FK8CF) subunit: a GLP-1 analogue with an '
   'exendin-4 C-terminal extension, cut at the GGGGS linker that precedes the Fc '
   '(...GAPPPS | GGGGS | ERKSCVECPPCPAPP...); methodology step 2d', 'Medium'),
 'romiplostim': (['romiplostim', 'nplate', 'amg-531', 'amg531'],
   'IEGPTLRQWLAARA',
   'NCATS GSRS record ROMIPLOSTIM (GN5XU2DXKV) subunit: an IgG1 Fc domain ending '
   '...KSLSLSPGK followed by GGGGG-IEGPTLRQWLAARA-GGGGGGGG-IEGPTLRQWLAARA; methodology step 2d - '
   'the two identical TPO-receptor-binding peptide repeats are reported once, the Fc carrier '
   'omitted', 'High'),
 'gp2 peptide': (['gp2 peptide', 'gp-2 peptide', 'gp2 her2', 'gp2 vaccine', 'gp2 her2-derived'],
   'IISAVVGIL',
   'NCATS GSRS record "GP-2 HER2-DERIVED, HLA-A2+ RESTRICTED PEPTIDE" subunit (9 residues), '
   'matched to the intervention name "GP2 peptide + GM-CSF vaccine"', 'High'),
}
# aliases to remove from the automatic lexicon: too loose, or they capture a different peptide
ALIAS_DROP = {
 'parathyroid': 'matches parathyroid tissue and parathyroid-hormone-related-protein trials '
                'rather than the drug parathyroid hormone',
}
# extra aliases for keys already in the table
ALIAS_ADD2 = {
 'parathyroid hormone-related protein 1-36': ['parathyroid hormone-related protein',
   'parathyroid hormone related protein', 'pthrp', 'pthrp 1-36', 'pthrp 1 36'],
}
# identified but not annotatable (methodology deliberate empties), with the sources tried
NEW_EXCLUDE = {
 'ny-eso-1': 'the record names the antigen, not an epitope: GSRS/UniProt NY-ESO-1 '
   '(CANCER/TESTIS ANTIGEN 1) is the full-length 180-residue antigen and the trials do not state '
   'which epitope peptide(s) are used',
 'rindopepimut': 'KLH-conjugated EGFRvIII peptide; the GSRS record (K3L4X0501F) contains only the '
   'keyhole-limpet-haemocyanin carrier and records the peptide as an unspecified residue-specific '
   'modification, and the bundle ChEMBL record has no biocomponent sequence',
 'fluciclatide': 'cyclic RGD peptide with non-peptidic cross-links, PEG and a fluorobenzoyl group; '
   'no subunit sequence in GSRS and no biocomponent sequence in the bundle ChEMBL record',
 'sar425899': 'investigational GLP-1/glucagon co-agonist; sequence not disclosed in the CTG record, '
   'GSRS or the bundle ChEMBL record',
 'qs-21': 'saponin adjuvant, not a peptide',
 'cefilavancin': 'glycopeptide-cephalosporin conjugate - not representable in single-letter code',
 'corifollitropin alfa': 'glycoprotein gonadotropin - not annotated',
 'somatropin': 'full-length recombinant growth hormone - not annotated',
 'filgrastim': 'full-length recombinant G-CSF - not annotated',
}
