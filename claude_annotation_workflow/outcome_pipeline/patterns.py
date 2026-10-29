#!/usr/bin/env python3
"""The six keyword families plus the relevance / exclusion / filter lexicons.

Every pattern here is counted against the corpus by audit_patterns.py (S9.1): a
zero count means the regex is broken, not that the phrase is rare. Note the
deliberate absence of `\b` after any stem that takes a suffix -- `difference\b`
can never match "differences", and the whole alternation dies silently.
"""
import re

# ---------------------------------------------------------------- polarity families
# family -> weight (S5.5). Endpoint families outweigh efficacy families.
WEIGHTS = {
    "negative-endpoint": 3.0,
    "negative-safety": 2.5,
    "negative-efficacy": 1.6,
    "positive-endpoint": 3.0,
    "positive-safety": 1.4,
    "positive-efficacy": 1.0,
}

FAMILIES = {
    "negative-endpoint": [
        r"did not (?:meet|achieve|reach|attain)",
        r"(?:failed|failure) to (?:meet|achieve|reach|demonstrate|show)",
        r"(?:primary|co-primary)(?: |[^.]{0,40} )(?:end ?point|outcome)s? (?:was|were|is|are)? ?not (?:met|achieved|reached)",
    # the measure name sits between the endpoint and its verb far more often than not:
    # "the primary endpoint of change in systolic blood pressure was not met"
    r"(?:end ?point|outcome)s?(?: of| for| in)[^.]{0,60} (?:was|were) not (?:met|achieved|reached|attained)",
        r"(?:end ?point|outcome)s? (?:was|were) not (?:met|achieved|reached|attained)",
        r"non[-\s]?inferiority (?:was )?not (?:met|demonstrated|established|shown|achieved)",
        r"(?:failed|fails) to (?:establish|confirm)",
    # a phase-2 go/no-go verdict is a statement about the registered endpoint:
    # "none of these three regimens were effective enough ... to warrant further study"
        r"(?:not|none|neither)[^.]{0,45}(?:effective|efficacious|active) enough[^.]{0,80}(?:warrant|justify|recommend)",
    # "canakinumab and anakinra were safe but were not effective as single
    # immunotherapy": an explicit non-efficacy verdict on the drug is an endpoint
    # statement, so it must outweigh the positive-safety half of the same sentence
    # in anything but a phase-1 trial, where S5.6.3 makes safety the endpoint.
        r"(?:was|were|is|are) not (?:clinically |statistically |sufficiently )?(?:effective|efficacious)\b",
        r"(?:stopped|terminated|discontinued|halted|closed|clos(?:ing|ure))\w* (?:early |prematurely )?(?:for|due to|because of|owing to|on the basis of) futility",
        r"futility (?:boundary|boundaries|threshold|criteri\w+|rule|margin)s? (?:was |were )?(?:crossed|met|reached|exceeded)",
        r"crossed the (?:pre[-\s]?specified |prespecified )?futility (?:boundary|threshold)",
        r"(?:met|meeting) (?:the )?(?:pre[-\s]?specified |prespecified )?criteri\w+ for futility",
        r"(?:declared|deemed) futile",
        r"(?:was|were) not superior",
        r"no(?:t)? (?:significantly )?superior to",
        r"did not (?:significantly )?(?:improve|reduce|increase|differ from placebo|prolong)",
        r"(?:trial|study) (?:was )?(?:stopped|terminated|halted) (?:early|prematurely)",
        r"(?:narrowly )?(?:missed|failed on) (?:the|its|both|all) (?:co-)?(?:primary )?(?:end ?point|outcome)",
        r"(?:study|trial) was[^.]{0,25}(?:unsuccessful|negative)",
        r"did not (?:confirm|support|demonstrate|show|reveal|detect) (?:the |a |an |any )?"
        r"(?:significant |clinical )?(?:efficacy|benefit|superiority|advantage|efficacy signal)",
        r"(?:primary|co-primary) (?:end ?point|outcome)s? (?:was|were) (?:therefore )?not",
        r"(?:terminated|closed|stopped|halted) (?:early |prematurely )?(?:after|at|following|on)(?: an?| the)?(?: pre[-\s]?planned| planned| preplanned)? interim",
        r"(?:enrol?lment|accrual) (?:was )?(?:stopped|halted|suspended|terminated)",
    ],
    "negative-safety": [
        r"(?:dose-limiting toxicit(?:y|ies)|DLTs?) (?:was|were) (?:observed|reported|seen|experienced|noted)",
        r"(?:unacceptable|unacceptably|excessive|prohibitive|substantial) (?:toxicit|adverse|rate of)",
        r"(?:treatment|drug|study|therapy)[- ]related (?:death|mortalit|fatalit)",
        r"(?:safety|toxicity|tolerability) concerns?",
        r"(?:poorly tolerated|not well[- ]tolerated|not well tolerated|inadequately tolerated)",
        r"(?:poor|inadequate) tolerabilit",
        r"(?:stopped|terminated|halted|discontinued) (?:early )?(?:for|due to|because of) (?:safety|toxicit|adverse|an? (?:safety|toxicity))",
        r"(?:significantly|markedly|substantially) (?:higher|greater|increased|more frequent) (?:rate|risk|incidence|frequency|number|proportion)s? (?:of |for )?(?:\w+[ ,-]){0,4}(?:adverse|toxicit|infection|death|mortalit|hypoglyc|hypokal|complication|bleeding|discontinuation|seizure|epileptiform|fracture|exacerbation|hospitali)",
        r"significantly increased (?:the )?(?:risk|rate|incidence) of (?:\w+[ ,-]){0,4}(?:adverse|toxicit|infection|death|mortalit|hypoglyc|hypokal|complication|bleeding)",
        r"(?:increase[sd]?|higher|greater|elevated) (?:risk|rate|incidence|frequency|number) "
        r"of (?:\w+[ ,-]){0,4}(?:adverse|toxicit|infection|death|mortalit|hypoglyc|hypokal|"
        r"complication|bleeding|episode|event|fracture|exacerbation|hospitali|discontinu)",
        r"(?:serious |severe |grade [345][+]? |treatment-emergent )?adverse events?[^.]{0,30}(?:was|were)[^.]{0,20}(?:higher|greater|more frequent|more common)",
        r"(?:safety|toxicity) (?:signal|issue)s?",
        r"maximum tolerated dose (?:was )?(?:not|exceeded)",
        r"(?:led|leading|resulting) (?:to|in) (?:early |premature )?(?:study|trial|enrol?lment|accrual) (?:closure|termination|suspension|discontinuation)",
        r"(?:increase|increased|higher|excess) (?:in )?(?:all-cause )?mortality",
        r"(?:anaphyla|hypersensitivity reaction)",
    ],
    "negative-efficacy": [
        r"no (?:statistically )?significant (?:difference|change|effect|improvement|reduction|increase|benefit|association|interaction)",
        r"(?:was|were|showed) no (?:significant )?(?:difference|effect|benefit|improvement|change)",
        r"did not differ(?: significantly)?",
        r"no (?:effect|benefit|improvement|advantage|impact) (?:of|on|was|were)",
        r"(?:similar|comparable|equivalent) (?:efficacy|response|outcome|reduction|improvement)",
        r"(?:without|lacked) (?:a )?(?:significant )?(?:effect|benefit|improvement)",
        r"not (?:statistically )?significant(?:ly)?",
        r"(?:no|without) (?:apparent |measurable |detectable )?(?:clinical )?benefit",
        r"(?:ineffective|insufficient efficacy|lack of efficacy|lacking efficacy)",
        r"(?:worse|worsened|deteriorated|declined|poorer) (?:outcome|response|survival|control|function)",
        r"(?:p|P) ?[=>] ?0?\.(?:0[5-9]|[1-9])",
    ],
    "positive-endpoint": [
        r"(?:met|achieved|reached|attained) (?:the|its|both|all) (?:co-)?(?:primary )?(?:end ?point|outcome)",
        r"(?:primary|co-primary) (?:end ?point|outcome)s? (?:was|were) (?:met|achieved|reached|attained)",
        r"non[-\s]?inferiority (?:was )?(?:met|demonstrated|established|shown|achieved|confirmed)",
        r"(?:was|were) non[-\s]?inferior",
        r"(?:was|were|proved|proven) superior to",
        r"(?:demonstrated|showed|established) superiority",
        r"(?:met|achieved) (?:the )?(?:pre[-\s]?specified|predefined|prespecified) (?:criteri|threshold|target)",
        r"(?:primary|co-primary) (?:end ?point|outcome)s? (?:was|were) (?:successfully )?(?:met|satisfied)",
        r"(?:primary|co-primary)[^.]{0,40}(?:reached|achieved|attained|met) (?:statistical )?significance",
        r"(?:the )?(?:study|trial) (?:met|achieved) (?:its|the)",
        r"bioequivalen(?:ce|t)[^.]{0,20}(?:was |were )?(?:achieved|established|demonstrated|met|shown|concluded|confirmed)",
        r"(?:met|meeting|within|satisfied) the[^.]{0,30}bioequivalence (?:criteri|limit|range|bound|margin)",
        r"(?:establish(?:ing|ed)|indicating|conclude[sd]?) bioequivalen",
    ],
    "positive-safety": [
        r"(?:was|were|generally) (?:well|safely) tolerated",
        r"(?:acceptable|favourable|favorable|good|satisfactory|manageable) (?:safety|tolerability|toxicity) (?:profile|pattern)?",
        r"no (?:dose-limiting|serious|treatment-related|drug-related|significant|unexpected) (?:toxicit|adverse|safety|event|side ?effect)",
        r"(?:no|without) (?:treatment|drug|study)[- ]related (?:death|serious adverse|mortalit)",
        r"(?:safe|safety) (?:and (?:well |effectively )?tolerat|profile was accept)",
        r"(?:was|were|appears?|appeared) (?:to be )?safe",
        r"no (?:new |unexpected )?safety (?:signal|concern|issue)s?",
        r"(?:adverse|side) (?:events?|effects?) (?:were|was) (?:mostly |mainly |generally |predominantly )?(?:mild|moderate|transient|manageable|comparable|similar)",
        r"(?:did not|no) (?:increase|increased|higher) (?:the )?(?:risk|rate|incidence) of",
        r"no (?:cases? of |episodes? of )?(?:severe )?hypoglyca?emia",
        r"(?:tolerability|tolerance)[^.]{0,25}(?:was |were )?(?:accept|good|excellent|favou?rab|satisfactor)",
    ],
    "positive-efficacy": [
        r"(?:significantly|markedly|substantially) (?:improved|reduced|increased|decreased|lowered|enhanced|prolonged)",
        r"(?:significant|marked|substantial|clinically meaningful) (?:improvement|reduction|increase|decrease|benefit|response|effect|decline in)",
        r"(?:was|were) (?:effective|efficacious)",
        r"(?:demonstrated|showed|showing|shown) (?:a |an )?(?:significant |clinically )?(?:efficacy|improvement|benefit|reduction|response|activity|advantage)",
        r"(?:improved|improvement in) (?:symptom|function|control|quality of life|survival|outcome)",
        r"(?:p|P) ?[<≤] ?0?\.0(?:0?[0-4]\d*|5)\b",
        r"(?:encouraging|promising|favourable|favorable) (?:activity|efficacy|result|response|outcome)",
        r"(?:objective |overall |complete )?(?:response|remission) rate",
        r"(?:greater|higher|increased) (?:reduction|improvement|weight loss|response|control|remission|survival|clearance)",
        r"(?:supports?|supporting) (?:the )?(?:use|efficacy|further development)",
        r"(?:beneficial|clinically relevant) effect",
    ],
}

