# -*- coding: utf-8 -*-
"""Curated additions / corrections on top of the automatic GSRS + ChEMBL lexicon."""

# --- drugs that must never carry a sequence (methodology: deliberate empties) -------------
EXCLUDE = {
 # glycopeptide / lipoglycopeptide antibiotics, echinocandins, polymyxins, other
 # non-representable natural products
 'vancomycin': 'glycopeptide antibiotic - not representable in single-letter code',
 'teicoplanin': 'glycopeptide antibiotic - not representable',
 'telavancin': 'lipoglycopeptide antibiotic - not representable',
 'dalbavancin': 'lipoglycopeptide antibiotic - not representable',
 'oritavancin': 'lipoglycopeptide antibiotic - not representable',
 'caspofungin': 'echinocandin - not representable',
 'micafungin': 'echinocandin - not representable',
 'anidulafungin': 'echinocandin - not representable',
 'colistin': 'polymyxin - not representable',
 'colistimethate': 'polymyxin - not representable',
 'polymyxin b': 'polymyxin - not representable',
 'daptomycin': 'lipopeptide - not representable',
 'surotomycin': 'lipopeptide - not representable',
 'bacitracin': 'cyclic peptide antibiotic - not representable',
 'bleomycin': 'glycopeptide - not representable',
 'dactinomycin': 'chromopeptide - not representable',
 'romidepsin': 'depsipeptide - not representable',
 'carfilzomib': 'peptide epoxyketone - not representable',
 'oprozomib': 'peptide epoxyketone - not representable',
 'bortezomib': 'boronic dipeptide - not representable',
 'ixazomib': 'boronic dipeptide - not representable',
 'pasireotide': 'cyclohexapeptide with non-proteinogenic residues - not representable',
 'telaprevir': 'peptidomimetic protease inhibitor - not a peptide drug',
 'danicopan': 'small molecule - not a peptide',
 'vemircopan': 'small molecule - not a peptide',
 'ltx-109': 'peptidomimetic with non-amino-acid residues - not representable',
 'macimorelin': 'peptidomimetic (D-Trp aldehyde) - not representable',
 'bms-686117': 'peptidomimetic with multiple non-proteinogenic residues',
 'glatiramer': 'random amino-acid copolymer - no defined sequence',
 'glatiramer acetate': 'random amino-acid copolymer - no defined sequence',
 # full-length proteins / growth factors / cytokines / plasma proteins
 'mecasermin': 'recombinant IGF-1 growth factor - not annotated',
 'nepidermin': 'recombinant EGF growth factor - not annotated',
 'aprotinin': 'full-length bovine protease-inhibitor protein - not annotated',
 'tiprelestat': 'engineered 56-aa protein (depelestat) - not annotated',
 'procalcitonin': 'precursor protein, not a drug',
 'cystatin-c': 'plasma protein, not a drug',
 'stromal cell-derived factor 1': 'chemokine, not a drug',
 'c-x-c motif chemokine 9': 'chemokine, not a drug',
 'melanoma antigen recognized by t-cells': 'full-length antigen record, not the vaccine peptide',
 'melanoma antigen recognized by t-cells 1': 'full-length antigen record, not the vaccine peptide',
 'survivin': 'full-length antigen record, not the vaccine peptide',
 'gp-100 antigen': 'full-length antigen record, not the vaccine peptide',
 'telomerase reverse transcriptase': 'full-length antigen record',
 'thymosin': 'ambiguous; thymalfasin (thymosin alpha-1) handled separately',
 'carnosine': 'beta-alanyl dipeptide - beta-linkage not representable',
 'alanyl glutamine': 'nutritional dipeptide, not a peptide drug under test',
 'poly-iclc': 'adjuvant, not a peptide',
 'angiotensin': 'ambiguous ChEMBL record; angiotensin I and II handled separately',
}

