# Chargeback Sentinel

**AI Chargeback Representment System** for the Razorpay *AI Risk Manager* track.

> Merchants shouldn't fight every chargeback. Our ML model predicts representment winnability, routes disputes deterministically (`DO_NOT_FIGHT` / `MANUAL_REVIEW` / `RECOMMEND_CONTEST`), and uses an LLM only to assemble a grounded evidence package for the strongest cases.

**The dataset is synthetic and is used to validate the system methodology, not to claim production-level chargeback performance.**

## What it does

1. Score a chargeback for **winnability** (XGBoost)
2. Route with a **deterministic decision engine**
3. For `RECOMMEND_CONTEST` only, assemble an **evidence package** (OpenAI if keyed, otherwise grounded template fallback)
4. Keep an **audit log** and show **held-out precision / recall / PR-AUC / FP cost**

Defense-only. No offense tooling. Human review before submission.

## Local development

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt

# Generate synthetic temporal splits + train (first time only)
python -m data.synthetic.generator
python -m ml.training.train --final-test

# API
uvicorn app.main:app --reload --port 8000

# UI (separate terminal) — Vite proxies /api → :8000
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` (UI) and `http://127.0.0.1:8000/docs` (API).

On **Live desk**, use the seeded demo cases or upload a CSV of chargebacks (sample + empty template available in the UI).

Or Windows one-liner for API: `powershell -File scripts/start_api.ps1`

Optional: copy `.env.example` → `.env` and set `OPENAI_API_KEY` for live LLM evidence. Without a key, the desk uses a labelled template fallback.

## Deploy (one URL, UI + API)

Production serves the built React app from FastAPI on a single port. `/api/*` stays on the same origin, so no CORS/proxy issues.

### Prerequisites

1. Trained artifacts present: `ml/artifacts/xgb.joblib`, `evaluation/metrics.json`
2. Optional `.env` with `OPENAI_API_KEY` (template fallback works without it)

### Option A — Docker (recommended)

```bash
# From repo root
docker compose up --build
```

Open `http://127.0.0.1:8000` — full desk UI.  
API docs: `http://127.0.0.1:8000/docs` · health: `/api/health`

### Option B — Build UI, run uvicorn (no Docker)

```bash
cd frontend
npm install
npm run build
cd ..
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Same URL: `http://127.0.0.1:8000`

### Option C — Render / Railway / Fly (cloud)

1. Push this repo to GitHub (include `ml/artifacts/` and `evaluation/metrics.json`).
2. Create a **Docker** web service from the repo root (`Dockerfile`).
3. Set env vars:
   - `OPENAI_API_KEY` (optional)
   - `OPENAI_MODEL=gpt-4o-mini` (optional)
4. Health check path: `/api/health`
5. Open the public URL — UI and API are both there.

A `render.yaml` blueprint is included for [Render](https://render.com).

**Checklist after deploy**

- [ ] `/api/health` returns `"ready": true`
- [ ] Home page loads the Chargeback Sentinel desk
- [ ] Demo cases 1 → 2 → 3 score correctly
- [ ] Metrics tab shows held-out numbers
- [ ] Evidence on case 3 shows `openai` or `template_fallback`

## Evaluation honesty

### Component 1 — ML (formal)

Precision, recall, F1, PR-AUC, confusion matrix, expected-cost threshold curve on a **temporal held-out test set**.

### Component 2 — LLM (proxy only)

Schema validity, completeness, grounding / unsupported-claim rate.  
**Precision/recall are not claimed for the LLM component.**

## Repository map

```text
app/            FastAPI + services (ML, decision, LLM, audit)
ml/             features, baselines, XGBoost, evaluation
data/synthetic  archetype config + generator
data/splits     train/val/test CSVs (generated)
frontend/       React desk UI
docs/           architecture, data strategy, FP economics, failures
evaluation/     metrics JSON + audit log
tests/          unit tests
```

## Demo script (5 minutes)

1. Problem: wasted fights + missed recoveries  
2. Architecture: ML gate → deterministic tiers → LLM only on `RECOMMEND_CONTEST`  
3. Live: three seeds (do not fight / review / contest + evidence)  
4. Metrics page: held-out P/R vs baselines + cost assumptions  
5. Failures / limitations: synthetic data, LLM proxy metrics

## License / safety

Strictly defense-only. Built for a student hackathon demonstration.
