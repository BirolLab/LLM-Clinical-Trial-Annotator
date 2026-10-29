import csv, re, sys, collections
p = sys.argv[1]
R = list(csv.DictReader(open(p)))
AA = set('ACDEFGHIKLMNPQRSTVWY')
bad = collections.defaultdict(list)
conf = collections.Counter()
for r in R:
    s = r['Sequence']; conf[r['Confidence']] += 1
    if not s:
        if r['Confidence'] != 'n/a': bad['empty but confidence set'].append(r['NCT Number'])
        continue
    if r['Confidence'] == 'n/a': bad['sequence but confidence n/a'].append(r['NCT Number'])
    if s.count('(') != s.count(')'): bad['unbalanced brackets'].append(r['NCT Number'])
    if re.search(r'[\[\]{}]', s): bad['square/curly brackets'].append(r['NCT Number'])
    for part in s.split('|'):
        if not part.strip(): bad['empty peptide segment'].append(r['NCT Number'])
        core = re.sub(r'\([^)]*\)', '', part)
        for ch in core:
            if ch in '/': continue
            if ch.isupper() and (ch in AA or ch == 'X'): continue
            if ch.islower() and ch.upper() in AA: continue
            bad['unexpected char %r' % ch].append(r['NCT Number'])
print('rows', len(R), dict(conf))
print('non-empty', sum(1 for r in R if r['Sequence']),
      '| distinct sequences', len({r['Sequence'] for r in R if r['Sequence']}))
print('rows missing Evidence', sum(1 for r in R if not r['Evidence']))
ids = [r['NCT Number'] for r in R]
print('duplicate NCTs', len(ids) - len(set(ids)))
for k, v in sorted(bad.items()): print('  !!', k, len(v), v[:5])
if not bad: print('  notation checks: clean')