COMPILED = {fam: [(p, re.compile(p, re.I)) for p in pats] for fam, pats in FAMILIES.items()}

# ---------------------------------------------------------------- relevance (S5.2)
DESIGN_RE = re.compile(
    r"\b(?:randomi[sz]ed|randomi[sz]ation|double[-\s]?blind|single[-\s]?blind|"
    r"placebo[-\s]?controlled|open[-\s]?label|cross[-\s]?over|phase\s*(?:1|2|3|4|i{1,3}|iv)\b|"
    r"primary (?:end ?point|outcome)|multicent(?:re|er)|parallel[-\s]?group|"
    r"enrol?led|participants were assigned|intention[-\s]?to[-\s]?treat)", re.I)

NCT_RE = re.compile(r"\bNCT\d{8}\b")

REVIEW_TITLE_HARD = re.compile(
    r"\b(?:systematic review|meta[-\s]?analys[ie]s|meta[-\s]?analytic|scoping review|"
    r"narrative review|umbrella review|network meta[-\s]?analys[ie]s|"
    r"a review\b|: a review|review of the literature|literature review|"
    r"review and meta|pooled analys[ie]s)", re.I)

REVIEW_TITLE_SOFT = re.compile(
    r"\b(?:review|overview|update on|current status|state of the art|"
    r"perspective|opinion|commentary|editorial|landscape|pipeline|"
    r"advances in|progress (?:in|of)|emerging role|future directions|"
    r"what(?:'s| is) new|a primer|consensus (?:statement|recommendation)|"
    r"critical appraisal|current evidence|considerations for|"
    r"new (?:concepts|approaches|strategies|insights|horizons|frontiers) (?:for|in|into)|"
    r"(?:novel|new|emerging|current|recent) (?:treatments|therapies|therapeutics|"
    r"agents|drugs|options|approaches|modalities|strategies) (?:for|in|of|to)|"
    r"therapeutic potential|clinical potential of|role of .{0,40}in the management of|"
    r"where (?:are|do) we|lessons (?:learned|from)|"
    r"guideline|position (?:statement|paper))", re.I)

