"""
Value + sequence normalization utilities for agent-annotate.

Dependency-free helpers (shared by the scoring/eval dev scripts) for comparing
annotation field values and amino-acid sequences. Extracted from the former
concordance module, which was removed — Agent Annotate is annotation-only.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger("agent_annotate.normalization")

# ---------------------------------------------------------------------------
# Field definitions (CSV column name-based)
# ---------------------------------------------------------------------------
FIELDS = {
    "classification": {"csv_ann1": "Classification_ann1", "csv_ann2": "Classification_ann2", "blank_means_skip": True},
    "delivery_mode": {"csv_ann1": "Delivery Mode_ann1", "csv_ann2": "Delivery Mode_ann2", "blank_means_skip": True},
    "outcome": {"csv_ann1": "Outcome_ann1", "csv_ann2": "Outcome_ann2", "blank_means_skip": True},
    "reason_for_failure": {"csv_ann1": "Reason for Failure_ann1", "csv_ann2": "Reason for Failure_ann2", "blank_means_skip": False},
    "peptide": {"csv_ann1": "Peptide_ann1", "csv_ann2": "Peptide_ann2", "blank_means_skip": True},
    "sequence": {"csv_ann1": "Sequence_ann1", "csv_ann2": "Sequence_ann2", "blank_means_skip": True},
}

# ---------------------------------------------------------------------------
# Value normalisation aliases
# ---------------------------------------------------------------------------
CLASSIFICATION_ALIASES: dict[str, str] = {
    "amp": "AMP", "amp(infection)": "AMP", "amp(other)": "AMP",
    "amp (infection)": "AMP", "amp (other)": "AMP", "other": "Other",
}

DELIVERY_MODE_ALIASES: dict[str, str] = {
    "iv": "Injection/Infusion", "intravenous": "Injection/Infusion",
    "injection/infusion - intramuscular": "Injection/Infusion",
    "injection/infusion - subcutaneous/intradermal": "Injection/Infusion",
    "injection/infusion - other/unspecified": "Injection/Infusion",
    "injection/infusion": "Injection/Infusion",
    "subcutaneous": "Injection/Infusion", "intradermal": "Injection/Infusion",
    "subcutaneous/intradermal": "Injection/Infusion",
    "intramuscular": "Injection/Infusion", "intravitreal": "Injection/Infusion",
    "sc": "Injection/Infusion",
    "oral - tablet": "Oral", "oral - capsule": "Oral", "oral - food": "Oral",
    "oral - drink": "Oral", "oral - unspecified": "Oral", "oral": "Oral",
    "topical - cream/gel": "Topical", "topical - powder": "Topical",
    "topical - spray": "Topical", "topical - strip/covering": "Topical",
    "topical - wash": "Topical", "topical - unspecified": "Topical", "topical": "Topical",
    "inhalation": "Other", "intranasal": "Other",
    "other/unspecified": "Other", "other": "Other",
}

OUTCOME_ALIASES: dict[str, str] = {
    "active": "Active", "active, not recruiting": "Active",
    "active not recruiting": "Active", "recruiting": "Recruiting",
    "failed - completed trial": "Failed - completed trial",
    "positive": "Positive", "terminated": "Terminated",
    "withdrawn": "Withdrawn", "unknown": "Unknown",
}

REASON_ALIASES: dict[str, str] = {
    "business reason": "Business Reason",
    "business_reason": "Business Reason",
    "ineffective for purpose": "Ineffective for purpose",
    "ineffective_for_purpose": "Ineffective for purpose",
    "recruitment issues": "Recruitment issues",
    "recruitment_issues": "Recruitment issues",
    "toxic/unsafe": "Toxic/Unsafe",
    "toxic_unsafe": "Toxic/Unsafe",
    "due to covid": "Due to covid",
    "due_to_covid": "Due to covid",
    "unknown": "Unknown",
}

PEPTIDE_ALIASES: dict[str, str] = {
    "true": "TRUE", "false": "FALSE",
    "yes": "TRUE", "no": "FALSE",
    "1": "TRUE", "0": "FALSE",
}

# ---------------------------------------------------------------------------
# Blank handling standard (universal rule)
# ---------------------------------------------------------------------------
#
# BLANK_HANDLING_STANDARD:
#
# An NCT is considered "annotated" by a human only if at least one of the
# five annotation fields (classification, delivery_mode, outcome,
# reason_for_failure, peptide) has a non-blank value. Rows where all five
# fields are blank/None are treated as unannotated — the annotator was
# assigned the row but did not engage with it.
#
# This applies universally:
#   - Annotator NCT counts: only count rows with at least one filled field
#   - Annotator-filtered concordance: only include annotated rows
#   - Per-field concordance: blank_means_skip=True fields skip when EITHER
#     side is blank. reason_for_failure uses outcome-aware blank handling
#     (blank reason + blank outcome = skipped trial, not "no failure").
#   - Agent annotations always have all 5 fields filled (never blank).
#
# This standard exists because many annotators left large portions of their
# assigned rows blank (e.g., Annotator 4 12%, Annotator 5 7%, Annotator 7 11% coverage). Without
# this filter, annotator counts are inflated and concordance includes
# unannotated trials as false disagreements.
# ---------------------------------------------------------------------------


def _has_any_annotation(field_data: dict[str, str]) -> bool:
    """Check if at least one annotation field has a non-blank value.

    Uses the universal blank handling standard: an NCT is only considered
    annotated if at least one of the five fields is filled.
    """
    for field_name in FIELDS:
        raw = field_data.get(field_name, "")
        _, is_blank = _normalise(raw, field_name)
        if not is_blank:
            return True
    return False


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
def _normalise(value: object, field_name: str) -> tuple[str, bool]:
    """Normalise a value for comparison.

    Returns (normalised_string, is_blank).
    """
    if value is None:
        return ("", True)

    # CSV stores Peptide as string
    if isinstance(value, bool):
        return (str(value).upper(), False)

    s = str(value).strip()
    if s == "" or s.lower() in ("none", "n/a"):
        return ("", True)

    s_lower = s.lower()

    if field_name == "delivery_mode":
        # Multi-value: normalise each part, sort alphabetically
        parts = [p.strip() for p in s.split(",")]
        normalised_parts = []
        for part in parts:
            part_lower = part.strip().lower()
            normalised_parts.append(
                DELIVERY_MODE_ALIASES.get(part_lower, part.strip()).lower()
            )
        normalised_parts.sort()
        result = ", ".join(normalised_parts)
    elif field_name == "outcome":
        result = OUTCOME_ALIASES.get(s_lower, s)
    elif field_name == "classification":
        result = CLASSIFICATION_ALIASES.get(s_lower, s)
    elif field_name == "reason_for_failure":
        result = REASON_ALIASES.get(s_lower, s)
    elif field_name == "peptide":
        result = PEPTIDE_ALIASES.get(s_lower, s)
    else:
        result = s

    # Case-normalize for comparison: uppercase for peptide (TRUE/FALSE),
    # lowercase for everything else
    if field_name == "peptide":
        return (result.upper(), False)
    return (result.lower(), False)


# ---------------------------------------------------------------------------
# Grouped normalisation (simplified categories for high-level comparison)
# ---------------------------------------------------------------------------
def _normalise_grouped(value: str, field_name: str) -> str:
    """Apply grouping to an already-normalised value.

    Reduces granular categories to broad buckets:
    - Classification: AMP(infection)/AMP(other) → AMP
    - Delivery mode: injection subtypes → Injection/Infusion, oral → Oral, etc.
    - Outcome: Active not recruiting/Recruiting → Active
    - Peptide: unchanged (already binary)
    - Reason for failure: unchanged
    - Sequence: unchanged
    """
    if not value:
        return value

    v_lower = value.lower()

    if field_name == "classification":
        if v_lower.startswith("amp"):
            return "AMP"
        return "Other"

    elif field_name == "delivery_mode":
        # Handle multi-value (comma-separated)
        parts = [p.strip().lower() for p in value.split(",")]
        buckets = set()
        for p in parts:
            if "iv" == p or "injection" in p or "infusion" in p or "intravenous" in p or "subcutaneous" in p or "intradermal" in p or "intramuscular" in p:
                buckets.add("Injection/Infusion")
            elif "oral" in p:
                buckets.add("Oral")
            elif "topical" in p:
                buckets.add("Topical")
            elif "inhalation" in p or "inhaled" in p:
                buckets.add("Inhalation")
            else:
                buckets.add("Other")
        return ", ".join(sorted(buckets))

    elif field_name == "outcome":
        if v_lower in ("active, not recruiting", "recruiting"):
            return "Active"
        return value  # Positive, Failed, Terminated, Withdrawn, Unknown stay

    # peptide, reason_for_failure, sequence: no grouping
    return value



# ---------------------------------------------------------------------------
# Sequence-specific normalisation (v23: order-agnostic comparison)
# ---------------------------------------------------------------------------
def _canonicalise_single_sequence(seq: str) -> str:
    """Reduce a single sequence string to its canonical form for comparison.

    Strips: whitespace, hyphens, parenthesised modifications, terminal
    chemistry suffixes (-OH, -NH2, -NH₂), case → uppercase.

    v42.7.16 (2026-04-27): added terminal-suffix stripping. Previously
    "(glp)lyenkprrpyil-oh" canonicalized to "LYENKPRRPYILOH" — the
    naïve hyphen-removal treats "OH" as the AA pair Ornithine-Histidine.
    But "-OH" is a chemistry notation for C-terminal hydroxyl, not an
    AA tail. The agent almost never emits this suffix; GT (manually
    annotated from chemistry papers) often does. A Job #92 example trial's
    sequence miss was exactly this format gap. Stripping the suffix
    before AA-matching closes it.
    """
    s = seq.strip()
    if not s or s.upper() in ("N/A", "NONE", ""):
        return ""
    # Remove parenthesised modifications: (Ac), (NH2), (Glp), etc.
    s = re.sub(r"\([^)]*\)", "", s)
    # v42.7.16: strip terminal chemistry suffixes BEFORE general hyphen
    # removal, because the suffix is hyphen-anchored ("-OH" / "-NH2").
    s = re.sub(r"-(?:NH2|NH₂|OH)\s*$", "", s, flags=re.IGNORECASE)
    # Remove hyphens (format artefact)
    s = s.replace("-", "")
    # Remove spaces
    s = s.replace(" ", "")
    # Uppercase (D-amino acid lowercase → uppercase for canonical)
    s = s.upper()
    return s


def sequences_match(gt_raw: str, pred_raw: str) -> bool:
    """Public helper: does the GT sequence match any canonical sequence
    predicted by the agent? True when the GT canonical is ⊆ pred canonical
    set (i.e. the human-recorded sequence is one of the agent's candidates).

    v42.6.15: lifts measured sequence accuracy without changing agent output.
    Pipeline emits rich data (multiple candidate sequences separated by '|');
    GT is usually a single canonical form. Set-containment is the correct
    match predicate — the agent is right when its set includes GT.

    Returns False if either side is blank/None (non-scoreable — callers
    should filter blanks first to avoid false matches).
    """
    gt_canon, _ = _normalise_sequence_for_comparison(gt_raw)
    pred_canon, _ = _normalise_sequence_for_comparison(pred_raw)
    if not gt_canon or not pred_canon:
        return False
    return gt_canon.issubset(pred_canon)


def _normalise_sequence_for_comparison(
    raw: str,
) -> tuple[frozenset[str], list[str]]:
    """Normalise a sequence field value for order-agnostic comparison.

    Returns:
        (canonical_set, display_list)
        - canonical_set: frozenset of canonical AA strings (uppercase, no mods)
        - display_list: sorted list of original (trimmed) sequence strings
    """
    if raw is None:
        return (frozenset(), [])
    s = str(raw).strip()
    if not s or s.upper() in ("N/A", "NONE"):
        return (frozenset(), [])

    # Split on pipe separator
    parts = [p.strip() for p in s.split("|")]
    parts = [p for p in parts if p]

    canonical_set: set[str] = set()
    display_list: list[str] = []
    for part in parts:
        canon = _canonicalise_single_sequence(part)
        if canon:
            canonical_set.add(canon)
            display_list.append(part)

    display_list.sort()
    return (frozenset(canonical_set), display_list)


