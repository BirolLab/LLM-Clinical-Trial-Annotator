import re
AMIDE = re.compile(r'AMIDE$|AMIDE,')
def render_gsrs(rec):
    """rec from gsrs_proteins.jsonl -> (sequence_string, notes, unmapped_frags)"""
    subs = {i: list(s) for i, s in rec['subunits'] if s and len(s) >= 8}
    if not subs: return None, [], []
    notes = []; unmapped = []
    pre = {}; post = {}
    for m in rec.get('mods') or []:
        f = (m.get('frag') or '').upper()
        loc = (m.get('loc') or '')
        sites = m.get('sites') or []
        if not f: continue
        if any(k in f for k in ('PALMITAMIDO', 'ICOSANEDIOYL', 'OCTADECANEDIOYL', 'MYRISTOYL',
                                'PALMITOYL', 'STEAROYL', 'HEXADECANOYL', 'OCTADECANOYL',
                                'TETRADECANOYL', 'DODECANOYL', 'LITHOCHOLIC', 'LAUROYL',
                                'TETRAXETAN', 'DOTA', 'DTPA', 'MECOSAR', 'CHELATOR',
                                'ALBUMIN', 'IMMUNOGLOBULIN', 'MALEIMID', 'KLH', 'TOXOID',
                                'VEDOTIN', 'DERUXTECAN', 'CYSTEINYL', 'HEME', 'ZINC', 'CALCIUM')):
            notes.append('omitted conjugate: ' + f[:40]); continue
        tok = None; repl = None
        if 'PEG' in f or 'POLYETHYLENE GLYCOL' in f or 'POLY(ETHYLENE GLYCOL)' in f:
            tok = '(PEG)'
        elif AMIDE.search(f) or f.endswith('AMIDE'):
            tok = '(NH2)'
            if f.startswith('D-') or ', D-' in f: repl = 'lower'
        elif '2-AMINOISOBUTYRIC' in f or 'AMINOISOBUTYRIC' in f:
            repl = 'X'
        elif 'PIDOLIC ACID' in f or 'PYROGLUTAM' in f:
            repl = '(pGlu)'
        elif f.startswith('N-ACETYL') or f == 'ACETIC ACID':
            tok = '(Ac)'
            if '-D-ALANINE' in f: repl = 'lower'
            if 'NAPHTHYL' in f: repl = '(d2Nal)'
        elif 'HYDROXYPROLINE' in f: repl = '(Hyp)'
        elif 'NORLEUCINE' in f: repl = '(Nle)'
        elif 'SARCOSINE' in f: repl = '(Sar)'
        elif 'ORNITHINE' in f: repl = '(Orn)'
        elif 'FENCLONINE' in f: repl = '(dCpa)' if '(R)' in f else '(Cpa)'
        elif 'PYRIDYL)-D-ALANINE' in f: repl = '(d3Pal)'
        elif 'DIAMINOBUTYRIC' in f: repl = '(Dab)'
        elif 'O-PHOSPHATE' in f or 'FOSFOSERINE' in f or 'PHOSPHATE' in f:
            tok = '(PO3H2)'
        elif 'O-SULFATE' in f: tok = '(SO3H)'
        elif 'PROLINE ETHYLAMIDE' in f: tok = '(NHEt)'
        elif '1-NAPHTHYL-L-ALANINE' in f: repl = '(1Nal)'
        elif '3-(2-NAPHTHYL)-D-ALANINE' in f: repl = '(d2Nal)'
        elif 'METHYL-L-TRYPTOPHAN' in f: repl = '(MeTrp)'
        elif 'ACETURIC' in f: tok = '(Ac)'
        elif 'ACETYL' in f: tok = '(Ac)'
        elif f.endswith(', D-'):
            repl = 'lower'
        else:
            unmapped.append(f[:50]); continue
        for st in sites:
            si = st.get('subunitIndex'); ri = st.get('residueIndex')
            if si is None or ri is None: continue
            if repl == 'lower': post.setdefault((si, ri), []); pre.setdefault((si, ri), [])
            if repl and repl != 'lower': post.setdefault((si, ri), []); pre.setdefault((si, ri), [])
            if repl == 'lower': subs.get(si) and ri <= len(subs[si]) and subs[si].__setitem__(ri-1, subs[si][ri-1].lower())
            elif repl:
                if si in subs and ri <= len(subs[si]): subs[si][ri-1] = repl
            if tok:
                if tok == '(Ac)' or (loc == 'N-TERMINUS'): pre.setdefault((si, ri), []).append(tok)
                else: post.setdefault((si, ri), []).append(tok)
    out = []
    for si in sorted(subs):
        s = ''
        for k, aa in enumerate(subs[si], 1):
            s += ''.join(pre.get((si, k), [])) + aa + ''.join(post.get((si, k), []))
        out.append(s)
    return '/'.join(out), notes, unmapped