# --- brand / duplicate keys that must fold into one drug ---------------------------------
MERGE = {
 'sandostatin': 'octreotide',
 'lenomorelin': 'ghrelin',
 'desacyl ghrelin': 'ghrelin',
 'nesiritide citrate': 'nesiritide',
 'corticotropin human': 'corticotropin',
 'iodine i-124 evuzamitide': 'evuzamitide',
 'insulin 338': 'insulin icodec',
 'gallium oxodotreotide ga-68': 'oxodotreotide',
 'endothelin': 'endothelin-1',
 'vasoactive intestinal peptide': 'aviptadil',
 'glp-1': 'glucagon-like peptide 1',
 'glucagon-like peptide-i 7-36 amide': 'glucagon-like peptide 1',
 'glucagon-like peptide 1 7-36': 'glucagon-like peptide 1',
}

# --- generic family terms: dropped when a specific peptide was also identified -----------
GENERIC = {
 'glucagon-like peptide 1', 'glp-1', 'glucagon-like peptide ii',
 'glucagon-like peptide-i 7-36 amide', 'gastric inhibitory polypeptide',
 'somatostatin', 'ghrelin', 'apelin', 'neuropeptide y', 'bradykinin',
 'substance p', 'endothelin', 'endothelin-1', 'oxyntomodulin',
 'pancreatic polypeptide', 'peptide yy human', 'peptide yy human 3-36',
 'parathyroid hormone', 'calcitonin gene-related peptide', 'angiotensin',
 'angiotensin i', 'angiotensin ii', 'glucagon', 'insulin human',
 'vasoactive intestinal peptide', 'adrenomedullin', 'gastrin-releasing peptide',
 'proinsulin human', 'insulin b-chain human', 'hepcidin',
 'parathyroid hormone-related protein 1-36', 'xenin', 'amylin', 'kisspeptin', 'aviptadil',
 'endothelin-1',
 'pituitary adenylate cyclase-activating polypeptide 38',
 'urocortin-2', 'urocortin-3', 'tetanus toxoid helper peptide',
}

# --- extra aliases for drug keys already in the automatic lexicon -----------------------
ALIAS_ADD = {
 'insulin human': ['insulin', 'regular insulin', 'insulin regular', 'human insulin', 'soluble insulin',
   'human soluble insulin', 'human regular insulin', 'nph insulin', 'insulin nph', 'nph',
   'neutral protamine hagedorn insulin', 'neutral protamine hagedorn', 'isophane insulin',
   'intranasal insulin', 'oral insulin', 'inhaled insulin', 'crystalline insulin',
   'novolin r', 'humulin r', 'humulin', 'actrapid', 'insulatard', 'insuman',
   'technosphere insulin', 'insulin therapy', 'intravenous insulin', 'subcutaneous insulin',
   'continuous insulin', 'intensive insulin therapy', 'pulsatile insulin therapy',
   'insulin injection', 'insulin infusion', 'iv insulin', 'short-acting insulin',
   'rapid acting insulin', 'rapid-acting insulin', 'insulin human recombinant'],
 'calcitonin salmon': ['calcitonin', 'salmon calcitonin', 'calcitonin-salmon', 'miacalcin',
   'miacalcic', 'fortical', 'calcimar', 'calcitonine'],
 'secretin human': ['secretin', 'chirhostim', 'human secretin', 'secrelux'],
 'serelaxin': ['relaxin', 'relaxin-2', 'human relaxin', 'rhrlx'],
 'oligopeptide-104': ['p11-4', 'p11 4', 'curodont', 'curodont repair', 'curodont protect',
   'self-assembling peptide p11-4', 'oligopeptide p11-4', 'sap p11-4'],
 'evuzamitide': ['p5 14', 'p5+14', '124i-evuzamitide', 'iodine i 124 evuzamitide'],
 'lsalt peptide': ['lsalt', 'metablok', 'lsalt peptide'],
 'tertomotide': ['gv1001', 'gv-1001'],
 'nelipepimut-s': ['e75', 'neuvax', 'nelipepimut', 'e75 peptide', 'her2/neu e75'],
 'disomotide': ['gp100 209-217 210m', 'gp100:209-217(210m)', 'gp100 209-217',
   'gp100:209-217', 'g209-2m', 'gp100 209-2m'],
 'ovemotide': ['gp100 280-288 288v', 'gp100:280-288(288v)', 'gp100 280-288', 'gp100:280-288',
   'g280-9v'],
 'glutathione': ['glutathione', 'gsh', 'l-glutathione', 'reduced glutathione'],
 'thymalfasin': ['thymosin alpha 1', 'thymosin alpha-1', 'thymosin a1', 'thymosin alpha1',
   'thymosin fraction 5', 'zadaxin', 'thymalfasin'],
 'kisspeptin': ['kisspeptin', 'kisspeptin-54', 'kisspeptin 54', 'kp54', 'kp-54', 'metastin'],
 'kisspeptin-10': ['kisspeptin-10', 'kisspeptin 10', 'kp10', 'kp-10'],
 'amylin': ['amylin', 'human amylin', 'islet amyloid polypeptide', 'iapp'],
}

