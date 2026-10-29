"""Verbatim stop text -> expected bucket (section 10.6).  Fast regression check."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rules import classify_text
from config import RECRUITMENT, BUSINESS, INEFFECTIVE, TOXIC, COVID

T = "TERMINATED"
W = "WITHDRAWN"
CASES = [
    # --- recruitment
    ("Low accrual", T, RECRUITMENT),
    ("Slow accrual; closed by funder", T, RECRUITMENT),
    ("Did not meet target patient accrual goals", T, RECRUITMENT),
    ("Futility for enrollment", T, RECRUITMENT),
    ("Accrual Factor", T, RECRUITMENT),
    ("Under-enrollment", T, RECRUITMENT),
    ("High number of screen failures", T, RECRUITMENT),
    ("Patients were screened but not enrolled", W, RECRUITMENT),
    ("Recruitment was at a standstill. We are currently preparing our results for publication.", T, RECRUITMENT),
    ("Diminished rectruitment", T, RECRUITMENT),
    ("Low recruiment.", T, RECRUITMENT),
    ("Lost funding due to low enrollment.", T, RECRUITMENT),
    ("Subjects were not recruited as intended.", W, RECRUITMENT),
    ("DSMC acknowledged no safety concerns with the trial, recommending that the trial be terminated due to slow enrollment", T, RECRUITMENT),
    ("Enrollment was much slower than anticipated, leading to a decision to terminate the study early for enrollment futility.", T, RECRUITMENT),
    ("The study was stopped because all five participants were lost to follow-up before completing treatment or any assessments, leaving no outcome data available and making continuation of the trial infeasible.", T, RECRUITMENT),
    ("Study was not initiated and has been withdrawn due to lack of appropriate cases", W, RECRUITMENT),
    # --- business
    ("Break in funding", T, BUSINESS),
    ("PI left institution", T, BUSINESS),
    ("Investigator left institution. 7 patients accrued and there is insufficient data to analyze.", T, BUSINESS),
    ("Due to funding source and lack of accrual", T, BUSINESS),
    ("stopped before the targeted number of patients was reached due to lack of support.", T, BUSINESS),
    ("Recruitment was stopped before start of the pollen season", T, BUSINESS),
    ("Study never started", W, BUSINESS),
    ("Transfer of study sponsor", T, BUSINESS),
    ("Study drug no longer available", T, BUSINESS),
    ("competing study at site", T, BUSINESS),
    ("Enrollment held for toxicity evaluation; then closed due to competing trial", T, BUSINESS),
    ("Blood sugar status of the enrolled subjects wasn't evaluable", T, BUSINESS),
    ("Duplicate Study", W, BUSINESS),
    ("A business decision was made by Pfizer to terminate the study. Termination was not due to any safety concerns, requests from regulatory authorities, changes to the benefit/risk profile or any new concerns regarding the investigational product.", T, BUSINESS),
    ("Trial was terminated for business reasons. There has been no change in the benefit/risk profile of ofatumumab.", T, BUSINESS),
    ("The study was terminated early as related study I3Y-MC-JPCM (NCT03706365) did not meet its primary endpoint.", T, BUSINESS),
    ("Per source documents the study was terminated well in advance of targeted enrollment. A method for the analysis of insulin and proinsulin samples was never fully developed and validated. Study terminated upon expiration of IRB approval", T, BUSINESS),
    ("reduced recruitment rate due to non infectious, but competitive trials at our institution", T, BUSINESS),
    ("Stopped after internal review", T, BUSINESS),
    # --- ineffective
    ("Lack of efficacy", T, INEFFECTIVE),
    ("Per interim analysis, for futility.", T, INEFFECTIVE),
    ("Primary endpoint was not met", T, INEFFECTIVE),
    ("Superiority was no longer attainable", T, INEFFECTIVE),
    ("experimental treatment not Superior to standard - no need to continue the follow-up", T, INEFFECTIVE),
    ("Following review of Part 1 study data, the Sponsor decided to terminate the study with immediate effect. Results indicated that VE202 was not superior to placebo on the primary or any of the secondary endpoints. No new safety concerns were observed.", T, INEFFECTIVE),
    ("The study was terminated based on the review by an independent data monitoring committee of the prespecified interim analysis of the Phase 3 AMEERA-5 efficacy data. No new safety signals were observed.", T, INEFFECTIVE),
    ("Withdrawn because there were no dramatic changes in the main endpoint, as well as low enrollment numbers. The data are not interpretable in terms of efficacy.", T, INEFFECTIVE),
    ("Lack of substantial evidence for immune responses in response to vaccination.", T, INEFFECTIVE),
    ("Due to lack of clinical efficacy and lack of drug supply, trial was closed early and correlative studies were not pursued further.", T, INEFFECTIVE),
    # --- toxic
    ("Unexpected toxicity (2 early deaths)", T, TOXIC),
    ("Hepatic safety signal identified.", T, TOXIC),
    ("Due to adverse events", T, TOXIC),
    ("Study was terminated due to patient complications unrelated to study drugs", T, TOXIC),
    ("Due to the high rate of morbidity and mortality", T, TOXIC),
    # --- covid
    ("Covid-19 Pandemic", T, COVID),
    ("Study drug not available due to COVID-19 FDA restrictions", T, COVID),
    ("Study completed early due to COVID-19 pandemic regulations.", T, COVID),
    ("Closed due to historically slow enrollment compounded by the COVID-19 pandemic.", T, RECRUITMENT),
    ("Difficulty in recruiting patients also due to the pandemic period, presence of competitive studies.", T, RECRUITMENT),
    ("The study was terminated early due to low enrollment, this was partially related to our ability to recruit during the COVID-19 pandemic.", T, RECRUITMENT),
    ("No longer studying long COVID", W, BUSINESS),
    ("Recruitment rate; a lower than anticipated observed cardiovascular event rate. The Sponsor decision to stop the trial was not based on any safety concerns or any knowledge of the results, or influenced by issues imposed by the COVID-19 pandemic.", T, RECRUITMENT),
    # --- non-failure / uninformative -> no reason on record
    ("Met study stopping rules", T, None),
    ("end-point reached", T, None),
    ("Study completed", T, None),
    ("Finished", T, None),
    ("all patients recruited", T, None),
    ("Study intervention was adopted as standard of care.", T, None),
    ("DSMB recommendation based on safety benefit in Experimental (oral) arm", T, None),
    ("why study stopped", T, None),
    ("Not stated", T, None),
    ("Withdrawn", W, None),
    ("Terminated: recruiting or enrolling participants has halted prematurely and will not resume; participants are no longer being examined or treated", T, None),
    ("Unable to complete study", T, None),
]

def main():
    bad = 0
    for text, status, want in CASES:
        got = classify_text(text, status)
        g = got["reason"] if got else None
        if g != want:
            bad += 1
            print(f"FAIL want={want!r} got={g!r} rule={got and got.get('rule')!r}\n      {text[:150]}")
    print(f"\n{len(CASES)-bad}/{len(CASES)} unit cases pass")
    return bad

if __name__ == "__main__":
    sys.exit(1 if main() else 0)
