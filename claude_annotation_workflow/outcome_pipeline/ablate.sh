#!/bin/bash
# Measure the method switches (methodology S12): every default is on, and each
# is only trusted if turning it off measurably hurts. Runs against a scratch
# copy of work/ so the shipped calls.json is never touched.
set -e
# resolve the project root from this script's own location, so the ablation runs
# wherever the pipeline is checked out rather than against one machine's path
cd "$(dirname "$(readlink -f "$0")")/.."
SCRATCH=${SCRATCH:-${TMPDIR:-/tmp}/outcome_ablate}
rm -rf "$SCRATCH"; mkdir -p "$SCRATCH"
cp outcome_pipeline/work/*.json "$SCRATCH"/

run () {
  local name="$1"; shift
  echo "=============== $name ==============="
  env "$@" OUTCOME_WORK="$SCRATCH" python3 -I outcome_pipeline/classify.py | sed -n '/outcome/,/^$/p;/decision source/,$p' | head -20
  # agreement needs a labelled subset; without one the label counts above are the
  # only measurement available, so say so rather than failing the run
  if [ -f "${OUTCOME_TRAIN:-train_df.csv}" ]; then
    env OUTCOME_WORK="$SCRATCH" python3 -I outcome_pipeline/score.py \
      | grep -E "pipeline vs Outcome_ann1|pipeline vs Outcome_ann2"
  else
    echo "  (no labelled subset: label counts only, no agreement figure)"
  fi
  echo
}

run "DEFAULT (all switches on)" OUTCOME_OFF=
run "OUTCOME_OFF=k5  (drop default-positive convention)" OUTCOME_OFF=k5
run "OUTCOME_OFF=k3  (drop endpoint-level failure gate + sub-study gate)" OUTCOME_OFF=k3
run "OUTCOME_OFF=k4  (drop safety-context routing)" OUTCOME_OFF=k4
run "OUTCOME_ON=k7   (loosen relevance gate for full-text hits)" OUTCOME_ON=k7
