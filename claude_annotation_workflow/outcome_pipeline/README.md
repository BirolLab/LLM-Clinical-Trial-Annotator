# outcome_pipeline

Implements `outcome_methodology.md` against `bundles_chunks/`. Produces
`outcome_10_26_2026.csv` (`NCT Number`, `Outcome`, `Confidence`, `Evidence`).

## Run order

Two later fetch stages read the unresolved set from a prior classify pass, so
classify runs three times (methodology S12):

```
parse_lit -> fetch_status -> fetch_detail -> classify
          -> fetch_extra  -> classify
          -> fetch_epmc2  -> classify -> assemble
```

Validation, none of it optional:

```
python3 -I outcome_pipeline/audit_patterns.py   # S9.1, after every patterns.py edit
python3 -I outcome_pipeline/test_traps.py       # S9.3 trap table as a regression suite
python3 -I outcome_pipeline/score.py            # S9.5, needs a labelled subset
bash     outcome_pipeline/ablate.sh             # S12, measure every switch
```

`assemble.py` asserts the S9.4 invariants and exits non-zero rather than writing
a table that violates one.

## Pointing it at another dataset

| variable | meaning | default |
|---|---|---|
| `BUNDLES` | the `bundles_chunks` directory to parse | `bundles_chunks` |
| `OUTCOME_WORK` | intermediate `work/` files and fetch caches | `outcome_pipeline/work` |
| `OUTCOME_CSV` | output CSV path | `outcome_10_26_2026.csv` |
| `OUTCOME_TRAIN` | labelled subset for `score.py` | `train_df.csv` |
| `EPMC_BY` | decision sources to re-search in the full-text stage | `unknown` |
| `OUTCOME_OFF` | `k5` drop the convention, `k3` drop the failure/sub-study gates, `k4` drop safety routing | all on |
| `OUTCOME_ON` | `k7` loosen the relevance gate for full-text hits | off |

Every fetch stage is cached by NCT id or PMID and is resumable: re-running after
an interruption re-requests nothing. Classification is offline and contains no
network call, because it is re-run dozens of times during validation.