REVIEW_BODY = re.compile(
    r"\b(?:we (?:review|summari[sz]e|searched|discuss)|this review|"
    r"in this review|were searched|databases were searched|PubMed(?:,| and)|"
    r"Cochrane (?:Library|Central)|search(?:ed)? (?:MEDLINE|Embase)|"
    r"eligible studies|included studies|random[-\s]?effects model|"
    r"pooled (?:estimate|odds|risk|mean|hazard)|heterogeneity was|I2 ?=|"
    r"forest plot|PRISMA)", re.I)

# excluded outright whatever the score (S5.2)
EXCLUDE_TITLE = re.compile(
    r"\b(?:in vitro|in-vitro|ex vivo|ex-vivo|in silico|preclinical|pre-clinical|"
    r"animal model|\bmice\b|\bmurine\b|\brats?\b|\brabbit|\bzebrafish|\bcanine|"
    r"cell line|cytotoxicity assay|"
    r"case report|case series|case of\b|a case\b|"
    r"study protocol|protocol for|trial protocol|design (?:and rationale|of a)|"
    r"rationale and design|statistical analysis plan|"
    r"cost[-\s]?effectiveness|cost[-\s]?utility|budget impact|claims (?:analys|database)|"
    r"post[-\s]?hoc|posthoc|secondary analys[ie]s|exploratory analys[ie]s|"
    r"prognostic (?:factor|index|marker|model|score|value)s?|competing risks?|"
    r"model[-\s]?informed|model[-\s]?based (?:analys|approach)|dose selection|"
    r"subgroup analys[ie]s|pooled|\bmethod(?:s)? (?:validation|development)|"
    r"assay (?:validation|development)|analytical validation|"
    # a device/meter performance paper measures the instrument used in the trial, not
    # the trial: "System Accuracy Assessment of a Blood Glucose Meter ..." concludes it
    # "did not meet the level of analytical accuracy required", which is not an endpoint.
    r"(?:system|analytical|measurement|device) accuracy|accuracy (?:assessment|of a)|"
    r"performance (?:assessment |evaluation )?of (?:a|the) (?:blood glucose |continuous )?"
    r"(?:meter|monitor|sensor|device|assay|system)|"
    # a model built on a finished trial's data reports the model, not the trial:
    # "Prediction of People ... Not Achieving HbA1c Target ... Machine Learning"
    r"machine learning|deep learning|artificial intelligence|"
    r"predicti(?:on|ve) model|prediction of\b|nomogram|"
    r"bibliometric|cross[-\s]?sectional survey|questionnaire survey|"
    r"ongoing (?:clinical )?trials|trials in progress|"
    r"clinical trials?: (?:status|current|an? (?:update|overview))|"
    r"a (?:systematic|rapid) (?:review|search)|"
    # a paper about how the trial was RUN, not what it found (S5.2, the same class as
    # method-validation papers). "...to Improve Research Staff Preparedness for Informed
    # Consent" concludes "titration study consent rates did not improve" -- a statement
    # about recruitment process that the negative-endpoint family reads as a failed trial.
    r"informed consent|consent rates?|research staff|study staff (?:training|preparedness)|"
    r"staff preparedness|telesimulation|recruitment (?:strateg|challeng|barrier|experience)|"
    r"enrol?ment (?:strateg|challeng|barrier|experience)|lessons learned|"
    r"site (?:performance|selection)|data (?:management|quality|monitoring) plan)", re.I)