# aliases that name a peptide family rather than a specific product: identification is
# good enough to annotate the clinically marketed form, but confidence is capped at Medium
GENERIC_ALIAS = {
 'insulin', 'regular insulin', 'insulin regular', 'soluble insulin', 'human soluble insulin',
 'nph insulin', 'insulin nph', 'nph', 'neutral protamine hagedorn insulin',
 'neutral protamine hagedorn', 'isophane insulin', 'intranasal insulin', 'oral insulin',
 'inhaled insulin', 'crystalline insulin', 'technosphere insulin', 'insulin therapy',
 'intravenous insulin', 'subcutaneous insulin', 'continuous insulin',
 'intensive insulin therapy', 'pulsatile insulin therapy', 'insulin injection',
 'insulin infusion', 'iv insulin', 'short-acting insulin', 'rapid acting insulin',
 'rapid-acting insulin', 'calcitonin', 'calcitonine', 'secretin', 'relaxin', 'somatostatin',
 'glutathione', 'gsh',
}

# --- sequence overrides / additions ------------------------------------------------------
# key -> (sequence, source, confidence, note)
OVERRIDE = {
 'degarelix': ('(Ac)(d2Nal)(dCpa)(d3Pal)S(Aph)(Hor)(dAph)(Cbm)LK(iPr)Pa(NH2)',
   'ChEMBL/PubChem structure (CID 16136245) decomposed; residue 5 = 4-aminophenylalanine '
   'N-acylated with hydroorotic acid, the one residue the automatic backbone cut could not isolate',
   'Medium', 'structure-derived join of the two perceived fragments'),
 'carbetocin': ('(Bua)Y(Me)IQNCPLG(NH2)',
   'PubChem structure (CID 16681432) decomposed; 1-butanoyl (deamino, carba) N-terminus and '
   'O-methyl-Tyr2 restored from the structure',
   'Medium', 'structure-derived join'),
 'bremelanotide': ('(Ac)(Nle)DHfRWK',
   'PubChem structure (CID 9941379) decomposed; Asp-Lys lactam bridge re-joined',
   'Medium', 'structure-derived join'),
 'satoreotide': ('(Cpa)cY(dAph)(Cbm)KTCy(NH2)',
   'PubChem structure (CID 121488181) decomposed; disulfide macrocycle re-joined',
   'Medium', 'structure-derived join'),
 'satoreotide tetraxetan': ('(Cpa)cY(dAph)(Cbm)KTCy(NH2)',
   'PubChem structure (CID 121488181) decomposed; chelator omitted', 'Medium', ''),
 'satoreotide trizoxetan': ('(Cpa)cY(dAph)(Cbm)KTCy(NH2)',
   'PubChem structure (CID 121488181) decomposed; chelator omitted', 'Medium', ''),
 'glucagon-like peptide 1': ('HAEGTFTSDVSSYLEGQAAKEFIAWLVKGR(NH2)',
   'NCATS GSRS protein record GLUCAGON-LIKE PEPTIDE-I(7-36) AMIDE - the circulating/administered '
   'form of native GLP-1', 'High', 'GLP-1(7-36)amide'),
 'bivalirudin': ('fPRPGGGGNGDFEEIPEEYL',
   'PubChem structure (CID 16129704) decomposed; the GSRS subunit sequence writes the '
   'N-terminal D-Phe as X', 'High', ''),
 'ghrelin': ('GSSFLSPEHQRVQQRKESKKPPAKLQPR',
   'NCATS GSRS protein record LENOMORELIN (ghrelin) subunit sequence, corroborated by the bundle '
   'UniProt precursor Q9UBU3 (appetite-regulating hormone) which contains this 28-mer; the ChEMBL '
   'structure for GHRELIN decomposes to a different 28-mer and was not used. Ser3 octanoyl ester omitted',
   'High', ''),
 'kisspeptin': ('GTSLSPPPESSGSPQQPGLSAPHSRQIPAPQGAVLVQREKDLPNYNWNSFGLRF(NH2)',
   'kisspeptin-54 (metastin) cut from the bundle UniProt precursor Q15726 (metastasis-suppressor '
   'KiSS-1): the 54 residues ending at the C-terminal YNWNSFGLRF decapeptide; C-terminally amidated',
   'Medium', 'kisspeptin-54'),
 'amylin': ('KCNTATCATQRLANFLVHSSNNFGAILSSTNVGSNTY(NH2)',
   'human amylin (IAPP 34-70) cut from the bundle UniProt precursor P10997 (islet amyloid '
   'polypeptide); C-terminally amidated', 'Medium', ''),
 'elatipepimut-s': ('CRMFPNAPYL|CYTWNQMNL',
   'NCATS GSRS protein record ELATIPEPIMUT-S: the record lists the two vaccine peptides as separate '
   'subunits, reported here as two peptides', 'High', ''),
 'dirucotide': ('DENPVVHFFKNIVTPRT',
   'NCATS GSRS protein record DIRUCOTIDE subunit sequence (the ChEMBL structure assigns a '
   'D-configuration at Ile which the GSRS record does not)', 'High', ''),
 'nerofe': ('wwtfflpstlwerk',
   'ChEMBL structure decomposed; the structure assigns a D-configuration at every residue, which '
   'could not be confirmed against a second source', 'Low', 'all-D assignment unconfirmed'),
 'kisspeptin-10': ('YNWNSFGLRF(NH2)', 'NCATS GSRS record KISSPEPTIN-10 (UNII) subunit sequence',
   'High', 'C-terminal amide'),
 'oligopeptide-104': ('(Ac)QQRFEWEFEQQ(NH2)',
   'NCATS GSRS record OLIGOPEPTIDE-104 subunit sequence; N-acetyl / C-amide from the same record',
   'High', 'self-assembling dental peptide P11-4'),
 'thymosin beta -4': ('(Ac)SDKPDMAEIEKFDKSKLKKTETQEKNPLPSKETIEQEKQAGES',
   'NCATS GSRS record THYMOSIN .BETA.-4 subunit sequence (N-acetyl only; the record\'s further '
   'post-translational variants are not part of the drug substance)', 'Medium', ''),
 'glutathione': ('(gGlu)CG', 'tripeptide gamma-L-glutamyl-L-cysteinyl-glycine; the gamma-glutamyl '
   'linkage is marked (gGlu)', 'Low', 'non-standard gamma peptide bond'),
 'veldoreotide': ('(2Nal)cY(dAph)KTF', 'PubChem structure (CID 9919857) partial decomposition',
   'Low', 'cyclic somatostatin analogue; only part of the ring could be resolved'),
}

