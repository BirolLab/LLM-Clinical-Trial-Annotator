import sys, json, re, csv, collections
sys.path.insert(0,'/projects/btl/ezhang/final_ctg_lookup/ctg_api_out/sequence_pipeline')
import cfg
from curated import GENERIC
M=json.load(open(cfg.WORK+'/match2.json'))
ctg={}
for l in open(cfg.WORK+'/ctg.jsonl'):
    d=json.loads(l); ctg[d['nct']]=d
# the family name is used at class level: "<family> receptor agonist/antagonist/blocker/
# inhibitor/analogue", "anti-<family>", "<family> receptor blockade"
CLASS=re.compile(r'(?i)(receptor[- ](agonist|antagonist|blocker|blockade|inhibit|modulat)|'
                 r'[- ](antagonist|antagonism|blockade|blocker|inhibitor|inhibition)\b|'
                 r'\banti[- ])')
hits=collections.Counter(); ex=collections.defaultdict(list)
for nct,f in M.items():
    d=ctg.get(nct,{})
    title=((d.get('bt') or '')+' '+(d.get('ot') or ''))
    for k,info in f.items():
        if k not in GENERIC: continue
        if 'intervention' in info['where']: continue
        # is the family alias followed by class-level wording in the title?
        for al in info['alias']:
            m=re.search(r'(?i)'+re.escape(al)+r'(.{0,30})', title)
            if m and CLASS.search(al+m.group(1)):
                hits[k]+=1; ex[k].append((nct,title[:110])); break
print('generic keys matched only in title/search terms, at class level:')
for k,c in hits.most_common():
    print('%4d  %s' % (c,k))
    for nct,t in ex[k][:3]: print('        %s %s' % (nct,t))
