# Agent Annotate — Standalone

**Publication-grade clinical-trial annotation with a local multi-agent LLM pipeline.**

Agent Annotate takes a list of [ClinicalTrials.gov](https://clinicaltrials.gov)
NCT IDs and produces structured, evidence-backed annotations for each trial —
running entirely on your own machine against models served by
[Ollama](https://ollama.com). No data leaves your host except read-only queries
to public research APIs.

This is the **standalone** repackaging: a single self-contained FastAPI service
with no external auth, no sibling services, and a one-command installer. It runs
on any machine that can run the models (macOS, Linux, or Windows).

---

## What it does

For each trial it answers six fields, each backed by cited evidence:

| Field | Question |
|-------|----------|
| `classification` | Is the intervention an antimicrobial peptide (AMP) or not? |
| `peptide` | Is the drug a peptide, and what is its sequence/identity? |
| `sequence` | The amino-acid sequence, when identifiable. |
| `delivery_mode` | How is it administered (IV, topical, oral, …)? |
| `outcome` | Did the trial succeed, fail, or is the outcome unknown? |
| `reason_for_failure` | If it failed, why? |

The pipeline works in three stages:

1. **Research** — ~25 parallel agents query public databases
   (ClinicalTrials.gov, PubMed/PMC, FDA, UniProt, ChEMBL, RCSB PDB, DRAMP,
   DBAASP, SEC EDGAR, NIH RePORTER, and more) and collect evidence.
2. **Annotation** — a primary LLM proposes each field from the evidence.
3. **Blind multi-model verification** — three different model families
   independently verify each annotation from distinct adversarial personas
   (conservative / evidence-strict / adversarial), and a reconciler resolves
   disagreements. This cognitive diversity is what makes the output
   publication-grade.

> Deep technical detail lives in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) and
> the end-user walkthrough in [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

---

## Requirements

- **OS:** macOS, Linux, or Windows 10/11 (PowerShell).
- **Python:** 3.10 or newer (3.11 / 3.12 recommended for the widest wheel support).
- **[Ollama](https://ollama.com):** installed automatically by the installer.
- **RAM:** the default **`mac_mini`** model profile fits comfortably in **16–24 GB**.
  The optional **`server`** profile needs **240 GB+**.
- **Disk:** ~25–30 GB for the default models.
- **Network:** outbound HTTPS to public research APIs (see
  [Network egress](#network-egress)). The API boots fine offline, but
  annotation jobs need internet.

---

## Quick start

### macOS / Linux

```bash
git clone <this-repo-url> agent-annotate
cd agent-annotate
git checkout birollabs-migration

./install.sh        # installs Ollama + models + Python deps  (use --server for big models)
./run.sh            # starts the API on http://127.0.0.1:9005
```

### Windows (PowerShell)

```powershell
git clone <this-repo-url> agent-annotate
cd agent-annotate
git checkout birollabs-migration

.\install.ps1       # installs Ollama + models + Python deps  (-Server for big models)
.\run.ps1           # starts the API on http://127.0.0.1:9005
```

Verify it's up:

```bash
curl http://127.0.0.1:9005/api/health
# {"status":"ok"}
```

Open `http://127.0.0.1:9005/` in a browser for the bundled web UI.

---

## What the installer does

`install.sh` / `install.ps1` is idempotent — safe to re-run. It:

1. Finds a suitable Python (3.10+).
2. Installs **Ollama** if it isn't already present.
3. Starts the Ollama server and waits for it to be reachable.
4. Pulls the LLM models for the chosen profile (see below).
5. Creates a `.venv` virtualenv and installs `requirements.txt`.
6. Creates the runtime directories (`results/…`, `logs/`).
7. Copies `.env.example` → `.env` (if you don't already have one).

You can re-pull a single model anytime with `ollama pull <model>`.

---

## Models & hardware profiles

The pipeline's model selection lives in
[`config/default_config.yaml`](config/default_config.yaml) under
`orchestrator.hardware_profile`. Two profiles ship:

### `mac_mini` (default — 16–24 GB RAM)

| Role | Model |
|------|-------|
| Primary annotator + reconciler (all 6 fields) | `qwen3:14b` |
| Annotator / verifier (adversarial) | `llama3.1:8b` |
| Verifier (conservative) | `gemma3:12b` |
| Verifier (evidence-strict) | `qwen3:8b` |

`./install.sh` pulls exactly these four.

### `server` (optional — 240 GB+ RAM)

Premium reasoning model (`kimi-k2-thinking`) for the hardest fields plus larger
verifiers (`gemma2:27b`, `qwen2.5:32b`, `phi4:14b`). Install with
`./install.sh --server` and set `hardware_profile: "server"` in the config.

> Missing models are also auto-pulled by the app on first use, but a cold pull
> mid-job can be slow — pre-pulling via the installer avoids first-job timeouts.

---

## Using the API

The API is **open** (no authentication). By default it accepts **any** valid
NCT ID (`NCT` followed by 8 digits). Jobs are queued and processed one at a time.

### 1. Submit a job

```bash
curl -s -X POST http://127.0.0.1:9005/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{"nct_ids": ["NCT04545749", "NCT03680742"]}'
```

```json
{ "job_id": "a1b2c3d4e5f6", "status": "queued", "total_trials": 2, "queue_position": 0 }
```

### 2. Poll job status

```bash
curl -s http://127.0.0.1:9005/api/jobs/a1b2c3d4e5f6
# full job record incl. status: queued → running → completed (per-trial progress)

# live pipeline view (which agent is running on which trial):
curl -s http://127.0.0.1:9005/api/status/pipeline/a1b2c3d4e5f6
```

### 3. Fetch results

```bash
curl -s http://127.0.0.1:9005/api/results/a1b2c3d4e5f6              # full JSON
curl -s http://127.0.0.1:9005/api/results/a1b2c3d4e5f6/summary     # summary
curl -sOJ http://127.0.0.1:9005/api/results/a1b2c3d4e5f6/csv       # download CSV
```

### Common endpoints

| Method & path | Purpose |
|---------------|---------|
| `GET  /api/health` | Liveness probe. |
| `POST /api/jobs` | Create/queue a job (`{"nct_ids": [...]}`). |
| `GET  /api/jobs` · `GET /api/jobs/{id}` | List jobs · job detail. |
| `POST /api/jobs/{id}/cancel` · `/resume` | Cancel · resume a job. |
| `GET  /api/status/pipeline/{id}` | Live per-trial pipeline status. |
| `GET  /api/results/{id}` · `/csv` · `/summary` | Results JSON · CSV · summary. |
| `GET  /api/status/models` | Models available in Ollama. |
| `GET/PUT /api/settings` · `POST /api/settings/reload` | Runtime config. |
| `GET  /api/review` · `POST /api/review/{job}/{nct}/{field}` | Human review queue / corrections. |
| `GET  /api/agreement/*` | Inter-rater concordance analytics (needs the GT dataset). |

Interactive API docs are always available at
`http://127.0.0.1:9005/docs` (Swagger UI).

---

## Configuration

### Environment (`.env`)

Copy `.env.example` to `.env`. Everything is optional:

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_ANNOTATE_PORT` | `9005` | App's self-reported port (diagnostics). |
| `OLLAMA_HOST` / `OLLAMA_PORT` | `localhost` / `11434` | Where Ollama is served. |
| `OLLAMA_TIMEOUT` | `600` | Max seconds per LLM call. |
| `PUBMED_API_KEY` | — | NCBI key → 10 req/s (vs 3). |
| `OPENALEX_EMAIL` / `CROSSREF_EMAIL` | — | "Polite pool" contact emails. |
| `CORS_ORIGINS` | `localhost:5173,9005` | Browser origins allowed to call the API. |

### Pipeline (`config/default_config.yaml`)

Models, the research/annotation agent graph, evidence thresholds, verifier
personas, per-model timeouts, and `hardware_profile`. Edit and call
`POST /api/settings/reload` (or restart) to apply.

### Binding host/port

```bash
HOST=0.0.0.0 PORT=8080 ./run.sh        # listen on all interfaces, port 8080
```

---

## Optional: enable scoring & concordance

The human ground-truth dataset (`docs/human_ground_truth_train_df.csv`) is a
**dataset, not code**, so it is not shipped. Without it:

- ✅ You can annotate **any** NCT ID.
- ⚠️ The `/api/agreement/*` concordance endpoints and EDAM accuracy-scoring are
  inert (they degrade gracefully and log a warning).

To enable scoring/concordance, drop your ground-truth CSV at
`docs/human_ground_truth_train_df.csv`. When present, job submission is
restricted to the trials in that CSV (the scoreable set) and the concordance
analytics light up.

---

## Project layout

```
.
├── app/                  # FastAPI service: routers, services, models, prebuilt SPA
│   ├── main.py           #   ASGI entrypoint (app.main:app)
│   ├── config.py         #   env + path configuration
│   ├── routers/          #   /api/* endpoints
│   └── services/         #   orchestrator, ollama client, persistence, memory (EDAM)
├── agents/               # research + annotation + verification agents
├── config/               # default_config.yaml (the pipeline definition)
├── frontend/             # React/Vite source for the web UI (prebuilt copy in app/static/spa)
├── scripts/              # dev/eval tooling (scoring, slice-builders, regression tests)
├── docs/                 # methodology, paper, strategy, user guide, business docs
├── install.sh / .ps1     # dependency installers
├── run.sh / .ps1         # start the API
├── requirements.txt
└── .env.example
```

Generated at runtime (git-ignored): `results/`, `logs/`, `.venv/`.

---

## Development

- **Run the test suite:** `bash scripts/run_full_regression.sh`
  (source-level trip-wires + versioned regression tests + live API integration
  tests).
- **Score a job vs ground truth:** `python scripts/score_full_corpus.py`
  / `python scripts/compare_jobs.py` (require the GT CSV in `docs/`).
- **Build NCT slices:** the `scripts/pick_*.py` utilities.
- The living development docs are [`CONTINUATION_PLAN.md`](CONTINUATION_PLAN.md),
  [`LEARNING_RUN_PLAN.md`](LEARNING_RUN_PLAN.md), and
  [`docs/AGENT_STRATEGY_ROADMAP.md`](docs/AGENT_STRATEGY_ROADMAP.md).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `503 Ollama is unreachable` on job submit | Start Ollama: `ollama serve`. Confirm `curl localhost:11434/api/tags`. |
| Job stuck at "running" / very slow | First call cold-loads the model. Big models (`qwen3:14b`) take time; raise `OLLAMA_TIMEOUT`. |
| `ollama pull` fails / times out | Re-run `ollama pull <model>`; check disk space and network. |
| Annotation fields all "Unknown" | Likely no internet egress to the research APIs — see below. |
| `Address already in use` | Another process holds the port — `PORT=9006 ./run.sh`. |
| pip install fails on Python 3.13/3.14 | Use Python 3.11 or 3.12: `PYTHON_BIN=$(which python3.12) ./install.sh`. |
| Web UI 404s but `/api/health` works | The prebuilt SPA at `app/static/spa/` is missing; the API still works headless. |

### Network egress

Real annotation queries these public hosts (read-only):
`clinicaltrials.gov`, `api.fda.gov`, `accessdata.fda.gov`,
`eutils.ncbi.nlm.nih.gov` / `pubmed.ncbi.nlm.nih.gov`, `europepmc.org`,
`api.openalex.org`, `api.semanticscholar.org`, `api.crossref.org`, `doi.org`,
`rest.uniprot.org`, `dramp.cpu-bioinfor.org`, `dbaasp.org`, `www.ebi.ac.uk`,
`*.rcsb.org`, `aps.unmc.edu`, `guidetopharmacology.org`, `trialsearch.who.int`,
`api.reporter.nih.gov`, `efts.sec.gov` / `www.sec.gov`, `lite.duckduckgo.com`.
The app boots and health-checks fine without them; only annotation degrades.
