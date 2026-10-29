import sys, json
sys.path.insert(0, '.')
from pepseq import sequence_residues
from rdkit import Chem

from sidechains import SC, CTERM, THREE, NTERM
AA20 = 'ACDEFGHIKLMNPQRSTVWY'
def build_templates():
    m = Chem.MolFromSequence(AA20)
    r, e = sequence_residues(Chem.MolToSmiles(m))
    order = r['chains'][0]
    t = {}
    for pos, k in enumerate(order):
        i = r['res'][k]
        t[i['sc'] + ('@ring' if i['nring'] else '')] = (AA20[pos], i['cip'])
    return t
TPL = build_templates()

def render(smiles, extra=None):
    r, e = sequence_residues(smiles)
    if e: return None, e, None
    tpl = dict(TPL); 
    if extra: tpl.update(extra)
    chains = []; unk = []; conj = []
    for ch in r['chains']:
        s = ''
        for pos, k in enumerate(ch):
            i = r['res'][k]
            key = i['sc'] + ('@ring' if i['nring'] else '')
            suf = ''
            if key in tpl:
                let, lcip = tpl[key]
                if i['cip'] and lcip and i['cip'] != lcip: let = let.lower()
            elif key in SC:
                let, lcip, suf = SC[key]
                if i['cip'] and lcip and i['cip'] != lcip:
                    let = let.lower() if len(let) == 1 else '(d' + let[1:]
            else:
                # a conjugated side chain: fall back to the parent residue and drop the conjugate
                base = None
                for k2 in (sorted(tpl, key=len, reverse=True) + sorted(SC, key=len, reverse=True)):
                    if len(k2) >= 3 and key.startswith(k2) and not k2.endswith('@ring'):
                        base = k2; break
                if base:
                    if base in tpl: let, lcip = tpl[base]
                    else: let, lcip, suf = SC[base]
                    if i['cip'] and lcip and i['cip'] != lcip:
                        let = let.lower() if len(let) == 1 else '(d' + let[1:]
                    if 'OCCOCC' in key or 'PEG' in key: suf = (suf or '') + '(PEG)'
                    conj.append(key)
                else:
                    let = '{%s}' % key; unk.append(key)
            pre = ''
            for ns in i['nsub']:
                if i['nring']: continue
                if ns == '*C':
                    base = let.strip('()')
                    if base.upper() == 'G': let = '(Sar)'
                    elif len(base) == 1 and base.upper() in THREE:
                        t = THREE[base.upper()]
                        let = '(Me' + (t if base.isupper() else t.lower()) + ')'
                    elif let.startswith('(') and let.endswith(')'): let = '(Me' + let[1:-1] + ')'
                    else: pre = '(NMe)'
                elif ns == 'CC=O': pre = '(Ac)'
                elif ns in ('CC(C)=O',): pre = '(Ac)'
                elif ns in NTERM: pre = NTERM[ns]
                else: pre = '(N:%s)' % ns
            post = ''
            for cs in i['csub']:
                if cs in CTERM: post = CTERM[cs]
                else: post = '(C:%s)' % cs
            s += pre + let + suf + post
        chains.append(s)
    return chains, None, {'nres': r['nres'], 'cov': r['coverage'], 'unk': unk, 'conj': conj}