# pooled multi-trial survey phrasing, caught by wording not NCT count (S5.2)
# A retrospectively designed analysis of trial cohorts (S5.2, alongside post-hoc
# and secondary analyses). "Clinical characteristics and outcome of localized
# GN/GNBI were retrospectively compared to localized neuroblastoma ... registered in
# the German neuroblastoma trials" concludes "Chemotherapy is not effective" -- a
# statement about a tumour subtype, not about either registered trial's endpoint.
# Matched on the design statement rather than on the bare word, so a prospective
# trial that merely mentions retrospective literature is not excluded.
RETRO_BODY = re.compile(
    r"\bretrospectiv(?:e|ely)\s+(?:compar|analy[sz]|review|examin|assess|evaluat|"
    r"collect|identif|abstract|extract)"
    r"|\ba retrospectiv\w*\s+(?:analys|review|stud|cohort|comparison|chart|audit|"
    r"evaluation|series)"
    r"|\bretrospectiv\w*\s+(?:analys[ie]s|review|study|cohort study|chart review)"
    r"\s+(?:of|was|were)", re.I)

POOLED_BODY = re.compile(
    r"(?:among|across|of) (?:the )?\d{1,3} (?:[\w-]+ ){0,3}?"
    r"(?:trials|studies|rcts)\b"
    r"|\d{1,3} (?:trials|studies) (?:were (?:included|identified|analy[sz]ed)|met the)"
    r"|we (?:identified|included|analy[sz]ed) \d{1,3} (?:trials|studies)"
    r"|(?:phase [iv1-3]{1,3}|clinical|randomi[sz]ed|subsequent|later|most|many|numerous|"
    r"several|prior|previous)(?: \w+){0,2} trials (?:have|had|were|largely|mostly|"
    r"generally|consistently|repeatedly)"
    r"|trials (?:have|had) (?:largely|mostly|generally|consistently|so far|thus far|"
    r"to date|repeatedly)"
    # a pooled analysis names no NCT count and says so in words instead: "data were
    # pooled from phase 3 trials". Without this the pooled report of five basal-insulin
    # trials failed all five on a population-selection sentence.
    r"|data (?:were|was) pooled (?:from|across)"
    r"|pooled (?:patient[- ]level |individual )?(?:data|analys[ei]s) (?:from|of|were|was)"
    r"|using pooled data", re.I)

# sub-study / mechanistic papers: may support Positive, never produce Negative (S5.8)
SUBSTUDY_TITLE = re.compile(
    r"\b(?:as a probe|receptor occupancy|mechanis(?:m|tic)|proof of mechanism|"
    r"pharmacodynamic(?:s)? (?:of|study)|signal(?:l)?ing|immunogenicity|"
    r"metabolom|proteom|transcriptom|lipidom|"
    r"gastric emptying|gallbladder|bone turnover|bone marker|"
    r"plasma (?:level|concentration)s? of|serum (?:level|concentration)s? of|"
    r"effects? on (?:plasma|serum|circulating)|"
    r"biomarker|biodistribution|dosimetry|tracer|microdialysis|"
    r"endothelial function|flow[-\s]?mediated|microcirculation|microvascular (?:function|reactivity))", re.I)

BIOMARKER_TITLE = re.compile(
    r"\b(?:plasma|serum|circulating|urinary|salivary|cerebrospinal|"
    r"hormone|cytokine|lipid|lipoprotein|cholesterol|triglyceride|"
    r"glucagon|insulin secretion|c-peptide|renin|aldosterone|cortisol|"
    r"osteocalcin|CTX|P1NP|adiponectin|leptin|ghrelin|gene expression|"
    r"receptor (?:binding|density)|pharmacokinetic)", re.I)

# An association / correlation / prediction paper is not an endpoint report: it asks
# whether a marker tracks a measure, not whether the drug worked. Found by hand-read
# (S9.2): "Epigenetic age acceleration is not strongly associated with cardiorespiratory
# fitness in heart failure" failed its trial on a sentence about a methylation clock.
# Used only with CLIN_ENDPOINT_TITLE absent, so a titled RCT is never gated away.
ASSOC_TITLE = re.compile(
    r"\b(?:(?:is|are|was|were|not)\s+(?:\w+\s+){0,2}associated with|association (?:of|between|with)|"
    r"correlat(?:es?|ed|ion)\b|predict(?:s|ive|or|ion)?\b|"
    r"as an? (?:marker|predictor|surrogate|proxy)(?: end ?point| marker)? (?:of|for)|"
    r"surrogate (?:end ?point|marker|measure)s? (?:of|for)|"
    r"relationship (?:between|of|to)|epigenetic|methylation|DNA ?m\b)", re.I)

HEALTHY_RE = re.compile(r"\bhealthy (?:volunteer|subject|male|female|men|women|particip|adult|control)", re.I)

CLIN_ENDPOINT_TITLE = re.compile(
    r"\b(?:efficacy|effectiveness|safety|survival|mortality|outcome|"
    r"randomi[sz]ed|phase (?:1|2|3|i{1,3})|placebo[-\s]?controlled|"
    r"non[-\s]?inferiority|superiority|HbA1c|glycaemic control|glycemic control|"
    r"weight loss|pain|fracture|exacerbation|relapse|remission|response rate)", re.I)

# S5.8 condition 3 reads the clinical-endpoint vocabulary strictly. A bare "outcome"
# is too weak to establish that a prediction-shaped title is an endpoint report: "A
# clinical measure of DNA methylation predicts outcome in de novo AML" cleared the gate
# on that one word and failed the trial it was nested in (S9.2). Everything here is
# either a design word or a named clinical endpoint, so a titled randomised efficacy
# report still never reaches the gate.
CLIN_ENDPOINT_STRICT = re.compile(
    r"\b(?:efficacy|effectiveness|safety|randomi[sz]ed|phase (?:1|2|3|i{1,3})|"
    r"placebo[-\s]?controlled|non[-\s]?inferiority|superiority|primary (?:end ?point|outcome)|"
    r"(?:overall|progression[-\s]?free|event[-\s]?free|disease[-\s]?free|relapse[-\s]?free) survival|"
    r"mortality|HbA1c|glyca?emic control|weight loss|fracture|exacerbation|"
    r"relapse|remission|response rate)\b", re.I)

