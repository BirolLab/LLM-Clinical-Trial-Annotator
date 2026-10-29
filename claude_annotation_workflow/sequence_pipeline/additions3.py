"""Third lexicon pass, for sequence_10_26_2026.csv.

The corpus changed between the 10/19 run and this one: bundles_chunks/ now holds 12,372
NCT records (5,180 of them new, 542 of the old ones gone).  Every entry below was reached
by running the methodology's steps 1a / 1d / 1f / 2b over the NEW trials' own CTG records
and the current bundle files.  Each carries the evidence that produced it.
"""

# ---------------------------------------------------------------------------------------
# Step 1a: sequences stated verbatim in the trial's own ClinicalTrials.gov record.
# nct -> (sequence, evidence, confidence)
# ---------------------------------------------------------------------------------------
EXPLICIT3 = {
 'NCT00003224': ('YLEPGPVTA',
   'CTG intervention other-name: "peptide 946, gp100 [280-288], YLEPGPVTA"; the arm '
   'descriptions give 100 mcg peptide gp100 [280-288]. The record states the native '
   '280-288 sequence, so it replaces the lexicon ovemotide 288V analogue (YLEPGPVTV) '
   '(failure group 6, wrong form). The tetanus helper peptide co-administered in arms '
   '3-6 ("tetanus peptide", 190 mcg) is not sequence-defined in the record', 'High'),
 'NCT00470379': ('SLLMWITQC',
   'CTG official title: "Transcutaneous (Topical) Peptide Immunization With NY-ESO-1b '
   '(SLLMWITQC) Peptide Using Resiquimod as an Immune Adjuvant"', 'High'),
 'NCT00951743': ('aSTTTNYT(NH2)',
   'CTG brief summary: "ADAPTAVIR, Monomeric Dala1-peptide T-amide (mDAPTA)" - peptide T '
   '(ASTTTNYT) with D-Ala in position 1 and a C-terminal amide; replaces the unmodified '
   'peptide T the lexicon alias produced', 'High'),
 'NCT01588756': ('(Ac)SDKP(NH2)',
   'CTG title: "the Tetrapeptide N-acetyl-Ser-Asp-Lys-Pro-amide (AcSDKP-NH2)" - the '
   'administered GFR-tracer peptide is the agent under study', 'High'),
 'NCT01658410': ('wdPvL',
   'CTG intervention other-name for BQ-123: "Cyclo(-D-Trp-D-Asp-Pro-D-Val-Leu) sodium '
   'salt"; D-residues lowercased. Replaces endothelin-1, which the title '
   '("Short-term Endothelin A Receptor Blockade") names as the receptor target, not as an '
   'administered peptide', 'High'),
 'NCT03246659': ('eeeeeeAYGWMDF(NH2)',
   'CTG intervention: "111In-CP04 (DOTA-(DGlu)6-Ala-Tyr-Gly-Trp-Met-Asp-Phe-NH2"; the DOTA '
   'chelator and the radionuclide are omitted, the six D-Glu residues lowercased', 'High'),
 'NCT02821494': ('DKCLKFYSKISEYRHYCYSLYGTTL|DKKQRFHNIRGRWTGRCMSCCRSSRTRRETQL',
   'CTG intervention other-name for Hespecta: "HPV 16 E6 synthetic peptides (E6 71-95 and '
   'E6 127-158)"; the two residue ranges cut from UniProt P03126 (HPV-16 E6, 158 aa). '
   'The Amplivant adjuvant conjugate is omitted', 'High'),
}

