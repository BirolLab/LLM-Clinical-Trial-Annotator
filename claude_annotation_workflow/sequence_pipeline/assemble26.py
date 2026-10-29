import json, re, csv, sys, collections
sys.path.insert(0,'/projects/btl/ezhang/final_ctg_lookup/ctg_api_out/sequence_pipeline')
import cfg
from curated import EXCLUDE, GENERIC, SUPP, OVERRIDE, GENERIC_ALIAS
from explicit import EXPLICIT, REJECT
from additions import NEW_EXCLUDE
from additions2 import NEW_EXCLUDE2
from additions3 import EXPLICIT3, NEW_EXCLUDE3
EXCLUDE = dict(EXCLUDE); EXCLUDE.update(NEW_EXCLUDE); EXCLUDE.update(NEW_EXCLUDE2)
EXCLUDE.update({k: why for k, (als, why) in NEW_EXCLUDE3.items()})

D = json.load(open(cfg.WORK+'/drugs.json')); drugs = D['drugs']
M = json.load(open(cfg.WORK+'/match2.json'))
ctg = {}
for l in open(cfg.WORK+'/ctg.jsonl'):
    d = json.loads(l); ctg[d['nct']] = d
scope = [l.strip() for l in open(cfg.NCTS) if l.strip()]
bundle = {}
for l in open(cfg.WORK+'/bundle_parsed.jsonl'):
    d = json.loads(l); bundle[d['nct']] = d

BAD = re.compile(r'\{|\(N:|\(C:')
def _core(s):
    s = re.sub(r'\([^)]*\)|\{[^}]*\}', '', s)
    return re.sub(r'[^A-Za-z]', '', s).upper()
def pick_seq(k):
    """-> (seq, source, confidence, note) or None"""
    e = drugs.get(k)
    if not e: return None
    if 'override' in e:
        o = e['override']; return o['seq'], o['src'], o['conf'], o.get('note', '')
    if 'supp' in e:
        s = e['supp']
        return (s['seq'] or None) if s['seq'] else None, s['src'], s['conf'], ''
    c = e.get('chembl'); g = e.get('gsrs')
    cclean = bool(c and c['seq'] and c['meta']['nchain'] == 1 and c['meta']['cov'] >= 0.9
                  and not c['meta']['unk'] and not BAD.search(c['seq']))
    # a ChEMBL walk that is a rotation of the GSRS sequence means the backbone walk could not
    # find the N-terminus (ring-order ambiguity): the GSRS record then decides the order
    if cclean and g and g['seq']:
        cg, cc = _core(g['seq']), _core(c['seq'])
        if cg and cc and len(cg) == len(cc) and cg != cc and cc in (cg + cg):
            cclean = False
    gclean = bool(g and g['seq'] and not BAD.search(g['seq']))
    gn = g['meta']['tot'] if g else 0
    if cclean and c['meta']['nres'] <= 60:
        return c['seq'], 'ChEMBL structure %s (bundle by_source/chembl.jsonl) decomposed into residues' % c['meta']['id'], 'High', ''
    if gclean:
        note = ''
        if g['meta']['unmapped']: note = 'GSRS modification(s) not rendered: ' + '; '.join(g['meta']['unmapped'][:3])
        return g['seq'], 'NCATS GSRS protein record %s (%s) subunit sequence' % (g['name'], g['meta']['unii']), 'High', note
    if cclean:
        return c['seq'], 'ChEMBL structure %s decomposed into residues' % c['meta']['id'], 'Medium', ''
    if c and c['seq'] and not BAD.search(c['seq']) and c['meta']['nchain'] == 1 and c['meta']['cov'] >= 0.8:
        return c['seq'], 'ChEMBL structure %s decomposed into residues (partial)' % c['meta']['id'], 'Low', 'structure only partially resolved'
    return None
def order_chains(seq):
    if '/' not in seq: return seq
    ch = seq.split('/')
    if len(ch) == 2 and 'GIVEQCC' in ch[1] and 'GIVEQCC' not in ch[0]:
        return ch[1] + '/' + ch[0]
    return seq
SEQ_CACHE = {}
for k in drugs:
    v = pick_seq(k)
    if v and v[0]: v = (order_chains(v[0]),) + tuple(v[1:])
    SEQ_CACHE[k] = v