# ---------------------------------------------------------------- sentence filters (S5.4)
SKIP_SENT = re.compile(
    r"^(?:(?:when|if|whenever|for (?:those|patients)) [^,.]{0,80}(?:end ?point|outcome|response|target|goal) (?:was|were) not (?:achieved|met|reached|attained)|"
    r"the (?:aim|objective|purpose|goal)|our (?:aim|objective|goal)|"
    r"we (?:aimed|sought|hypothesi[sz]ed|conducted|performed|designed|describe|report here)|"
    r"this (?:study|trial|analysis|paper|report) (?:aim|was designed|describes|evaluat|assess|examin|investigat)|"
    r"(?:to|in order to) (?:assess|evaluate|determine|investigate|examine|compare|study|explore)|"
    r"background|introduction|objective|aim|purpose|method|design|setting|"
    r"participants were (?:recruited|enrol?led|eligible)|"
    r"(?:eligible|inclusion|exclusion) (?:patients|criteria|subjects)|"
    r"(?:baseline|demographic) characteristics|"
    r"(?:previous|prior|earlier) (?:studies|trials|reports|work)|"
    r"(?:further|future|additional|larger|longer) (?:studies|trials|research|investigation)|"
    r"(?:we|the authors) (?:believe|suggest that future|recommend that future)|"
    r"(?:in|among) (?:mice|rats|rabbits|dogs|animals))", re.I)

# S5.4: a sentence reporting an animal experiment is not a trial result. The
# invertebrate models were missing, so "in the worm study, showed a weak but
# significant increase in lifespan" was deciding a human trial (S9.3, animal
# experiments).
ANIMAL_SENT = re.compile(r"\b(?:mice|mouse|rats?|murine|rabbits?|canine|porcine|"
                         r"worms?|c\.? ?elegans|caenorhabditis|drosophila|nematodes?|"
                         r"zebrafish|in vitro|ex vivo)\b", re.I)

EXPLORATORY_SENT = re.compile(
    r"\b(?:post[-\s]?hoc|exploratory|subgroup|sub[-\s]?group|sensitivity analys|"
    r"in a subset|among (?:those|patients) who|secondary (?:end ?point|outcome|analys)|"
    r"\bper[-\s]?protocol analys)", re.I)

# endpoint-definition sentences, allowed only with a result verb (S5.4)
# A conditional protocol clause: "When the primary end point was not achieved,
# methotrexate was increased to 25 mg". It states a per-patient escalation RULE,
# not this trial's result. It matters because a sentence splitter will not break
# after "at week 8." (digit-period, protected so decimals survive), so the clause
# gets absorbed into the endpoint-DEFINITION sentence ahead of it, and its
# "achieved" then satisfies the S5.4 result-verb escape hatch -- turning a methods
# passage into a confident endpoint failure.
# A dose-titration action: "methotrexate was increased to 25 mg", "the dose was
# reduced to 2.5 mg/kg/d". The verb is a S5.4 RESULT_VERB, so without this a
# dosing sentence in the methods clears the endpoint-definition escape hatch.
DOSE_ACTION = re.compile(
    r"\b(?:was|were|be)\s+(?:then\s+|further\s+|subsequently\s+)?"
    r"(?:increased|reduced|decreased|escalated|de[-\s]?escalated|titrated|"
    r"up[-\s]?titrated|down[-\s]?titrated|doubled|halved|adjusted|adapted|raised|"
    r"lowered|adminstered|administered)\s+"
    r"(?:to|from|by|up to|down to)?\s*\d[\d.,]*\s*"
    r"(?:mg|g|mcg|microgram|ug|\u00b5g|iu|units?|ml|mmol|nmol|%)\b[^,.;]{0,40}",
    re.I)

# A patient-disposition or eligibility clause: "There were 298 patients who did
# not meet the randomization criteria", "33 (8.1%) did not meet the inclusion
# criteria and were excluded", "those who did not achieve a remission had a median
# peak blood CAR level of ...". Each carries a negative-endpoint phrase whose
# subject is a group of patients, not the trial's endpoint. SKIP_SENT holds the
# eligibility vocabulary but is anchored at "^", so a clause arriving mid-sentence
# -- which is where these almost always arrive -- goes straight through it and
# fails a trial on its screening log.
DISPOSITION_CLAUSE = re.compile(
    r"\b(?:did|do|does|had|have) not\s+(?:meet|met|achieve|achieved|reach|reached|"
    r"attain|attained|fulfil|fulfill|fulfilled|satisfy|satisfied)\s+"
    r"(?:the\s+|all\s+|any\s+(?:of\s+the\s+)?|our\s+|these\s+|study\s+|"
    r"protocol\s+|pre[-\s]?defined\s+|predefined\s+)*"
    r"(?:inclusion|exclusion|eligibility|entry|enrol?ment|randomi[sz]ation|"
    r"screening|selection)\s+criteri\w*"
    r"|\b(?:patients?|subjects?|participants?|women|men|individuals?|cases?|those|"
    r"responders?|non[-\s]?responders?)\s+(?:who|that)\s+"
    r"(?:(?:did|had) not\s+(?:meet|met|achieve|achieved|reach|reached|attain|attained)"
    r"|(?:had\s+)?fail(?:ed|s)?\s+to\s+(?:meet|achieve|reach|attain|respond))"
    r"\b[^,.;]{0,60}"
    r"|\b(?:because of|due to|after|following|owing to)\s+(?:either\s+)?"
    r"(?:failure to (?:achieve|respond|reach|meet)|loss of (?:adequate\s+)?"
    r"(?:clinical\s+)?response)\b[^,.;]{0,60}",
    re.I)

