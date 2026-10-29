# Step 2b.5: epitopes named by protein + residue range in the trial's own record.
import sys, json, re, csv, collections
sys.path.insert(0,'/projects/btl/ezhang/final_ctg_lookup/ctg_api_out/sequence_pipeline')
import cfg
csv.field_size_limit(10**9)
R={r['NCT Number']:r for r in csv.DictReader(open(cfg.WORK+'/trial.csv'))}
RX=re.compile(r'(?i)([A-Za-z0-9][A-Za-z0-9\-/\. ]{1,28}?)\s*[\(\[:]?\s*(\d{1,4})\s*[-–]\s*(\d{1,4})\s*[\)\]]?')
PEP=re.compile(r'(?i)peptide|epitope|vaccine|antigen')
out=collections.defaultdict(set)
for l in open(cfg.WORK+'/ctg.jsonl'):
    d=json.loads(l)
    if R.get(d['nct'],{}).get('Sequence'): continue
    for iv in d.get('ivs',[]):
        for nm in [iv.get('name','')]+(iv.get('otherNames') or []):
            if not nm or not PEP.search(nm): continue
            for m in RX.finditer(nm):
                prot,a,b=m.group(1).strip(),int(m.group(2)),int(m.group(3))
                if not (0<a<b<=3000 and 4<=b-a+1<=60): continue
                out[(prot.lower(),a,b)].add(d['nct'])
print('protein+range epitope candidates:',len(out))
for (p,a,b),n in sorted(out.items(), key=lambda x:-len(x[1])):
    if len(n)<1: continue
    print('%3d  %-34s %d-%d   %s' % (len(n), p[:34], a, b, ' '.join(sorted(n)[:5])))
