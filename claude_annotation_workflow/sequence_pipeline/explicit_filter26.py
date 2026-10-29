import sys, json, re, collections
sys.path.insert(0,'/projects/btl/ezhang/final_ctg_lookup/ctg_api_out/sequence_pipeline')
import cfg
R = json.load(open(cfg.WORK + '/explicit_scan.json'))
# Step 1a: accept a hit only when it sits next to the drug name or the words
# peptide / sequence / epitope.  Reject brand names, gene symbols, database names.
CTX = re.compile(r'(?i)\b(sequence|peptide|epitope|amino[- ]acid|residues?|'
                 r'nh2|cooh|amide|acetyl|immunogen|antigenic)\b')
REJECT_TOK = set('''SYFPEITHI ADCETRIS TECENTRIQ VLINIVAL CELLECTRA PACIENTES PERJETA HERCEPTIN
KADCYLA GARDASIL CERVARIX SPIKEVAX COMIRNATY TRELSTAR LUPRON ELIGARD FIRMAGON SANDOSTATIN
SOMATULINE SIGNIFOR LANTUS LEVEMIR TRESIBA HUMALOG NOVOLOG APIDRA VICTOZA SAXENDA OZEMPIC
WEGOVY TRULICITY BYDUREON BYETTA MOUNJARO ZEPBOUND SYMLIN FORTEO TYMLOS NATPARA MIACALCIN
FORTICAL PITRESSIN VASOSTRICT DDAVP STIMATE CETROTIDE GANIRELIX PLENAXIS SUPPRELIN VANTAS
PROPECIA PRIALT INTEGRILIN ANGIOMAX ACTHAR CORTROSYN SINCALIDE KINEVAC SECREFLO CHIRHOSTIM
GATTEX REVESTIVE NATPAR ZOMETA ARANESP EPOGEN PROCRIT NEUPOGEN NEULASTA LEUKINE PROLEUKIN
ENBREL ORENCIA HUMIRA REMICADE RITUXAN AVASTIN KEYTRUDA OPDIVO YERVOY TECARTUS KYMRIAH
PLACEBO PATIENTS PARTICIPANTS DIAGNOSIS TREATMENT SCREENING RANDOMISED RANDOMIZED
STANDARD CLINICAL HISTOLOGY PATHOLOGY BASELINE WITHDRAWAL BIOPSY SPANISH ENGLISH
PRIMARY SECONDARY TERTIARY CRITERIA PROTOCOL SPECIMEN ANALYSIS INFUSION INJECTION'''.split())
keep = collections.OrderedDict()
for nct, hits in R.items():
    kept = []
    for kind, s, tag, ctx in hits:
        if kind == '1letter':
            if s in REJECT_TOK: continue
            if len(s) < 8: continue
            if not CTX.search(ctx): continue
            # a run that is an ordinary English/acronym word is rejected
            if re.search(r'(?i)\b%s\b' % re.escape(s), ctx) and s.lower() in ctx and not s.isupper():
                pass
        kept.append([kind, s, tag, ctx])
    if kept: keep[nct] = kept
json.dump(keep, open(cfg.WORK + '/explicit_kept.json','w'), indent=0)
print('trials after context filter:', len(keep), '| hits:', sum(len(v) for v in keep.values()))