# A clause whose subject is somebody else's trial: "Other studies failed to show
# significant benefits with the addition of ...", "Although study 303 failed to
# demonstrate equivalence, ...", "trials in these diseases with IL-2 that did not reach
# their primary end points". SKIP_SENT holds the prior-literature vocabulary but is
# anchored at "^" and lists only previous/prior/earlier, so these went straight through
# and failed the trial on a sentence about the literature. Clipped at the next comma, so
# the host sentence's own main clause survives. The lookbehinds keep "this trial that did
# not reach its primary endpoint" -- the trial's own report -- out of it.
OTHER_STUDY_CLAUSE = re.compile(
    r"\b(?:other|another|previous|prior|earlier|several|many|numerous|recent|"
    r"subsequent|later|published)\s+(?:\w+\s+){0,2}?"
    r"(?:stud(?:y|ies)|trials?|reports?|analys[ie]s|rcts)\b[^,.;]{0,80}"
    r"|\bstud(?:y|ies)\s+\d{2,4}\b[^,.;]{0,80}"
    r"|(?<!this )(?<!our )(?<!present )\b(?:trials|studies)\b[^,.;]{0,60}?"
    r"\bthat\s+(?:did not|failed to|had not)\b[^,.;]{0,70}", re.I)

# A stop whose stated reason is administrative: recruitment, funding, a sponsor decision,
# a drug programme being discontinued. The task records every registry-status stop under
# its own label (S4), but a stop reported only in a PAPER, on a trial the registry calls
# Completed, is being read here as a reported endpoint failure -- and "enrollment was
# stopped owing to very slow patient accrual" says nothing about the drug. Dropped to
# neutral unless the sentence also gives a substantive reason.
ADMIN_STOP_REASON = re.compile(
    r"\b(?:slow|poor|low|insufficient|inadequate|limited|lack of|difficult\w*)\s+"
    r"(?:\w+\s+){0,2}?(?:accrual|recruitment|enrol?ment|uptake|participation)"
    r"|\b(?:accrual|recruitment|enrol?ment)\s+(?:rate\s+)?(?:was\s+|were\s+)?"
    r"(?:slow|poor|low|insufficient|challeng\w+|difficult\w*)"
    r"|\bfeasibility of (?:recruitment|enrol?ment|accrual)"
    r"|\b(?:lack|loss|withdrawal|absence) of (?:funding|financial support|sponsor|support)"
    r"|\b(?:administrative|logistic\w*|business|strategic|financial|sponsor(?:'s)?)\s+"
    r"(?:reasons?|decision|considerations?)"
    r"|\bdrug (?:supply|shortage|unavailab\w+)"
    r"|\bdiscontinuation of (?:the )?(?:\w+\s+){0,3}(?:development|manufactur\w+|product|programme?|supply)"
    r"|\bCOVID[-\s]?19 (?:pandemic|restrictions|related)"
    r"|\b(?:principal )?investigator (?:left|departure|relocat\w+)", re.I)

# The reason that makes a stop substantive, matched as a REASON clause rather than as a
# bare word: "a futility analysis was performed because of slow accrual" mentions
# futility but stopped for accrual.
SUBSTANTIVE_STOP_REASON = re.compile(
    r"(?:for|due to|because of|owing to|on grounds of|on the basis of)\s+"
    r"(?:\w+\s+){0,3}?(?:safety|toxicit\w*|adverse|harm\w*|mortalit\w*|deaths?|"
    r"futility|futile|excess\w*|lack of (?:efficacy|benefit|effect|response)|"
    r"(?:in)?efficacy|benefit)"
    r"|\b(?:futility|safety|efficacy|harm) (?:boundary|boundaries|criteri\w+|rule|stopping rule)s?"
    r"\s*(?:was |were )?(?:crossed|met|reached|exceeded)"
    r"|\bstopped (?:early )?for (?:futility|safety|efficacy|harm)", re.I)

# The stop vocabulary itself, used to decide whether the two reason lexicons apply at all.
STOP_HIT = re.compile(
    r"\b(?:stopped|terminated|halted|closed|suspended|discontinued|clos(?:ing|ure))\b"
    r"|\b(?:enrol?lment|accrual)\b", re.I)

# An accrual or enrolment stop is a statement about RECRUITMENT. Unlike a trial-level
# stop it is administrative by default, so it needs a substantive reason to count.
ACCRUAL_STOP = re.compile(
    r"\b(?:enrol?lment|accrual|recruitment)\b[^.]{0,40}?"
    r"\b(?:stopped|halted|suspended|terminated|closed|ceased)\b"
    r"|\b(?:stopped|halted|suspended|terminated|closed|ceased)\b[^.]{0,30}?"
    r"\b(?:enrol?lment|accrual|recruitment)\b", re.I)

# A p-value that states the test's own threshold is a METHODS statement: "with a
# significance level of p=0.10", "false discovery rate corrected at P = 0.05". Read as a
# result it failed one trial that met its endpoint and one whose title reports a positive
# finding. Matched in a window around the hit, so a result p-value elsewhere in the same
# sentence still scores.
ALPHA_WINDOW = re.compile(
    r"significance (?:level|threshold)|alpha level|\balpha\b|type I error|"
    r"false discovery rate|\bFDR\b|Bonferroni|Holm|corrected at|"
    r"(?:was|were) set at|considered (?:statistically )?significant|"
    r"statistical significance was (?:set|defined)|powered to", re.I)

