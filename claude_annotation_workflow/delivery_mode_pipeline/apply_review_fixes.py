#!/usr/bin/env python3
"""Pass 13: corrections from the section 6 stratified review of rb_pass12.

Error class: a route word belonging to a co-administered non-peptide agent (or
to a meal/OGTT, a trial acronym, or embryo implantation) was attributed to the
peptide, because the section 10.2 nearest-drug-wins guard could not see the
rival drug. Each correction is re-evidenced from the trial's own record where it
states the peptide's route, else from the retrieved drug-level route table.
"""
import csv,json,re,sys,collections

import os
# Was hardcoded to a different dataset directory, so the corrections were
# re-evidenced from *another* run's drug_routes.tsv and ctg_raw.jsonl.
DATA=os.environ.get('DM_DATA','.')
WORK=os.environ.get('DM_WORK', os.path.join(DATA,'work'))
PIPE=os.path.dirname(os.path.abspath(__file__))
INJ='injection/infusion'
R={
 'oad':'route word belongs to a co-administered oral antidiabetic, an OGTT or a meal, not the peptide',
 'endo':'route word belongs to a co-administered oral endocrine/antiandrogen agent or an add-back patch, not the peptide',
 'pi':'route word belongs to a co-administered oral agent (melphalan, prednisone, dexamethasone, thalidomide), not the peptide',
 'ms':'route word belongs to a co-administered oral agent; the peptide itself is injected',
 'rec':'the CTG record states an oral route that does not exist for this drug (record error)',
 'emb':'"implant" refers to embryo implantation, not an implanted dosage form',
 'acr':'"PATCH" is the trial acronym, not a dosage form',
 'endo2':'route word belongs to a co-administered oral antiandrogen or a progesterone/estradiol comparator, not the peptide',
 'chemo':'route word belongs to the co-administered chemotherapy regimen described in the same arm, not to the colony-stimulating factor',
}
C={}
def add(tag,ids):
    for n in ids.split(): C[n]=(INJ,R[tag])
add('oad','''NCT00097877 NCT00286429 NCT00311818 NCT00347100 NCT00383877 NCT00469833 NCT00562133
NCT00604396 NCT00641407 NCT00653302 NCT00667732 NCT00757588 NCT00762190 NCT00770445 NCT00770640
NCT00791895 NCT00849576 NCT00862875 NCT00975533 NCT01076842 NCT01135992 NCT01832935 NCT02189395
NCT03665350 NCT01677104 NCT02483299 NCT03034941 NCT06732245 NCT06847399 NCT06515418 NCT01911468''')
add('endo','''NCT00053911 NCT00067015 NCT00532272 NCT00826839 NCT01353846 NCT01642186 NCT01763541
NCT02115282 NCT02603679 NCT02903368 NCT03839823 NCT04671966 NCT05439499 NCT06145308 NCT06922318
NCT07319429''')
add('endo2','NCT04025372 NCT05143723')
add('pi','NCT00573391 NCT00789256 NCT01063179 NCT01208766 NCT01788020 NCT01813227')
add('ms','NCT00203099 NCT00451204 NCT01404117')
add('rec','NCT01240941 NCT00102934')
# run 7 (14.2): the same error class on recombinant protein biologics, found by
# the generalized detector over every non-injection High/Medium row
add('chemo','NCT00673179 NCT03943901')
C['NCT00542126']=(INJ,R['emb']); C['NCT06624956']=(INJ,R['acr'])
C['NCT02944110']=('Unknown','the administered agent is the small-molecule glucagon receptor antagonist '
  'LY2409021, given orally; glucagon itself is the endogenous hormone under study, not given as a drug')

routes={}
for line in open(os.path.join(PIPE,'drug_routes.tsv')):
    if line.startswith('#'): continue
    p=line.rstrip('\n').split('\t')
    if len(p)>=5: routes[p[0]]=p

INJ_RE=re.compile(r'(sub\s?-?cutaneous\w*|sub[\s-]?cut\b|intra\s?-?muscular\w*|intra\s?-?venous\w*'
                  r'|\bIM\b|\bSC\b|\bs\.c\.|\bi\.v\.|\bIV\b|injections?|injected|infusions?|infused'
                  r'|depot|subcutaneous implant)',re.I)
rec={}
for line in open(os.path.join(WORK,'ctg_raw.jsonl')):
    d=json.loads(line)
    if d.get('nct') in C: rec[d['nct']]=d


TIERS=('intervention name','intervention description','description of arm','study text naming',
       'drug-level route','trial-level','brief title','official title','context class',
       'other names','abstract','generic study description','peptide is measured','no retrieved',
       'intervention "','the administered agent')
def split_head(ev):
    """Return (head, [drug names], prior-evidence) -- the drug list is every
    ' | '-separated segment before the first evidence-tier marker."""
    segs=ev.split(' | ')
    drugs=[]; i=0
    for i,sg in enumerate(segs):
        c=sg.replace('peptide drug(s):','').strip()
        if any(k in sg.lower() for k in TIERS): break
        drugs.append(c)
    else:
        i=len(segs)
    head='peptide drug(s): '+' | '.join(drugs)
    prior=re.sub(r'\s*\[.*$','',' | '.join(segs[i:]))[:110]
    return head,[d for d in drugs if d],prior

