"""Section 4.1: registry narrative fields beyond whyStopped, for exactly the subset
that needs them -- detailed description, posted-results limitations-and-caveats,
participant-flow disposition types, and primary-outcome analyses."""
import json, os, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

FIELDS = [
    "protocolSection.identificationModule.nctId",
    "protocolSection.descriptionModule.detailedDescription",
    "resultsSection.moreInfoModule.limitationsAndCaveats.description",
    "resultsSection.participantFlowModule.periods.dropWithdraws.type",
    "resultsSection.participantFlowModule.recruitmentDetails",
    "resultsSection.outcomeMeasuresModule.outcomeMeasures.type",
    "resultsSection.outcomeMeasuresModule.outcomeMeasures.title",
    "resultsSection.outcomeMeasuresModule.outcomeMeasures.analyses.pValue",
    "resultsSection.outcomeMeasuresModule.outcomeMeasures.analyses.pValueComment",
    "resultsSection.outcomeMeasuresModule.outcomeMeasures.analyses.statisticalMethod",
]

def get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))

def flat(st):
    p, rs = st.get("protocolSection", {}), st.get("resultsSection", {}) or {}
    pf = rs.get("participantFlowModule", {}) or {}
    disp = []
    for per in pf.get("periods", []) or []:
        for dw in per.get("dropWithdraws", []) or []:
            if dw.get("type"):
                disp.append(dw["type"])
    oms = []
    for om in (rs.get("outcomeMeasuresModule", {}) or {}).get("outcomeMeasures", []) or []:
        oms.append({"type": om.get("type", ""), "title": om.get("title", ""),
                    "p": [{"pValue": a.get("pValue", ""), "comment": a.get("pValueComment", ""),
                           "method": a.get("statisticalMethod", "")}
                          for a in om.get("analyses", []) or []]})
    return {
        "nct_id": (p.get("identificationModule", {}) or {}).get("nctId", ""),
        "detailed": ((p.get("descriptionModule", {}) or {}).get("detailedDescription", "") or ""),
        "limitations": (((rs.get("moreInfoModule", {}) or {}).get("limitationsAndCaveats", {}) or {})
                        .get("description", "") or ""),
        "recruitment_details": pf.get("recruitmentDetails", "") or "",
        "dispositions": sorted(set(disp)),
        "outcomes": oms,
    }

def main():
    ids = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    out = open(sys.argv[2], "w")
    B, got = 25, 0
    for i in range(0, len(ids), B):
        batch = ids[i:i + B]
        q = urllib.parse.urlencode({"filter.ids": ",".join(batch), "fields": ",".join(FIELDS),
                                    "pageSize": str(B), "format": "json"})
        for st in get(config.CTG_API + "?" + q).get("studies", []):
            out.write(json.dumps(flat(st)) + "\n"); out.flush(); got += 1
        if (i // B) % 10 == 0:
            print(f"{i+len(batch)}/{len(ids)} -> {got}", flush=True)
    out.close()
    print(f"DONE {got}/{len(ids)}", flush=True)

if __name__ == "__main__":
    main()
