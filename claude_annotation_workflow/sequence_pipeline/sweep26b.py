import sys, json, re, collections
sys.path.insert(0,'/projects/btl/ezhang/final_ctg_lookup/ctg_api_out/sequence_pipeline')
import cfg
byname=json.load(open(cfg.WORK+'/sweep26_byname.json'))
# peptide-suggestive surface forms (methodology step 1d naming patterns + explicit peptide words)
TIDE=re.compile(r'(tide|relin|pressin|tocin|glutide|cortin|motide|pepimut|ermin|actide|arelix|'
                r'relix|tirelin|morelin|bersat|mustine)\b')
PEPW=re.compile(r'\b(peptide|peptides|polypeptide|epitope|oligopeptide|dipeptide|tripeptide|'
                r'tetrapeptide|peptidomimetic|peptid)\b')
CODE=re.compile(r'^[a-z]{2,6}[- ]?\d{2,6}[a-z]?$')
cand=collections.Counter(); kind={}
for t,ncts in byname.items():
    w=t.split(' ')
    hit=None
    if PEPW.search(t): hit='peptide-word'
    elif TIDE.search(t): hit='tide-suffix'
    elif len(w)<=2 and any(CODE.match(x) for x in w): hit='research-code'
    if hit: cand[t]=len(ncts); kind[t]=hit
print('peptide-suggestive unmatched names:',len(cand))
for t,c in cand.most_common():
    if c<2 and kind[t]=='research-code': continue
    print('%4d  %-13s %s' % (c, kind[t], t[:88]))