# --- drugs absent from both automatic lexicons: curated entries --------------------------
# key -> (aliases, sequence, source, confidence)
SUPP = {
 'oxodotreotide': (['oxodotreotide', 'dotatate', 'dota-tate', 'dota tate', 'dotatate lutetium',
   'lutetium lu 177 dotatate', 'lutetium lu-177 dotatate', '177lu-dotatate', 'lu-177 dotatate',
   'lu 177 dotatate', 'lutathera', '68ga-dotatate', 'ga-68 dotatate', 'gallium ga 68 dotatate',
   'gallium-68 dotatate', '64cu-dotatate', 'cu-64 dotatate', 'copper cu 64 dotatate',
   'detectnet', 'octreotate', 'tyr3-octreotate', 'dota0-tyr3-octreotate',
   '177lu-dota0-tyr3-octreotate', '90y-dotatate', 'dota-octreotate'],
   'fCYwKTCT', 'PubChem structure of oxodotreotide / DOTA-TATE (CID 11170867) decomposed; '
   'DOTA chelator and radionuclide omitted', 'High'),
 'edotreotide': (['edotreotide', 'dotatoc', 'dota-toc', 'dota toc', '177lu-dotatoc', '90y-dotatoc',
   '68ga-dotatoc', 'ga-68 dotatoc', 'gallium ga 68 edotreotide', 'yttrium y 90 edotreotide',
   'lutetium lu 177 edotreotide', 'dota0-tyr3-octreotide', 'dota-tyr3-octreotide'],
   'fCYwKTCT(ol)', 'PubChem structure of edotreotide / DOTA-TOC (CID 158782) decomposed; '
   'DOTA chelator and radionuclide omitted', 'High'),
 'icatibant': (['icatibant', 'firazyr', 'icatibant acetate', 'hoe 140', 'hoe-140'],
   'rRP(Hyp)G(Thi)S(Tic)(Oic)R', 'PubChem structure (CID 6918173) decomposed', 'High'),
 'histrelin': (['histrelin', 'histrelin acetate', 'vantas', 'supprelin', 'supprelin la'],
   '(pGlu)HWSYh(Bzl)LRP(NHEt)', 'PubChem structure (CID 25077993) decomposed', 'High'),
 'sincalide': (['sincalide', 'kinevac', 'cck-8', 'sulfated cholecystokinin octapeptide'],
   'DY(SO3H)MGWMDF(NH2)', 'PubChem structure (CID 9833444) decomposed', 'High'),
 'atosiban': (['atosiban', 'tractocile', 'atosiban acetate'],
   '(Mpa)y(Et)ITNCP(Orn)G(NH2)', 'PubChem structure (CID 5311010) decomposed', 'High'),
 'pentagastrin': (['pentagastrin', 'peptavlon'], '(Boc)(bAla)WMDF(NH2)',
   'PubChem structure (CID 9853654) decomposed; N-terminal Boc-beta-alanine', 'Medium'),
 'avexitide': (['avexitide', 'exendin 9-39', 'exendin (9-39)', 'exendin-9-39', 'exendin 9-39 amide',
   'exendin(9-39)amide', 'exendin (9-39) amide', '9-39'],
   'DLSKQMEEEAVRLFIEWLKNGGPSSGAPPPS(NH2)',
   'PubChem structure of exendin(9-39) (CID 16198321) decomposed', 'High'),
 'glatiramer acetate': (['glatiramer', 'glatiramer acetate', 'copaxone', 'glatopa',
   'copolymer 1', 'cop-1', 'cop 1', 'glatiramoids'], '',
   'random copolymer of L-Ala, L-Glu, L-Lys, L-Tyr - no single defined sequence', 'n/a'),
 'pentixafor': (['pentixafor', 'ga-68 pentixafor', '68ga-pentixafor', 'cpcr4-2'],
   'R(2Nal)Gy', 'PubChem structure (CID 54575322) partial decomposition; cyclic pentapeptide '
   'with a non-proteinogenic residue, chelator omitted', 'Low'),
}
