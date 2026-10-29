# Sequences stated verbatim in the trial's own ClinicalTrials.gov record (methodology step 1a).
# key: NCT -> (sequence, evidence)
EXPLICIT = {
 'NCT00573495': ('YLFFYRKSV|YLQVNSLQTV',
   'CTG detailed description: "The two heteroclitic peptides are R572Y (YLFFYRKSV) and D988Y (YLQVNSLQTV)"'),
 'NCT00672152': ('RMFPNAPYL|CMTWNQMNL|QARMFPNAPYLPSCL|LKGVAAGSSSSVKWT',
   'CTG arm description lists WT1 peptides #1-#4 with sequences'),
 'NCT00694551': ('VLAGGFFLLYRHVIYAPSSHNKYA|LQLLKQSSRRLEHTFMFLRNFSL',
   'CTG description: PSMA27-35-PSMA687-701 (VLAGGFFLLYRHVIYAPSSHNKYA) and TARP13-35 (LQLLKQSSRRLEHTFMFLRNFSL)'),
 'NCT00856154': ('RLLNAWVKV|FLGKIWPV|NIWATHACV|KLGKAGYVV|ALVEMGHHV|GLADQLIHL|SLVKHHMYV|'
   'KRWIILGLNKIVRMY|VWGIKQLQARVLAVERYLKD|AK(Cha)VAAWTLKAAA',
   'CTG intervention description lists all 10 peptides pulsed on the dendritic cells '
   '(peptide 10 = PADRE, AKXVAAWTLKAAA, X = cyclohexylalanine)'),
 'NCT02559115': ('fQWAVGH(Sta)L(NH2)',
   'CTG brief summary: "68Ga-RM2 stands for Galium-68 labeled DOTA-4-amino-1-carboxymethylpiperidine-'
   'D-Phe-Gln-Trp-Ala-Val-Gly-His-Sta-Leu-NH2"; chelator omitted, Sta = statine'),
 'NCT02750995': ('PGVLLKEFTVSGNILTIRLTAADHR|LQSLLQHLIGLSNLTHVLYPVPLES|'
   'YLEYRQVPGSDPACYEFLWGPRALV|SQLECMTWNQMNLGATLKGVAAGSSSSVK',
   'CTG description lists the four 25-mer peptides (NY-ESO-1 119-143, PRAME 423-447, MAGE-A3 255-279, WT1)'),
 'NCT04051307': ('FMTYWHLLNAFTVTVPKDL|ISAKDIVYIGLRDVDPGEHYILKTLGIKYFSMTEVDRL',
   'CTG intervention names: "PD-L1 Long(19-27) Peptide sequence: FMTYWHLLNAFTVTVPKDL" and '
   '"ArgLong2(169-206) Peptide sequence ISAKDIVYIGLRDVDPGEHYILKTLGIKYFSMTEVDRL"'),
 'NCT03643068': ('QRHKPRE|KSPNPRF',
   'CTG description of the KSP/QRH heptapeptide dimer: Gln-Arg-His-Lys-Pro-Arg-Glu and Lys-Ser-Pro-Asn-Pro-Arg-Phe'),
 'NCT03148119': ('QRHKPREGGGSK',
   'CTG description: "Gln-Arg-His-Lys-Pro-Arg-Glu-Gly-Gly-Gly-Ser-Lys(Cy5)-NH2 ... QRHKPRE-GGGSK-(Cy5)-NH2"; '
   'Cy5 fluorophore omitted'),
 'NCT02156557': ('KCCFPAQGGGSK',
   'CTG intervention description: "KCCFPAQ-GGGSK-(5-FITC)-NH2"; FITC fluorophore omitted'),
 'NCT01391208': ('ASYNYDAGGGSK',
   'CTG intervention description: "GI heptapeptide, Linear, 7 amino acid peptide sequence ASYNYDA with a '
   '5-FITC tag", Ala1-Ser2-Tyr3-Asn4-Tyr5-Asp6-Ala7 plus GGGSK linker'),
 'NCT01630798': ('ASYNYDAGGGSK',
   'CTG intervention description: "GI heptapeptide, Linear, 7 amino acid peptide sequence ASYNYDA with a 5-FITC tag"'),
 'NCT00683085': ('TLFWLLLTL',
   'CTG intervention description: "VEGFR1-derived HLA-A*02:01-restricted peptide (VEGFR1-A02-770; TLFWLLLTL)"'),
 'NCT00683358': ('SYGVLLWEI',
   'CTG intervention description: "HLA-A*2402-restricted VEGFR1-derived peptide (VEGFR1-A24-1084; SYGVLLWEI)"'),
 'NCT01580696': ('EIWTHSTKV|EIWTFSTKV',
   'CTG arm descriptions: "E39 peptide (FBP, 191-199, EIWTHSTKV)" and "J65 peptide (an attenuated peptide of E39, EIWTFSTKV)"'),
 'NCT02019524': ('EIWTHSYKV|EIWTFSTKV',
   'CTG arm descriptions: "E39 peptide (EIWTHSYKV, Folate Binding Protein, 191-199)" and "J65 peptide (EIWTFSTKV, Folate Binding Protein)"'),
 'NCT01748747': ('ILGLNKIV',
   'CTG intervention name: "Gag:267-274 peptide vaccine ILGLNKIV"'),
 'NCT01570036': ('KIFGSLAFL',
   'CTG intervention description: "NeuVax vaccine E75 peptide (KIFGSLAFL, HER2/neu, 369-377)"'),
 'NCT06741072': ('RAKFKQLL',
   'CTG brief summary: "Vaccines made from synthetic peptide (RAKFKQLL) derived from the BZLF1 protein"'),
 'NCT04402957': ('LSALTPSPSWLKYKAL',
   'CTG intervention description: "LSALT, a peptide drug with the sequence NH3-LSALTPSPSWLKYKAL-COOH"'),
 'NCT05879432': ('LSALTPSPSWLKYKAL',
   'CTG intervention description: "LSALT, a peptide drug with the sequence NH3-LSALTPSPSWLKYKAL-COOH"'),
}
# NCTs where a sequence-looking token in the record must NOT be taken as a sequence
REJECT = {
 'NCT04546841': 'SYFPEITHI is the name of an MHC-ligand database, not the vaccine sequence; '
   'CoVac-1 component peptides are not listed in the record',
 'NCT07316361': 'VLINIVAL is a trademark in the study title, not a sequence; personalised neoantigen vaccine',
 'NCT04842513': 'GDPKHPKSF is the XS15 (Pam3Cys-GDPKHPKSF) immunomodulator co-administered as an adjuvant, '
   'not the vaccine peptide; the multipeptide vaccine components are not listed',
 'NCT03359239': 'TECENTRIQ is the atezolizumab trade name in the record, not a sequence',
 'NCT04015700': 'CELLECTRA is the electroporation device name, not a sequence',
 'NCT06195618': 'PACIENTES is a Spanish word in the record, not a sequence',
}