SYN={'gnrh':('gnrh','gonadotropin','lhrh','luteinising','luteinizing'),
     'analogue':(),'analog':(),'agonist':(),'antagonist':(),'hormone':(),
     'vaccine':(),'peptide':(),'product':(),'unidentified':(),'none':(),'identified':()}
STOP={'insulin','unspecified','acetate','human','regular','analogue','analog','agonist',
      'antagonist','hormone','vaccine','peptide','product','unidentified','none','identified'}
def clean(t):
    """Collapse whitespace so no Evidence cell carries an embedded newline."""
    return re.sub(r'\s+',' ',(t or '').replace('\\_',' ')).strip()

def toks(drug):
    drug=re.sub(r'\(.*?\)','',drug).lower()
    out=[]
    for t in re.findall(r'[a-z]{4,}',drug):
        if t in SYN and SYN[t]: out.extend(SYN[t]); continue
        if t in STOP or len(t)<5: continue
        out.append(t)
    return out

def record_quote(n,drugs):
    """An injection route stated in the peptide's OWN intervention text."""
    d=rec.get(n) or {}
    for iv in (d.get('interventions') or []):
        nm=iv.get('name') or ''; ds=iv.get('description') or ''
        blob=f'{nm} || {ds}'; low=blob.lower()
        matched=False
        for dr in drugs:
            tk=toks(dr)
            if tk and any(t in low for t in tk): matched=True; break
        if not matched: continue
        m=INJ_RE.search(blob)
        if m:
            s=max(0,m.start()-70); e=min(len(blob),m.end()+70)
            return ('intervention "%s" states the peptide\'s route: "%s"'%(clean(nm)[:50],clean(blob[s:e])),'High')
    # tier 6: a summary/detail sentence that names the peptide and its route
    for field in ('summary','detail','brief','official'):
        txt=d.get(field) or ''
        for sent in re.split(r'(?<=[.;])\s+',txt):
            low=sent.lower()
            if not INJ_RE.search(sent): continue
            for dr in drugs:
                tk=toks(dr)
                if tk and any(t in low for t in tk):
                    return ('study text naming the peptide: "%s"'%clean(sent)[:150],'Medium')
    return None

SRC=sys.argv[1] if len(sys.argv)>1 else os.path.join(WORK,'rb_pass12.csv')
rows=list(csv.DictReader(open(SRC,newline='')))
log=[]
for r in rows:
    n=r['NCT Number']
    if n not in C: continue
    new,reason=C[n]; old=r['Delivery Mode']
    # The generic pipeline reproduces most of these on its own now; only the
    # rows it still gets wrong are re-evidenced here.
    if old==new: continue
    ev=r['Evidence']
    head,drugs,prior=split_head(ev)
    prior=clean(prior)
    if new=='Unknown':
        r.update({'Delivery Mode':'Unknown','Confidence':'Unknown',
          'Evidence':f'{head} | {reason}; no route to report [corrected on review: was {old}, from {prior}]'})
        log.append((n,old,'Unknown','Unknown','adjudicated')); continue
    q=record_quote(n,drugs)
    if q:
        qt,qc=q
        r.update({'Delivery Mode':new,'Confidence':qc,
          'Evidence':f'{head} | {qt} [corrected on review: was {old}; {reason}]'})
        log.append((n,old,new,qc,'record')); continue
    ent=None
    for dr in drugs:
        e=routes.get(dr)
        if e and e[1]==INJ: ent=e; break
    if ent:
        conf='Medium' if ent[4]=='v' else 'Low'
        r.update({'Delivery Mode':new,'Confidence':conf,
          'Evidence':f'{head} | drug-level route for {ent[0]}: "{ent[2]}" ({ent[3]}) '
                     f'[corrected on review: was {old}; {reason}; superseded wording: {prior}]'})
        log.append((n,old,new,conf,'drug-table'))
    else:
        r.update({'Delivery Mode':new,'Confidence':'Low',
          'Evidence':f'{head} | no retrieved drug-level route; {reason} '
                     f'[corrected on review: was {old}; superseded wording: {prior}]'})
        log.append((n,old,new,'Low','unsourced'))

out=sys.argv[2] if len(sys.argv)>2 else os.path.join(WORK,'rb_pass13.csv')
w=csv.DictWriter(open(out,'w',newline=''),fieldnames=['NCT Number','Delivery Mode','Confidence','Evidence'])
w.writeheader(); w.writerows(rows)
print('corrected',len(log),'of',len(C),'| basis:',dict(collections.Counter(l[4] for l in log)))
print('conf:',dict(collections.Counter(l[3] for l in log)))
by_nct={r['NCT Number']:r for r in rows}
absent=[n for n in C if n not in by_nct]
if absent:
    print('correction ids no longer in the trial set:',len(absent))
bad={n for n,(lab,_) in C.items() if n in by_nct and by_nct[n]['Delivery Mode']!=lab}
assert not bad, bad
