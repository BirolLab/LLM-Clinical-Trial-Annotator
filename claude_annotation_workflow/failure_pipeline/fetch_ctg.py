"""Stage 1: batched registry fetch of the minimum useful field set (section 2)."""
import json, sys, time, urllib.parse, urllib.request, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

FIELDS = [
    "protocolSection.identificationModule.nctId",
    "protocolSection.identificationModule.briefTitle",
    "protocolSection.statusModule.overallStatus",
    "protocolSection.statusModule.lastKnownStatus",
    "protocolSection.statusModule.whyStopped",
    "protocolSection.statusModule.startDateStruct.date",
    "protocolSection.statusModule.primaryCompletionDateStruct.date",
    "protocolSection.statusModule.completionDateStruct.date",
    "protocolSection.statusModule.lastUpdatePostDateStruct.date",
    "protocolSection.designModule.phases",
    "protocolSection.designModule.studyType",
    "protocolSection.designModule.enrollmentInfo.count",
    "protocolSection.designModule.enrollmentInfo.type",
    "protocolSection.sponsorCollaboratorsModule.leadSponsor.name",
    "protocolSection.sponsorCollaboratorsModule.leadSponsor.class",
    "protocolSection.conditionsModule.conditions",
    "protocolSection.armsInterventionsModule.interventions.name",
    "protocolSection.outcomesModule.primaryOutcomes.measure",
    "protocolSection.referencesModule.references.pmid",
    "protocolSection.referencesModule.references.type",
    "protocolSection.referencesModule.references.citation",
    "hasResults",
]

def get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))

def dig(d, path):
    for k in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d

def flat(st):
    p = st.get("protocolSection", {})
    sm, dm, im = p.get("statusModule", {}), p.get("designModule", {}), p.get("identificationModule", {})
    refs = (p.get("referencesModule", {}) or {}).get("references", []) or []
    return {
        "nct_id": im.get("nctId", ""),
        "title": im.get("briefTitle", ""),
        "status": sm.get("overallStatus", "") or "",
        "last_known_status": sm.get("lastKnownStatus", "") or "",
        "why_stopped": (sm.get("whyStopped", "") or "").strip(),
        "start_date": dig(sm, "startDateStruct.date") or "",
        "primary_completion_date": dig(sm, "primaryCompletionDateStruct.date") or "",
        "completion_date": dig(sm, "completionDateStruct.date") or "",
        "last_update_date": dig(sm, "lastUpdatePostDateStruct.date") or "",
        "phases": "|".join(dm.get("phases", []) or []),
        "study_type": dm.get("studyType", "") or "",
        "enrollment": dig(dm, "enrollmentInfo.count"),
        "enrollment_type": dig(dm, "enrollmentInfo.type") or "",
        "sponsor": dig(p, "sponsorCollaboratorsModule.leadSponsor.name") or "",
        "sponsor_class": dig(p, "sponsorCollaboratorsModule.leadSponsor.class") or "",
        "conditions": "|".join((p.get("conditionsModule", {}) or {}).get("conditions", []) or []),
        "interventions": "|".join(
            i.get("name", "") for i in (p.get("armsInterventionsModule", {}) or {}).get("interventions", []) or []),
        "primary_outcomes": "|".join(
            o.get("measure", "") for o in (p.get("outcomesModule", {}) or {}).get("primaryOutcomes", []) or []),
        "has_results": bool(st.get("hasResults")),
        "refs": [{"pmid": r.get("pmid", ""), "type": r.get("type", ""), "citation": r.get("citation", "")} for r in refs],
    }

def main():
    ids = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    out = open(sys.argv[2], "w")
    B, got = 50, 0
    for i in range(0, len(ids), B):
        batch = ids[i:i + B]
        q = urllib.parse.urlencode({
            "filter.ids": ",".join(batch), "fields": ",".join(FIELDS),
            "pageSize": str(B), "format": "json"})
        data = get(config.CTG_API + "?" + q)
        for st in data.get("studies", []):
            out.write(json.dumps(flat(st)) + "\n"); out.flush()
            got += 1
        if (i // B) % 20 == 0:
            print(f"{i+len(batch)}/{len(ids)} ids -> {got} studies", flush=True)
    out.flush(); out.close()
    print(f"DONE {got} studies for {len(ids)} ids", flush=True)

if __name__ == "__main__":
    main()
