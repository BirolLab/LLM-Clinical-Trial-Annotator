"""SMILES -> peptide sequence perception (RDKit)."""
from rdkit import Chem
from rdkit.Chem import rdmolops
from rdkit import RDLogger
from rdkit.Chem.MolStandardize import rdMolStandardize
RDLogger.DisableLog('rdApp.*')
_TE = rdMolStandardize.TautomerEnumerator()
_CACHE = {}
def canon_frag(s):
    if not s: return ''
    if s in _CACHE: return _CACHE[s]
    out = s
    try:
        m = Chem.MolFromSmiles(s)
        if m is not None:
            m = _TE.Canonicalize(m)
            out = Chem.MolToSmiles(m)
    except Exception:
        pass
    _CACHE[s] = out
    return out

def frag_smiles(mol, atoms, attach):
    """canonical SMILES of the sub-fragment on `atoms`, with `attach` atoms turned into
    dummy atoms so the attachment point is preserved."""
    keep = set(atoms) | set(attach)
    if not keep: return ''
    rw = Chem.RWMol(mol)
    for i in sorted((a.GetIdx() for a in mol.GetAtoms() if a.GetIdx() not in keep), reverse=True):
        rw.RemoveAtom(i)
    # index shift map
    old = sorted(keep)
    newidx = {o: n for n, o in enumerate(old)}
    for o in attach:
        a = rw.GetAtomWithIdx(newidx[o])
        a.SetAtomicNum(0); a.SetNoImplicit(True); a.SetNumExplicitHs(0)
        a.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
        a.SetIsotope(0); a.SetFormalCharge(0)
    m = rw.GetMol()
    try:
        Chem.SanitizeMol(m)
    except Exception:
        return Chem.MolToSmiles(m, isomericSmiles=False)
    try:
        m2 = _TE.Canonicalize(m)
        m = m2
    except Exception:
        pass
    return Chem.MolToSmiles(m, isomericSmiles=False)

def is_carbonyl(a):
    if a.GetSymbol() != 'C': return False
    for b in a.GetBonds():
        o = b.GetOtherAtom(a)
        if o.GetSymbol() == 'O' and b.GetBondType() == Chem.BondType.DOUBLE: return True
    return False

def is_alpha(a):
    if a.GetSymbol() != 'C' or a.GetIsAromatic(): return False
    hasN = any(n.GetSymbol() == 'N' for n in a.GetNeighbors())
    hasCO = any(n.GetSymbol() == 'C' and is_carbonyl(n) for n in a.GetNeighbors())
    return hasN and hasCO

def find_cuts(mol):
    """return (peptide_bond_idxs, ss_bond_idxs, pairs) pairs=(carbonylC_idx, N_idx)"""
    pb = []; pairs = []
    for b in mol.GetBonds():
        a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
        for c, n in ((a1, a2), (a2, a1)):
            if n.GetSymbol() != 'N' or not is_carbonyl(c): continue
            nN = sum(1 for x in c.GetNeighbors() if x.GetSymbol() == 'N')
            if nN != 1: continue
            cas = [x for x in c.GetNeighbors() if is_alpha(x)]
            if not cas: continue
            ca2 = [x for x in n.GetNeighbors() if x.GetIdx() != c.GetIdx() and is_alpha(x)]
            if not ca2: continue
            pb.append(b.GetIdx()); pairs.append((c.GetIdx(), n.GetIdx()))
            break
    ss = [b.GetIdx() for b in mol.GetBonds()
          if b.GetBeginAtom().GetSymbol() == 'S' and b.GetEndAtom().GetSymbol() == 'S']
    return pb, ss, pairs

