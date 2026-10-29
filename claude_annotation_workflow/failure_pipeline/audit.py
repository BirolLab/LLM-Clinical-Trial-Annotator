"""Per-pattern match counts over the corpus stop texts (section 10.1) plus the
bucket distribution and the unclassified list (section 5.5 dump-and-read loop)."""
import collections, csv, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules
from rules import classify_text, norm

texts = [(r['nct_id'], r['status'], r['why_stopped'])
         for r in csv.DictReader(open(os.path.join(os.path.dirname(__file__), 'work/whystopped.csv')))]

def audit_patterns():
    groups = [("RECRUIT_PHRASES", rules.RECRUIT_PHRASES),
              ("BUSINESS_PATTERNS", rules.BUSINESS_PATTERNS),
              ("INEFFECTIVE_PATTERNS", rules.INEFFECTIVE_PATTERNS),
              ("TOXIC_PATTERNS", rules.TOXIC_PATTERNS)]
    dead = []
    for name, pats in groups:
        for rx, sub in pats:
            n = sum(1 for _, _, t in texts if re.search(rx, norm(t), re.I))
            if n == 0:
                dead.append((name, sub, rx))
    singles = [("NONFAILURE", rules.NONFAILURE), ("UNINFORMATIVE", rules.UNINFORMATIVE)]
    for name, pats in singles:
        for rx in pats:
            n = sum(1 for _, _, t in texts if rx.search(norm(t)))
            if n == 0:
                dead.append((name, rx.pattern[:60], rx.pattern))
    print(f"--- inert patterns: {len(dead)}")
    for name, sub, rx in dead:
        print(f"    {name:22s} {sub!r:40s} {rx[:90]}")

def run():
    out, unresolved = [], []
    for nct, status, t in texts:
        d = classify_text(t, status)
        out.append((nct, status, t, d))
        if d is None or d["reason"] is None:
            unresolved.append((nct, status, t, d))
    print(f"\n--- buckets over {len(out)} stated stop reasons")
    c = collections.Counter((d["reason"] or "(no reason on record)") for _, _, _, d in out)
    for k, v in c.most_common():
        print(f"{v:6d}  {k}")
    print(f"\n--- confidence")
    for k, v in collections.Counter(d["confidence"] for _, _, _, d in out).most_common():
        print(f"{v:6d}  {k}")
    print(f"\n--- arbitration rule")
    for k, v in collections.Counter(d["rule"] for _, _, _, d in out).most_common():
        print(f"{v:6d}  {k}")
    print(f"\n--- sub-reason (top 25)")
    for k, v in collections.Counter(d["sub"] for _, _, _, d in out if d["reason"]).most_common(25):
        print(f"{v:6d}  {k}")
    print(f"\n--- no reason on record from a stated text: {len(unresolved)}")
    for nct, status, t, d in unresolved:
        print(f"    {status[:4]} | {d['rule'][:22]:22s} | {t[:110]}")
    json.dump([{"nct_id": n, "status": s, "text": t,
                "reason": d["reason"], "confidence": d["confidence"],
                "rule": d["rule"], "sub": d["sub"]} for n, s, t, d in out],
              open(os.path.join(os.path.dirname(__file__), 'work/ws_classified.json'), 'w'), indent=0)

if __name__ == "__main__":
    audit_patterns()
    run()