# "The statistical analyses failed to show a 'center effect'" is a statement about the
# ANALYSIS, not about the drug: a model-diagnostic check, not an endpoint.
STAT_ARTEFACT = re.compile(
    r"\b(?:failed to (?:show|demonstrate|detect|reveal)|did not (?:show|detect|reveal|"
    r"suggest)|no (?:significant )?evidence of)\s+(?:a |an |any )?"
    r"[\"\u201c\u2018']?(?:\w+[\s-]){0,2}"
    r"(?:cent(?:re|er) effect|cent(?:re|er)[-\s]by[-\s]treatment|interaction|"
    r"heterogeneity|carry[-\s]?over|period effect|non[-\s]?normality|"
    r"departure from|violation of|proportional[-\s]?hazards?|collinearity|"
    r"publication bias|dose[-\s]?response trend|order effect)\b", re.I)

PROTOCOL_COND = re.compile(
    r"\b(?:when|if|whenever|unless|in (?:those|patients|cases))\b"
    r"[^,.;]{0,90}?(?:end ?point|outcome|response|target|remission|goal)s?"
    r"\s+(?:was|were|is|are|had been)\s+not\s+"
    r"(?:achieved|met|reached|attained|obtained)\b\s*,?", re.I)

ENDPOINT_DEF = re.compile(
    r"(?:primary|co-primary|secondary) (?:end ?point|outcome|objective)s? "
    r"(?:was|were|is|are|included|comprised|consisted)", re.I)

RESULT_VERB = re.compile(
    r"\b(?:met|achieved|missed|not met|failed|significant|significantly|"
    r"superior|non[-\s]?inferior|futility|improved|reduced|increased|occurred|"
    r"observed|reported|was reached|were reached)\b|(?:p|P) ?[<>=≤]", re.I)

# biomarker/analyte in subject position: first ~45 chars (S5.4)
ANALYTE_SUBJ = re.compile(
    r"^.{0,45}?\b(?:plasma|serum|circulating|urinary|plasma levels|"
    r"insulin|glucagon|c-peptide|ghrelin|leptin|adiponectin|cortisol|renin|"
    r"aldosterone|testosterone|oestradiol|estradiol|LH|FSH|IGF-?1|"
    r"cytokine|interleukin|IL-?\d|TNF|CRP|"
    r"cholesterol|triglyceride|LDL|HDL|free fatty acid|"
    r"osteocalcin|P1NP|CTX|bone turnover|alkaline phosphatase|"
    r"\d+[-\s]?hydroxyvitamin|vitamin d (?:plasma |serum )?levels?|klotho|receptor occupancy|gene expression|mRNA|AUC|Cmax|Tmax|half[-\s]?life|clearance|"
    r"heart rate|pulse rate|HOMA|insulin resistance|insulin sensitivity)\b", re.I)

# A count or proportion of PATIENTS in subject position ahead of an endpoint verb:
# "Three subjects (30%) achieved the primary endpoint", "27.5 and 25.6% of patients
# reached the primary outcome", "Two of six patients achieved the primary outcome".
# Each is a response rate, not a statement that the trial met its endpoint -- and
# read as one it turns a 30% responder rate into a met endpoint. The mirror of
# DISPOSITION_CLAUSE on the positive side.
COUNT_SUBJ = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s*%|\b\d{1,4}\b|"
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|none|neither)\b)"
    r"[^.]{0,45}?\b(?:subjects?|patients?|participants?|children|women|men|cases?|"
    r"recipients?|volunteers?)\b[^.]{0,25}$", re.I)

PRIMARY_SENT = re.compile(r"(?:primary|co-primary) (?:end ?point|outcome)", re.I)

CONCL_MARK = re.compile(
    r"(?:^|[.\s])(?:conclusions?|interpretation|in conclusion|in summary|"
    r"to conclude|summary|clinical implications?)\s*[:.\-—]?\s*", re.I)

# S5.6.1 negation guard
NEG_GUARD = re.compile(
    r"\b(?:no|not|non|without|neither|nor|lack of|lacked|absence of|absent|"
    r"never|none|cannot|could not|did not|does not|was not|were not|failed to show)\b", re.I)

# S5.6.2 safety-context subject
SAFETY_SUBJ = re.compile(
    r"^.{0,70}?\b(?:adverse event|adverse effect|side effect|safety|tolerability|"
    r"toleration|hypoglyca?emia|discontinuation|withdrawal|dropout|drop[-\s]?out|"
    r"mortality|death|serious adverse|toxicit|injection[- ]site|nausea|vomiting|"
    # named adverse events are safety subjects too: "Neutropenia did not increase
    # significantly in the dd groups" is a tolerability finding, not an endpoint miss
    r"neutropenia|thrombocytopenia|ana?emia|leukopenia|lymphopenia|pancytopenia|"
    r"mucositis|neuropathy|pyrexia|pruritus|rash|diarrh(?:oe|e)a|fatigue|headache|"
    r"hepatotoxicity|nephrotoxicity|"
    r"treatment-emergent|SAEs?|TEAEs?|AEs)\b", re.I)

EFFICACY_WORD = re.compile(
    r"\b(?:efficacy|effective|primary end ?point|primary outcome|HbA1c|"
    r"response rate|survival|progression|remission|reduction in (?:weight|pain)|"
    r"improvement in)\b", re.I)

NO_DIFF = re.compile(
    r"(?:no (?:statistically )?significant|not (?:statistically )?significant|"
    r"did not differ|no difference|comparable|similar|equivalent|"
    r"within the (?:pre[-\s]?specified |accepted )?(?:limits|margin|range|bounds)|"
    r"90% (?:confidence interval|CI)s? (?:were|was|fell) within)", re.I)

