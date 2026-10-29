#!/usr/bin/env python3
"""Rebuild drug_routes.tsv / trial_routes.tsv from any delivery-mode output CSV.

Methodology section 10.1: every Evidence string that used the drug-level or
trial-level route table wrote the retrieved evidence phrase and source into
itself verbatim, so both tables recover losslessly from an output CSV.
Usage: recover_routes.py <in.csv> <drug_routes.tsv> <trial_routes.tsv>
"""
import csv,re,sys,collections

DRUG=re.compile(r'drug-level route(?: for (?P<drug>[^:]+?))?: "(?P<phrase>[^"]*)" \((?P<src>[^)]*)\)')
TRIAL=re.compile(r'trial-level (?:verified )?route: "(?P<phrase>[^"]*)" \((?P<src>[^)]*)\)')

def main(inp,dout,tout):
    drug={}; trial={}
    seen=collections.Counter()
    for r in csv.DictReader(open(inp,newline='')):
        ev=r['Evidence']; mode=r['Delivery Mode']; conf=r['Confidence']
        # the label the table itself carried, before per-trial indication rules
        m=DRUG.search(ev)
        if m:
            d=(m.group('drug') or '').strip().lower()
            if not d:  # fell back to a class key; take the leading peptide name
                d=ev.split(' | ')[0].replace('peptide drug(s):','').split('|')[0].strip().lower()
            phrase=m.group('phrase'); src=m.group('src')
            multi=re.search(r'\[(?:multi-route|predominant)[^\]]*\]',ev)
            lab=mode
            if 'Multiple:' in ev:
                mm=re.search(r'Multiple:[^\s\]"]+',ev); lab=mm.group(0) if mm else mode
            q='v' if conf in ('High','Medium') else 'i'
            if 'inferred from class' in ev or 'route not retrieved' in ev: q='i'
            prev=drug.get(d)
            seen[d]+=1
            if prev is None or (prev[3]=='i' and q=='v'):
                drug[d]=(d,lab,phrase,src,q)
        m=TRIAL.search(ev)
        if m:
            trial[r['NCT Number']]=(r['NCT Number'],mode,m.group('phrase'),m.group('src'),
                                    'v' if conf in ('High','Medium') else 'i')
    with open(dout,'w') as f:
        f.write('# drug\tmode\tevidence phrase\tsource\tquality   (recovered from %s)\n'%inp)
        for d in sorted(drug):
            _,lab,phrase,src,q=drug[d]
            f.write('\t'.join([d,lab,phrase,src,q])+'\n')
    with open(tout,'w') as f:
        f.write('# nct\tmode\tevidence phrase\tsource\tquality   (recovered from %s)\n'%inp)
        for n in sorted(trial):
            _,lab,phrase,src,q=trial[n]
            f.write('\t'.join([n,lab,phrase,src,q])+'\n')
    print('recovered %d drugs, %d trial-level rows'%(len(drug),len(trial)))
    print('top by trials using the table:',seen.most_common(6))

if __name__=='__main__':
    main(*sys.argv[1:4])
