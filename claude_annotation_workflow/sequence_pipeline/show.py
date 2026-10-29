import sys, json
sys.path.insert(0,'/projects/btl/ezhang/final_ctg_lookup/ctg_api_out/sequence_pipeline')
import cfg
want=set(sys.argv[1:])
L=int(__import__('os').environ.get('L','700'))
for l in open(cfg.WORK+'/ctg.jsonl'):
    d=json.loads(l)
    if d['nct'] not in want: continue
    print('='*100); print(d['nct'], '|', (d.get('bt') or '')[:150])
    for a in d.get('arms',[]):
        print('  ARM[%s] %s :: %s' % (a.get('type',''), (a.get('label') or '')[:40], (a.get('description') or '')[:200]))
    for iv in d.get('ivs',[]):
        print('  IV[%s] %s' % (iv.get('type',''), (iv.get('name') or '')[:80]))
        if iv.get('otherNames'): print('      other: %s' % ' ; '.join(iv['otherNames'])[:250])
        if iv.get('description'): print('      desc: %s' % (iv['description'] or '')[:L])