def residue_info(mol, atoms, pairs_c, pairs_n):
    """describe one residue given atom indices (set) in the parent mol"""
    aset = set(atoms)
    ca = None
    cands = [i for i in atoms if is_alpha(mol.GetAtomWithIdx(i))]
    # restrict to alpha carbons whose N and carbonyl C are in this fragment
    good = []
    for i in cands:
        a = mol.GetAtomWithIdx(i)
        ns = [n.GetIdx() for n in a.GetNeighbors() if n.GetSymbol() == 'N' and n.GetIdx() in aset]
        cs = [n.GetIdx() for n in a.GetNeighbors() if n.GetSymbol() == 'C' and is_carbonyl(n) and n.GetIdx() in aset]
        if ns and cs: good.append((i, ns[0], cs[0]))
    if len(good) != 1: return None
    ca, nidx, cidx = good[0]
    a_ca = mol.GetAtomWithIdx(ca)
    # side chain: everything from ca excluding nidx,cidx
    side = set()
    stack = [x.GetIdx() for x in a_ca.GetNeighbors() if x.GetIdx() not in (nidx, cidx) and x.GetAtomicNum() > 1]
    seen = {ca, nidx, cidx}
    while stack:
        i = stack.pop()
        if i in seen: continue
        seen.add(i); side.add(i)
        for x in mol.GetAtomWithIdx(i).GetNeighbors():
            if x.GetIdx() not in seen and x.GetAtomicNum() > 1 and x.GetIdx() in aset: stack.append(x.GetIdx())
    # also allow side chain to leave the fragment (e.g. cut disulfide -> dummy) : keep within aset
    sc = frag_smiles(mol, side, [ca]) if side else ''
    # N substituents
    nat = mol.GetAtomWithIdx(nidx)
    nsub = sorted(x.GetIdx() for x in nat.GetNeighbors() if x.GetIdx() != ca and x.GetIdx() in aset)
    nsub_s = []
    for i in nsub:
        blk = set(); st = [i]; sn = {nidx, ca}
        while st:
            j = st.pop()
            if j in sn: continue
            sn.add(j); blk.add(j)
            for x in mol.GetAtomWithIdx(j).GetNeighbors():
                if x.GetIdx() not in sn and x.GetAtomicNum() > 1 and x.GetIdx() in aset: st.append(x.GetIdx())
        if blk: nsub_s.append(frag_smiles(mol, blk, [nidx]))
    # C-terminal substituent (on carbonyl C, other than =O and ca)
    cat = mol.GetAtomWithIdx(cidx)
    csub_s = []
    for x in cat.GetNeighbors():
        if x.GetIdx() in (ca,) or x.GetIdx() not in aset: continue
        if x.GetSymbol() == 'O' and mol.GetBondBetweenAtoms(cidx, x.GetIdx()).GetBondType() == Chem.BondType.DOUBLE: continue
        blk = set(); st = [x.GetIdx()]; sn = {cidx, ca}
        while st:
            j = st.pop()
            if j in sn: continue
            sn.add(j); blk.add(j)
            for y in mol.GetAtomWithIdx(j).GetNeighbors():
                if y.GetIdx() not in sn and y.GetAtomicNum() > 1 and y.GetIdx() in aset: st.append(y.GetIdx())
        if blk: csub_s.append(frag_smiles(mol, blk, [cidx]))
    cip = a_ca.GetPropsAsDict().get('_CIPCode', '')
    # ring N: path from N back to CA inside this fragment without using the direct bond
    ring = False
    st = [x.GetIdx() for x in mol.GetAtomWithIdx(nidx).GetNeighbors()
          if x.GetIdx() != ca and x.GetIdx() in aset and x.GetAtomicNum() > 1]
    sn = {nidx}
    while st:
        j = st.pop()
        if j == ca: ring = True; break
        if j in sn: continue
        sn.add(j)
        for x in mol.GetAtomWithIdx(j).GetNeighbors():
            if x.GetIdx() not in sn and x.GetIdx() in aset and x.GetAtomicNum() > 1: st.append(x.GetIdx())
    return {'ca': ca, 'n': nidx, 'c': cidx, 'sc': sc, 'cip': cip,
            'nsub': sorted(nsub_s), 'csub': sorted(csub_s), 'nring': bool(ring)}

def sequence_residues(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None: return None, 'parse_fail'
    frags = Chem.GetMolFrags(mol, asMols=False)
    if len(frags) > 1:
        frags = sorted(frags, key=len, reverse=True)
        keep = set(frags[0])
        mol = Chem.RWMol(mol)
        for i in sorted([a.GetIdx() for a in mol.GetAtoms() if a.GetIdx() not in keep], reverse=True):
            mol.RemoveAtom(i)
        mol = mol.GetMol()
        Chem.SanitizeMol(mol)
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    pb, ss, pairs = find_cuts(mol)
    if not pairs: return None, 'no_peptide_bond'
    # fragment atom sets after removing pb+ss bonds
    em = Chem.RWMol(mol)
    for bi in sorted(set(pb) | set(ss), reverse=True):
        b = mol.GetBondWithIdx(bi)
        em.RemoveBond(b.GetBeginAtomIdx(), b.GetEndAtomIdx())
    fr = Chem.GetMolFrags(em.GetMol(), asMols=False)
    owner = {}
    for k, f in enumerate(fr):
        for i in f: owner[i] = k
    res = {}
    for k, f in enumerate(fr):
        info = residue_info(mol, f, None, None)
        if info: res[k] = info
    # order: edges from residue(owner of carbonyl C) -> residue(owner of N)
    nxt = {}; prv = {}
    for c, n in pairs:
        kc, kn = owner[c], owner[n]
        if kc in res and kn in res:
            nxt[kc] = kn; prv[kn] = kc
    starts = [k for k in res if k not in prv]
    chains = []; used = set()
    for s in sorted(starts):
        ch = []; k = s
        while k is not None and k not in used:
            used.add(k); ch.append(k); k = nxt.get(k)
        chains.append(ch)
    cyc = [k for k in sorted(res) if k not in used]
    while cyc:
        s = cyc[0]; ch = []; k = s
        while k is not None and k not in used:
            used.add(k); ch.append(k); k = nxt.get(k)
        chains.append(ch); cyc = [k for k in sorted(res) if k not in used]
    cov = sum(len(fr[k]) for k in res)
    return {'res': res, 'chains': chains, 'frags': [len(f) for f in fr],
            'nres': len(res), 'coverage': cov / mol.GetNumHeavyAtoms(),
            'nfrag': len(fr), 'cyclic': bool([k for k in res if k in prv and k in nxt and nxt.get(k) == prv.get(k)])}, None