# stems, not whole words: a `\b`-style exact form here misses "increase" and
# "rise", and the direction check (S5.6.4) then silently never fires on them.
HIGHER_BAD = re.compile(
    r"(?:significantly |markedly |substantially |clinically )?(?:higher|greater|"
    r"increase(?:d|s|ing)?|more frequent|more common|elevat(?:ed|ion)|excess|"
    r"ris(?:e|es|ing|en)|worsen(?:ed|ing)?)", re.I)

# S5.6.4 direction check
WORSE_OBJ = re.compile(
    r"\b(?:hyperglyca?emia|hypoglyca?emia|glycemia|glycaemia|mortality|death|"
    r"risk|adverse event|adverse effect|toxicit|impairment|progression|relapse|"
    r"pain|exacerbation|hospitali[sz]ation|complication|infection|bleeding|"
    r"fracture|discontinuation|dropout|withdrawal|side effect|failure|"
    r"dysfunction|disease activity|flare|rejection|seizure|"
    r"nausea|vomiting|diarrh|injection[- ]site)\b", re.I)

BETTER_OBJ = re.compile(
    r"\b(?:improvement|improved|reduction|reduced|decrease|weight loss|control|"
    r"response|remission|survival|clearance|cure|efficacy|benefit|"
    r"recovery|(?<![-\w])healing|adherence|quality of life|satisfaction|"
    r"bone (?:mineral )?density|eradication|tolerability)\b", re.I)

# S5.6.5 equivalence re-reading
EQUIV_STUDY = re.compile(
    r"\b(?:pharmacokinetic|pharmacodynamic|bioequivalen|bio[-\s]?similar|biosimilar|"
    r"equivalence (?:study|trial)|non[-\s]?inferiority (?:study|trial)|"
    r"\bPK\b|\bPK/PD\b|interchangeab|generic)", re.I)

# S5.6.5, non-inferiority arm: a trial whose primary endpoint met non-inferiority has
# not failed merely because a superiority test did not clear. Superiority was not what
# the trial set out to show, so such a hit is dropped rather than flipped.
NI_MET = re.compile(
    r"\b(?:was|were) non[-\s]?inferior to\b"
    r"|non[-\s]?inferiority (?:was |criteri\w+ (?:was|were) )?"
    r"(?:met|demonstrated|established|achieved|confirmed|shown)\b", re.I)

SUPERIORITY_MISS = re.compile(
    r"\b(?:did )?not (?:demonstrate|show|achieve|reach|establish)\w*\s+superiority\b"
    r"|\bsuperiority (?:was|were) not (?:demonstrated|shown|achieved|met|established)\b"
    r"|\bfailed to (?:demonstrate|show|achieve)\s+superiority\b", re.I)

# S5.6.5: the equivalence re-reading is allowed on a primary-endpoint sentence -- that
# is the very sentence it exists for in a PK/bioequivalence study -- EXCEPT where the
# sentence says the equivalence or non-inferiority goal itself was missed.
EQUIV_FAIL = re.compile(
    r"\b(?:not|failed to)\b[^.]{0,40}\b(?:non[-\s]?inferior|equivalen|bioequivalen)"
    r"|\b(?:non[-\s]?inferiority|equivalence|bioequivalence) (?:was|were) not\b"
    r"|\bdid not (?:meet|achieve|reach)\b", re.I)

# S5.6.2 boundary case: a primary endpoint that IS a harm-rate measure. "No difference
# in percentage of time <4.0 mmol/L (primary outcome)" is not a failed trial, but the
# methodology forbids safety routing over a primary endpoint -- so the hit is dropped to
# neutral (S5.6.4's stated preference) rather than flipped to Positive.
SAFETY_PRIMARY_MEASURE = re.compile(
    r"\btime (?:spent )?(?:below|under|<)\s*(?:range\b|[\d.]+\s*(?:mmol|mg))"
    r"|\bpercentage of time\s*<\s*[\d.]+"
    r"|\btime below range\b"
    r"|\b(?:rate|incidence|frequency|number) of (?:severe |nocturnal |symptomatic )?"
    r"hypoglyca?emi\w*", re.I)

# S5.4 mirrored: a failed primary is never overridden by a positive subgroup, and a
# met primary is not overridden by a missed SECONDARY measure. "...produced significant
# weight loss but did not significantly improve metabolic and blood pressure control"
# reports secondary endpoints in the but-clause of a trial whose primary endpoint
# (bodyweight) was met.
SECONDARY_OBJ = re.compile(
    r"\b(?:blood pressure|systolic|diastolic|lipid|cholesterol|triglyceride|"
    r"metabolic (?:control|parameters|profile)|bone[- ]turnover|quality of life|"
    r"biomarker|inflammatory marker|marker of|markers of)\b", re.I)

# S5.6.1, second exemption: a p-value carries its polarity in its NUMBER, so a negation
# anywhere near it is not a double negative. "the primary endpoint was not met (p = 0.42)"
# flipped the non-significant p-value to positive-efficacy and read as a success.
NUMERIC_POLARITY = tuple(
    p for fam in ("negative-efficacy", "positive-efficacy") for p in FAMILIES[fam]
    if re.search(r"\(\?:p\|P\)", p))

# patterns that already carry their own negation: do not double-flip (S5.6.1)
SELF_NEGATED = tuple(
    p for fam in ("negative-endpoint", "negative-efficacy", "positive-safety",
                  "positive-endpoint", "negative-safety")
    for p in FAMILIES[fam]
    if re.search(r"\b(?:no|not|non[-\s]?inferior|without|lack|failed|did not|futility|miss)", p, re.I))

FLIP = {
    "negative-safety": "positive-safety",
    "positive-safety": "negative-safety",
    "negative-efficacy": "positive-efficacy",
    "positive-efficacy": "negative-efficacy",
    "negative-endpoint": "positive-endpoint",
    "positive-endpoint": "negative-endpoint",
}
