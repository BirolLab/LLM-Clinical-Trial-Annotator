"""The seven inputs of failure_methodology.md section 0, in one place."""
import os

ROOT = "/projects/btl/ezhang/ctg_lookup/ctg_api_out"
WORK = os.path.join(ROOT, "failure_pipeline", "work")

# 1. corpus
CORPUS_GLOB = os.path.join(ROOT, "bundles_chunks", "chunk_*.md")

# 2. registry
CTG_API = "https://clinicaltrials.gov/api/v2/studies"

# 3. outcome determination
OUTCOME_CSV = os.path.join(ROOT, "outcome_10_20_2026.csv")
OUTCOME_ID_COL = "NCT Number"
OUTCOME_COL = "Outcome"
OUTCOME_NEGATIVE = "Negative"
# Outcome == "Unknown" means nothing on record settled it, i.e. no determination.
OUTCOME_NODETERMINATION = "Unknown"

# 4. label set -- none exists for this corpus.
LABEL_CSV = None

# 5. target vocabulary, spelled exactly as the requester spelled it.
RECRUITMENT = "Recruitment issues"
BUSINESS    = "Business reasons"
INEFFECTIVE = "Ineffective for purpose"
TOXIC       = "Toxic/unsafe"
COVID       = "Due to COVID-19 pandemic"
RESIDUAL    = "Unknown"
VOCAB = [RECRUITMENT, BUSINESS, INEFFECTIVE, TOXIC, COVID, RESIDUAL]

# 6. output schema, in the requester's spelling
OUT_CSV = os.path.join(ROOT, "failure_10_21_2026.csv")
OUT_COLS = ["NCT Number", "Reason for Failure", "Confidence", "Evidence"]
SIDECAR_CSV = os.path.join(ROOT, "failure_pipeline", "failure_10_21_2026_sidecar.csv")
SIDECAR_COLS = ["NCT Number", "Reason for Failure", "Confidence", "Basis",
                "Registry Status", "Upstream Outcome", "In Failure Set",
                "Status Prior", "Sub-reason", "Located Not Adopted", "Rule", "Evidence"]

# 7. scoring metric -- unstated by the requester, and no label set exists.
#    Per section 1.2a: ship residual-filled, carry the prior in the sidecar so the
#    other variant is one line away.
RESIDUAL_FILLED = True

# section 3 regimes
STOPPED_EARLY = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}
RAN_ON = {"COMPLETED", "UNKNOWN"}

# section 7.2 status-conditioned priors
STATUS_PRIOR = {
    "COMPLETED": INEFFECTIVE,
    "UNKNOWN": INEFFECTIVE,
    "TERMINATED": BUSINESS,
    "WITHDRAWN": BUSINESS,
    "SUSPENDED": BUSINESS,
}
STATUS_PRIOR_DEFAULT = BUSINESS   # still-recruiting / active: section 7.2, barely supported