CMPONLY = {'ACTIVE_COMPARATOR', 'PLACEBO_COMPARATOR', 'SHAM_COMPARATOR', 'NO_INTERVENTION', 'OTHER'}
FAMRX = re.compile(r'gonadotrop|luteinizing|lh releasing|lh-rh|gnrh')
CLASSRX = re.compile(r'(?i)(gnrh|lhrh|lh-rh|gonadotrop\w*[-\s]releasing hormone|'
                     r'luteini[sz]ing hormone[-\s]releasing hormone)'
                     r'[\s\-]*(?:\([^)]{0,14}\))?[\s\-]*(a\b|agonist|antagonist|analog)')
CLASSUSE = re.compile(r'(?i)(receptor[- ](agonist|antagonist|blocker|blockade|inhibit|modulat)|'
                      r'[- ](antagonist|antagonism|blockade|blocker|inhibitor|inhibition)\b|'
                      r'\banti[- ])')
# "clamp" has to be the clamp technique: plain /clamp/ also matched surgical phrases such as
# "before aortic cross-declamping" (NCT00987207), which demoted the trial's own study drug.
TESTRX = re.compile(r'(?i)stimulation test|tolerance test|secretin test|challenge test|'
                    r'provocation test|arginine test|diagnostic (test|agent)|'
                    r'(glucose|euglyc\w*|hyperglyc\w*|hyperinsulin\w*|insulin|glycemic)[- ]clamp|'
                    r'clamp (study|studies|technique|procedure|test|method)|clamped')