# ---------------------------------------------------------------------------------------
# Steps 1d / 2b: new drug keys.  key -> (aliases, sequence, source, confidence)
# ---------------------------------------------------------------------------------------
NEW_DRUGS3 = {
 'onilcamotide': (['rv001v', 'rv001', 'onilcamotide', 'rhoc peptide vaccine'],
   'ATRAGLQVRKNKRRRGCPIL',
   'NCATS GSRS protein record ONILCAMOTIDE (UQE6KP7T0D, proteinType VACCINE ANTIGEN) '
   'subunit sequence; resolved from the research code RV001V in the trials\' own text',
   'High'),
 'pegtarazimod': (['rls-0071', 'rls0071', 'pegtarazimod'],
   'IALILEPICCQERAA',
   'NCATS GSRS protein record Pegtarazimod (7AUD376O4W, proteinType PEPTIDE) subunit '
   'sequence; resolved from the research code RLS-0071 in the trials\' own text. The GSRS '
   'record carries no PEG attachment site, so no (PEG) is written',
   'High'),
 'urlc10 peptide': (['urlc10', 'urlc-10', 'urlc10 peptide', 'urlc10-177', 'ly6k-177',
                     'urlc10 peptide vaccine'],
   'RYCNLEGPPI',
   'LY6K-177 / URLC10-177 epitope (Cancer Science 2007 CTL-epitope report, confirmed as a '
   'contiguous 10-mer of the bundle\'s own UniProt Q17RY6 lymphocyte antigen 6K sequence)',
   'Medium'),
 '6mhp': (['6mhp', '6 melanoma helper peptide vaccine', 'melanoma helper peptide vaccine',
           '6 melanoma helper peptides', '6 class ii mhc-restricted melanoma-associated peptides',
           '6 melanoma helper peptides restricted by class ii mhc molecules'],
   'WNRQLYPEWTEAQRLD|QNILLSNAPLGPQFP|FLLHHAFVDSIFEQWLRRHRP|RNGYRALMDKSLHVGTQCALTRR|'
   'TSYVKVLHHMVKISG|LLKYRAREPVTKAE',
   'the six class II peptides of 6MHP (gp100 44-59, tyrosinase 56-70, tyrosinase 386-406, '
   'Melan-A/MART-1 51-73, MAGE-A3 281-295, MAGE-A1/2/3/6 121-134) cut from UniProt P40967, '
   'P14679, Q16655 and P43357; five of the six cuts reproduce the first three residues '
   'reported for the vaccine (WNR, FLL, RNG, TSY, LLK) and tyrosinase 56-70 reproduces the '
   'published QNILLSNAPLGPQFP. The trials\' own records name only "6 class II '
   'MHC-restricted peptides" without sequences',
   'Medium'),
 'ingap peptide': (['ingap peptide', 'ingap-peptide', 'ingap pp', 'ingap-pp', 'ingap'],
   'IGLHDPSHGTLPNGS',
   'INGAP pentadecapeptide = residues 104-118 of islet neogenesis-associated protein, cut '
   'from UniProt Q92778 (Mesocricetus auratus pancreatic beta cell growth factor / INGAP); '
   'the 104-118 range is the one the primary literature defines for INGAP-PP',
   'Medium'),
 'telomerase 540-548 peptide': (['telomerase 540-548 peptide', 'telomerase 540-548',
     'telomerase: 540-548 peptide vaccine', 'telomerase 540-548 peptide vaccine',
     'telomerase: 540-548 peptide'],
   'ILAKFLHWL',
   'hTERT residues 540-548 cut from UniProt O14746; the residue range is stated in the '
   'trials\' own intervention names',
   'High'),
 'p53 264-272 peptide': (['p53 264-272 peptide', 'p53: 264-272 peptide', 'p53 264-272'],
   'LLGRNSFEV',
   'TP53 residues 264-272 cut from UniProt P04637; the range is stated in the trial\'s own '
   'intervention name ("p53: 264-272 peptide")',
   'High'),
 'psa 154-163 155l peptide': (['psa 154-163 155l peptide', 'psa:154-163 155l peptide vaccine',
     'psa 154-163 155l peptide vaccine', 'psa-3a', 'psa pep vac', 'psa 154-163 peptide'],
   'VLSNDVCAQV',
   'KLK3 mature-protein residues 154-163 (UniProt P07288 chain 25-261, so precursor '
   '178-187 = VISNDVCAQV) with the 155L anchor substitution the trial\'s own record '
   'specifies ("PSA-3A; PSA: 154-163 [155L]")',
   'High'),
 'ny-eso-1 157-165 peptide': (['ny-eso-1 157-165 peptide', 'ny-eso-1 157-165',
     'ny-eso-1b', 'ny-eso-1 157-165 peptide vaccine',
     'ny-eso-1 157-165 peptide-pulsed autologous dendritic cell vaccine',
     'autologous ny-eso-1 157-165 peptide-pulsed dc vaccine'],
   'SLLMWITQC',
   'CTAG1B residues 157-165 cut from UniProt P78358 (180 aa); the residue range is stated '
   'in the trials\' own intervention names, and NCT00470379 states the sequence verbatim',
   'High'),
 'mart-1 27-35 peptide': (['mart-1 27-35 peptide', 'mart-1:27-35 peptide vaccine',
     'mart-1 27-35', 'mart-1:27-35 peptide', 'mart-1 27-35 peptide vaccine'],
   'AAGIGILTV',
   'MLANA residues 27-35 cut from UniProt Q16655; the range is stated in the trials\' own '
   'intervention names',
   'High'),
}

