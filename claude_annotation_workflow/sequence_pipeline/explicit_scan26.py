# Methodology step 1a: find runs of single-letter amino-acid code, and three-letter
# residue chains, stated in the trial's OWN ClinicalTrials.gov record.
import sys, json, re, collections
sys.path.insert(0,'/projects/btl/ezhang/final_ctg_lookup/ctg_api_out/sequence_pipeline')
import cfg
AA1 = r'[ACDEFGHIKLMNPQRSTVWY]'
RUN = re.compile(r'(?<![A-Za-z0-9])(%s{7,})(?![A-Za-z0-9])' % AA1)
TLC = ('Ala|Arg|Asn|Asp|Cys|Gln|Glu|Gly|His|Ile|Leu|Lys|Met|Phe|Pro|Ser|Thr|Trp|Tyr|Val|'
       'Aib|Sar|Orn|Cit|Nle|Nal|pGlu|Hyp|Abu|Dab|Sta|Cha|Pal|Cpa|Aph|Har|Thi|Tic|Oic|Mpa|Bua')
TLCRX = re.compile(r'((?:(?:D-|L-|d-|l-)?(?:%s)[- ]){3,}(?:(?:D-|L-|d-|l-)?(?:%s)))' % (TLC, TLC))
# words that look like a sequence but are not
CONTEXT = re.compile(r'(?i)sequence|peptide|epitope|amino acid|residue|aa\b|analog|vaccine|'
                     r'nh2|cooh|n-term|c-term|h-|-oh')
recs = collections.OrderedDict()
for l in open(cfg.WORK + '/ctg.jsonl'):
    d = json.loads(l)
    fields = []
    fields.append(('title', (d.get('bt') or '') + ' || ' + (d.get('ot') or '')))
    fields.append(('briefSummary', d.get('bs') or ''))
    fields.append(('detailedDescription', d.get('dd') or ''))
    for iv in d.get('ivs', []):
        fields.append(('intervention:' + (iv.get('name') or '')[:40],
                       (iv.get('name') or '') + ' || ' + ' || '.join(iv.get('otherNames') or [])
                       + ' || ' + (iv.get('description') or '')))
    for a in d.get('arms', []):
        fields.append(('arm:' + (a.get('label') or '')[:30], (a.get('description') or '')))
    hits = []
    for tag, txt in fields:
        if not txt: continue
        for m in RUN.finditer(txt):
            s = m.group(1)
            lo = max(0, m.start()-90); hi = min(len(txt), m.end()+90)
            ctx = txt[lo:hi].replace('\n', ' ')
            hits.append(('1letter', s, tag, ctx))
        for m in TLCRX.finditer(txt):
            lo = max(0, m.start()-90); hi = min(len(txt), m.end()+90)
            hits.append(('3letter', m.group(1), tag, txt[lo:hi].replace('\n',' ')))
    if hits: recs[d['nct']] = hits
json.dump(recs, open(cfg.WORK + '/explicit_scan.json', 'w'), indent=0)
print('trials with a sequence-looking token:', len(recs))
print('total hits:', sum(len(v) for v in recs.values()))