rows = []
stat = collections.Counter()
for nct in scope:
    d = ctg.get(nct, {})
    armtype_of = {a.get('label', ''): (a.get('type') or '') for a in d.get('arms', [])}
    hits = M.get(nct, {})
    title = ((d.get('bt') or '') + ' ' + (d.get('ot') or '')).lower()
    ev_extra = []
    ivtext = ' '.join((i.get('name', '') + ' ' + (i.get('description') or '')) for i in d.get('ivs', []))
    kept = {}; dropped = []; excl = []; demoted = []
    for k, info in hits.items():
        if k in EXCLUDE:
            excl.append((k, EXCLUDE[k], info)); continue
        arms = set(info['arms']); where = set(info['where'])
        in_title = 'title' in where
        if arms and not (arms & {'EXPERIMENTAL'}) and arms <= CMPONLY and not in_title:
            demoted.append((k, 'comparator / background arm only (%s)' % ','.join(sorted(a for a in arms if a)), info)); continue
        if 'DIAGNOSTIC_TEST' in info['ivtypes'] and not in_title:
            demoted.append((k, 'diagnostic-test agent', info)); continue
        if TESTRX.search(ivtext) and not any(a in title for a in info['alias']):
            demoted.append((k, 'test/clamp/challenge agent', info)); continue
        kept[k] = info
    # step 1c: "gonadotro..." must not produce gonadorelin when a named agent is in the trial,
    # and a class-level mention ("GnRH agonist") does not determine a specific peptide at all
    for k in list(kept):
        if k != 'gonadorelin': continue
        # a family name, or an echo in the search-terms field only, is not a named drug
        if not (all(FAMRX.search(a) for a in kept[k]['alias'])
                or set(kept[k]['where']) == {'search_terms'}): continue
        others = [k2 for k2 in list(kept) + [x[0] for x in demoted]
                  if k2 != k and SEQ_CACHE.get(k2) and SEQ_CACHE[k2][0]]
        if others:
            dropped.append((k, 'family/class name only ("%s"); the named peptide agent %s is also '
                            'identified in the trial (step 1c)'
                            % (kept[k]['alias'][0], ', '.join(sorted(set(others))[:3])), kept[k]))
            del kept[k]
        elif CLASSRX.search(ivtext + ' ' + title):
            dropped.append((k, 'named only at class level (GnRH/LHRH agonist, antagonist or '
                            'analogue); the specific peptide is not determinable', kept[k]))
            del kept[k]
    # Step 1c, generalised from the gonadorelin rule: a generic family term that the trial
    # names only in its title/search terms, and names there at class level ("GLP-1 receptor
    # agonist", "angiotensin-converting enzyme inhibitor", "endothelin receptor blockade"),
    # names the drug's target or class, not an administered peptide.  The specific peptide is
    # then not determinable from the family name, so the family peptide is dropped.
    for k in list(kept):
        if k not in GENERIC or k == 'gonadorelin': continue
        if 'intervention' in kept[k]['where']: continue
        als = kept[k]['alias']
        if not als: continue
        classlevel = True
        for al in als:
            m = re.search(r'(?i)' + re.escape(al) + r'(.{0,30})', title + ' ' + ivtext)
            if not (m and CLASSUSE.search(al + m.group(1))): classlevel = False; break
        if classlevel:
            dropped.append((k, 'generic family term used only at class level in the title/'
                            'search terms ("%s"); it names the target or drug class, not an '
                            'administered peptide, and the specific peptide is not '
                            'determinable (step 1c)' % als[0], kept[k]))
            del kept[k]

    # A drug identified only from inside a hyphen-glued token is weaker evidence: the parent
    # peptide's name sits inside its own derivative's name ("1-deamino-8-D-arginine-vasopressin"
    # is desmopressin, "90Y-DOTA-3-Tyr-octreotide" is edotreotide, "LAPS-exendin-4" is
    # efpeglenatide).  Such a hit yields to any drug the trial names directly, and plain
    # octreotide yields to a DOTA/NOTA-conjugated somatostatin analogue (step 1c, specific
    # beats generic; step 1e, a family name implied by the drug's own mechanism).
    SSTR_ANALOGUE = {'edotreotide', 'oxodotreotide', 'satoreotide trizoxetan',
                     'satoreotide tetraxetan', 'lanreotide', 'veldoreotide'}
    direct = [k2 for k2 in kept if not kept[k2].get('glue')
              and SEQ_CACHE.get(k2) and SEQ_CACHE[k2][0] and k2 not in GENERIC]
    for k in list(kept):
        if not kept[k].get('glue'): continue
        if direct:
            dropped.append((k, 'identified only from inside the glued token naming another drug '
                            '("%s"); the trial names %s directly'
                            % (kept[k]['alias'][0], ', '.join(sorted(direct)[:3])), kept[k]))
            del kept[k]
        elif k == 'octreotide' and any(k2 in SSTR_ANALOGUE for k2 in kept):
            dropped.append((k, 'parent peptide of the conjugated somatostatin analogue named in '
                            'the same token; the analogue itself is annotated', kept[k]))
            del kept[k]

    # Step 1e: the interventions this trial attaches to an EXPERIMENTAL arm, and that are
    # themselves a drug/biological.  A peptide demoted as comparator-or-background does NOT
    # come back when such an intervention exists and is not the peptide itself: the trial then
    # has a non-peptide experimental agent, and the peptide really is background (cyclosporine
    # under a sirolimus or belatacept arm, oxytocin against misoprostol, teriparatide against
    # romosozumab, a GnRH agonist against estradiol or TAK-385).
    expnames = set()
    for iv in d.get('ivs', []):
        if (iv.get('type') or '') not in ('DRUG', 'BIOLOGICAL', 'COMBINATION_PRODUCT'): continue
        if any(armtype_of.get(x) == 'EXPERIMENTAL' for x in (iv.get('armGroupLabels') or [])):
            expnames.add((iv.get('name') or '')[:60])
    # a demoted peptide is still the trial's peptide drug when no experimental peptide remains
    if not any(SEQ_CACHE.get(k) and SEQ_CACHE[k][0] for k in kept):
        for k, why, info in demoted:
            if why.startswith('comparator / background arm only') and expnames and not (
                    set(info.get('ivnames') or []) & expnames):
                dropped.append((k, why + '; the trial\'s experimental arm(s) carry a '
                                'non-peptide drug/biological intervention (%s), so the peptide '
                                'is background, not the investigational agent (step 1e)'
                                % ', '.join(sorted(expnames)[:2]), info))
                continue
            if (k == 'gonadorelin' and all(FAMRX.search(a) for a in info['alias'])
                    and CLASSRX.search(ivtext + ' ' + title)):
                dropped.append((k, 'named only at class level (GnRH/LHRH agonist, antagonist or '
                                'analogue); the specific peptide is not determinable', info))
                continue
            kept[k] = info
            ev_extra.append('%s kept although %s: no experimental peptide intervention in the trial' % (k, why))
        demoted = []
    dropped.extend(demoted)
    # generic suppression
    specific = [k for k in kept if k not in GENERIC and SEQ_CACHE.get(k)]
    if specific:
        for k in list(kept):
            if k in GENERIC:
                dropped.append((k, 'generic family term suppressed (specific agent identified)', kept[k]))
                del kept[k]
    seqs = []; ev = []; confs = []
    noseq = []
    for k in sorted(kept, key=lambda x: -len(max(kept[x]['alias'], key=len))):
        info = kept[k]
        s = SEQ_CACHE.get(k)
        matched = ', '.join(sorted(info['alias'])[:3])
        wh = '/'.join(sorted(info['where']))
        if s and s[0]:
            seq, src, conf, note = s
            if conf == 'High' and 'intervention' not in info['where']:
                conf = 'Medium'
                note = (note + '; ' if note else '') + 'drug named only in the title/search terms, not in an intervention field'
            if conf == 'High' and set(info['alias']) <= GENERIC_ALIAS:
                conf = 'Medium'
                note = (note + '; ' if note else '') + 'matched only by a family name; the clinically marketed form is annotated'
            if seq not in seqs: seqs.append(seq)
            confs.append(conf)
            ev.append('%s [matched "%s" in %s] -> %s; %s; confidence %s%s'
                      % (k, matched, wh, seq, src, conf, ('; ' + note) if note else ''))
        else:
            reason = (s[1] if s else (drugs[k].get('nosequence') or 'no sequence found in GSRS, ChEMBL structure, trial text or curated sources'))
            noseq.append(k)
            ev.append('%s [matched "%s" in %s] -> no sequence annotated; %s' % (k, matched, wh, reason))
    for k, why, info in excl:
        ev.append('%s identified but not annotatable: %s' % (k, why))
    for k, why, info in dropped:
        ev.append('dropped %s: %s' % (k, why))
    ev.extend(ev_extra)
    # explicit CTG sequences override
    if nct in EXPLICIT:
        seq, evid = EXPLICIT[nct]
        seqs = [seq]; confs = ['High']
        ev.insert(0, 'sequence stated in the CTG record -> %s; %s; confidence High' % (seq, evid))
        noseq = []
    if nct in EXPLICIT3:
        seq, evid, cf = EXPLICIT3[nct]
        seqs = [seq]; confs = [cf]
        ev.insert(0, 'sequence stated in the CTG record -> %s; %s; confidence %s' % (seq, evid, cf))
        noseq = []
    if nct in REJECT:
        ev.append('rejected sequence-like token: ' + REJECT[nct])
    # in-file corroboration
    corr = []
    bs = [u for u in (bundle.get(nct, {}).get('uni') or []) if u.get('seq')]
    for seq in seqs:
        core = re.sub(r'\([^)]*\)|\{[^}]*\}', '', seq).replace('/', '').replace('|', '')
        core = re.sub(r'[^A-Z]', '', core.upper())
        if len(core) >= 8:
            for u in bs:
                if core[:12] in u['seq'] or (len(core) >= 12 and core[-12:] in u['seq']):
                    corr.append('%s matches bundle UniProt %s (%s)' % (core[:12], u['acc'], u['name'][:40]))
                    break
    if corr: ev.append('in-file support: ' + '; '.join(sorted(set(corr))[:3]))
    if seqs:
        conf = 'High' if all(c == 'High' for c in confs) else ('Low' if 'Low' in confs else 'Medium')
        if noseq:
            conf = 'Low'
            ev.append('NOTE: co-tested agent(s) without annotated sequence: ' + ', '.join(noseq))
    else:
        conf = 'n/a'
        if not ev: ev.append('no peptide drug identified in the interventions, title or search terms')
    stat[conf] += 1
    parts = []
    for sq in seqs:
        for p in sq.split('|'):
            if p and p not in parts: parts.append(p)
    # The per-drug sequence sources were recorded when the ChEMBL structures were read from
    # the previous corpus's by_source/ dump; that local path does not exist in this corpus, so
    # the ChEMBL record is cited by its id alone.
    evtxt = ' || '.join(ev).replace(' (bundle by_source/chembl.jsonl)', '')
    rows.append({'NCT Number': nct, 'Sequence': '|'.join(parts), 'Confidence': conf,
                 'Evidence': evtxt})
out = (sys.argv[1] if len(sys.argv)>1 else cfg.WORK+'/trial.csv')
with open(out, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['NCT Number', 'Sequence', 'Confidence', 'Evidence'])
    w.writeheader()
    for r in rows: w.writerow(r)
print('rows', len(rows), dict(stat))
print('non-empty', sum(1 for r in rows if r['Sequence']))