# ---------------------------------------------------------------------------------------
# Documented empties (methodology "Deliberate empties").  key -> (aliases, reason)
# ---------------------------------------------------------------------------------------
NEW_EXCLUDE3 = {
 'sargramostim': (['sargramostim', 'leukine', 'prokine', 'sagramostim', 'sargramostatin',
     'drg-0012', 'rhu gm-csf', 'rhu gm-cfs', 'recombinant human gm-csf',
     '23-l-leucinecolony-stimulating factor 2', 'granulocyte-macrophage colony stimulating factor'],
   'full-length recombinant GM-CSF (127 residues, NCATS GSRS 5TAA004E22) - a recombinant '
   'protein, not annotated'),
 'vitespen': (['vitespen', 'hsppc-96', 'hspppc-96', 'heat shock protein-peptide complex-96',
     'heat shock protein peptide complex 96', 'oncophage', 'gp96'],
   'autologous tumour-derived gp96 heat-shock-protein-peptide complex: the carrier is the '
   'full-length 782-residue protein (NCATS GSRS VITESPEN H3598Y1TLJ) and the bound peptides '
   'are patient-specific - not annotated'),
 'vipivotide tetraxetan': (['vipivotide tetraxetan', 'vipivotide', 'psma-617', 'psma 617',
     'lutetium lu 177 vipivotide tetraxetan', 'lutetium lu-177 vipivotide tetraxetan',
     '177lu-psma-617', '177lu-labeled psma-617', 'aaa-617', 'aaa617', 'pluvicto'],
   'PSMA-617 is a urea-based peptidomimetic (Glu-urea-Lys pharmacophore with naphthylalanine '
   'and tranexamic-acid linkers); the GSRS records (4YM1W0EGQ5, G6UF363ECX) are '
   'substanceClass chemical with no protein subunits - not representable in single-letter code'),
 'enlicitide': (['enlicitide', 'enlicitide decanoate', 'enlicitide chloride', 'mk-0616'],
   'macrocyclic peptide PCSK9 inhibitor; the GSRS records (R7EZ772VG2, PSR59MCX5M, '
   '3D2DNA8NXK) are substanceClass chemical with no protein subunits - not representable '
   'in single-letter code'),
 'collagen peptides': (['collagen peptide', 'collagen peptides', 'hydrolyzed collagen',
     'collagen hydrolysate', 'collagen hydrolyzed peptides', 'bioactive collagen peptides',
     'marine collagen peptides', 'hydrolysed collagen', 'collagen tripeptide'],
   'enzymatic collagen hydrolysate - an undefined peptide mixture with no single sequence'),
}

# ---------------------------------------------------------------------------------------
# Aliases added to drug keys that already exist.
# ---------------------------------------------------------------------------------------
ALIAS_ADD5 = {
 'nelipepimut-s': ['e75', 'e75 peptide', 'neuvax', 'nelipepimut'],
 'nesiritide': ['recombinant human brain natriuretic peptide', 'rhbnp',
                'recombinant human brain natriuretic peptide rhbnp'],
 'pwt-126 peptide': ['wt-1 126-134', 'wt1 126-134', 'wt-1:126-134 peptide',
                     'wt1 126-134 peptide', 'wt-1 126-134 peptide'],
 'tetanus toxoid helper peptide': ['tetanus peptide', 'tetanus peptide melanoma vaccine',
                                   'tetanus helper peptide', 'modified tetanus p2 peptide'],
}
