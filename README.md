# Chargeback Sentinel

### AI Chargeback Representment System · Razorpay *AI Risk Manager*

<p align="center">
  <strong>Don't fight every chargeback. Fight the ones you can win.</strong>
</p>

<p align="center">
  <img alt="Defense only" src="https://img.shields.io/badge/scope-defense%20only-0f766e?style=for-the-badge" />
  <img alt="ML" src="https://img.shields.io/badge/score-XGBoost-1e3a5f?style=for-the-badge" />
  <img alt="Policy" src="https://img.shields.io/badge/policy-deterministic-334155?style=for-the-badge" />
  <img alt="LLM" src="https://img.shields.io/badge/LLM-evidence%20only-0ea5e9?style=for-the-badge" />
  <a href="https://razorpay-buildathon-knu4.onrender.com/"><img alt="Live demo" src="https://img.shields.io/badge/demo-live%20on%20Render-22c55e?style=for-the-badge" /></a>
</p>

## Live demo (try it)

| | Link |
|---|---|
| **App (UI + API)** | **[https://razorpay-buildathon-knu4.onrender.com/](https://razorpay-buildathon-knu4.onrender.com/)** |
| Health check | [https://razorpay-buildathon-knu4.onrender.com/api/health](https://razorpay-buildathon-knu4.onrender.com/api/health) |
| API docs | [https://razorpay-buildathon-knu4.onrender.com/docs](https://razorpay-buildathon-knu4.onrender.com/docs) |

**Quick test path:** open the app → click demo cases **1 → 2 → 3** → open **Metrics**.

> Free Render instances may **sleep when idle**. First load can take ~30–60 seconds; refresh once if the page is slow.

> **Honest disclaimer:** The dataset is **synthetic**. It validates the *methodology* (features → score → policy → evidence). It does **not** claim production-level chargeback win rates.

---

## The problem in one glance

```text
 Today (typical desk)                         Chargeback Sentinel
 ┌─────────────────────────┐                  ┌─────────────────────────┐
 │ Fight almost everything │                  │ Score winnability first │
 │ Analyst time wasted     │      ───►        │ Route by policy bands   │
 │ Weak cases clog queues  │                  │ Evidence only if strong │
 │ Strong cases under-docs │                  │ Human still approves    │
 └─────────────────────────┘                  └─────────────────────────┘
```

**Loss class we defend:** *merchant loses money / time by contesting unwinnable disputes (or under-preparing winnable ones).*

---

## Solution approach (how it works)

Three layers. **Only the first two decide.** The LLM never sets the score.

```mermaid
flowchart LR
  A[Chargeback<br/>notification] --> B[Component 1<br/>XGBoost]
  B --> C{P winnable}
  C --> D[Deterministic<br/>policy engine]
  D -->|score &lt; 0.35| E[DO NOT FIGHT]
  D -->|0.35–0.65| F[MANUAL REVIEW]
  D -->|score ≥ 0.65| G[RECOMMEND CONTEST]
  G --> H[Component 2<br/>LLM / template]
  H --> I[Evidence package]
  I --> J[Human review]
  E --> J
  F --> J
  J --> K[Submit or abandon]

  style E fill:#fecaca,stroke:#991b1b,color:#7f1d1d
  style F fill:#fef3c7,stroke:#92400e,color:#78350f
  style G fill:#bbf7d0,stroke:#166534,color:#14532d
  style B fill:#dbeafe,stroke:#1e40af
  style H fill:#e0f2fe,stroke:#0369a9
```

### Who owns what

| Layer | Tool | Job | Sets the tier? |
|---|---|---|---|
| **Score** | XGBoost | `P(winnable \| features)` | Influences |
| **Policy** | Pure Python bands | Map score → action | **Yes** |
| **Evidence** | OpenAI *or* grounded template | Draft representment package | **No** |
| **Explain** | Feature gain signals | “Why this score” | No |
| **Gate** | Human analyst | Final submit / abandon | Final say |

---

## End-to-end system map

```mermaid
flowchart TB
  subgraph INPUT["Inputs"]
    UI[React Live Desk]
    CSV[CSV batch upload]
    SEED[3 demo seeds]
  end

  subgraph API["FastAPI"]
    P["/api/predict"]
    E["/api/generate-evidence"]
    M["/api/metrics"]
  end

  subgraph CORE["Core pipeline"]
    ML[XGBoost artifact]
    POL[Decision engine<br/>0.35 / 0.65 bands]
    LLM[Evidence assembler]
  end

  subgraph OUT["Outputs"]
    TIER[Action + reasons]
    PKG[Evidence package]
    MET[Held-out P/R/PR-AUC]
    AUD[Audit JSONL]
  end

  UI --> P
  CSV --> P
  SEED --> P
  P --> ML --> POL --> TIER
  TIER -->|only RECOMMEND_CONTEST| E --> LLM --> PKG
  M --> MET
  P --> AUD
  E --> AUD
```

---

## Decision policy (visual)

Policy bands are **fixed and auditable** (separate from the binary cost-optimal threshold used only for metrics).

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#f8fafc'}}}%%
flowchart LR
  subgraph BANDS["Winnability score 0 → 1"]
    direction LR
    L["0.00 ——— 0.35<br/><b>DO NOT FIGHT</b><br/>Save analyst time"]
    M["0.35 ——— 0.65<br/><b>MANUAL REVIEW</b><br/>Mixed signals"]
    H["0.65 ——— 1.00<br/><b>RECOMMEND CONTEST</b><br/>Assemble evidence"]
  end

  style L fill:#fecaca,stroke:#991b1b
  style M fill:#fef3c7,stroke:#92400e
  style H fill:#bbf7d0,stroke:#166534
```

| Action | Meaning for the desk |
|---|---|
| `DO_NOT_FIGHT` | Low chance of winning — skip representment |
| `MANUAL_REVIEW` | Ambiguous — analyst inspects before spending time |
| `RECOMMEND_CONTEST` | Stronger case — generate grounded evidence draft |

Hard stop: duplicate chargebacks are never auto-contested.

---

## Model features (what the score actually uses)

Only these **13 fields** enter XGBoost. IDs, tracking text, and policy prose are **blocked from the score** (used later for evidence).

```mermaid
mindmap
  root((MODEL_FEATURES))
    Categorical
      reason_code
      merchant_category
    Boolean 0/1
      delivery_confirmed
      three_d_secure
      device_fingerprint_match
      ip_geolocation_match
      customer_email_opened
    Numeric
      amount
      customer_tenure_days
      customer_prior_disputes
      transaction_velocity_24h
      days_since_transaction
      amount_vs_customer_avg
```

**Leakage blocklist (never in the model):** `won`, archetype name, hidden adjudicator, `tracking_id`, `delivery_timestamp`, `merchant_policy`, dates, IDs.

---

## Data strategy (why metrics are honest)

Labels are **not** a deterministic function of the visible features.

```mermaid
flowchart LR
  A[Archetype prior<br/>win-rate] --> L[Label]
  H[Hidden adjudicator<br/>never a feature] --> L
  N[Noise + ~10%<br/>procedural flips] --> L
  F[Overlapping<br/>feature draws] --> X[Feature vector]
  X --> M[Model]
  L -.->|supervise| M

  style H fill:#fce7f3,stroke:#9d174d
  style N fill:#fce7f3,stroke:#9d174d
```

**Temporal split** (independent RNG seeds):

| Split | Calendar months | Role |
|---|---|---|
| Train | 1–8 | Fit model |
| Validation | 9–10 | Threshold / policy checks |
| **Held-out test** | 11–12 | Evaluated **once** after freeze |

---

## Held-out results (Component 1 — formal)

Temporal test set · n = 1000 · evaluated once after threshold freeze.

| Model | Precision | Recall | F1 | PR-AUC |
|---|---:|---:|---:|---:|
| Rules baseline | 0.55 | 0.37 | 0.45 | 0.47 |
| Logistic regression | 0.57 | 0.69 | 0.62 | 0.56 |
| Decision tree | 0.53 | 0.71 | 0.60 | 0.53 |
| **XGBoost (ours)** | **0.54** | **0.67** | **0.60** | **0.59** |

> Component 2 (LLM) is scored with **proxy** metrics only (schema validity, grounding / unsupported-claim rate). We **do not** claim precision/recall for the LLM.

Full dumps: [`evaluation/`](evaluation/) · decisions: [`docs/`](docs/)

---



## Repository map

```text
Razorpay-buildathon/
├── app/                 # FastAPI — predict, evidence, metrics, audit
├── ml/
│   ├── features/        # Canonical schema + leakage blocklist
│   ├── training/        # Baselines + XGBoost
│   └── artifacts/       # Frozen xgb.joblib + thresholds
├── data/
│   ├── synthetic/       # Archetypes + generator
│   └── splits/          # train / val / test CSVs
├── frontend/            # React + Vite live desk
├── evaluation/          # Held-out metrics JSON
├── docs/                # Architecture, data, FP cost, failures
├── tests/               # Unit tests
├── Dockerfile           # UI build + API in one image
└── README.md            # You are here
```

---

## Quick start

### Local (two terminals)

```bash
# 1) Backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# First time only:
#   python -m data.synthetic.generator
#   python -m ml.training.train --final-test
uvicorn app.main:app --reload --port 8000

# 2) Frontend
cd frontend && npm install && npm run dev
```

- UI: http://127.0.0.1:5173  
- API docs: http://127.0.0.1:8000/docs  

Optional: copy `.env.example` → `.env` and set `OPENAI_API_KEY`.  
Without a key, evidence uses labelled **`template_fallback`** (demo still works).

### One URL (production-style)

```bash
cd frontend && npm run build && cd ..
uvicorn app.main:app --host 0.0.0.0 --port 8000
# → http://127.0.0.1:8000   (UI + /api together)
```

Or: `docker compose up --build` · cloud: Docker service + health `/api/health` (see `render.yaml`).

---

## Safety & scope

| Allowed | Not in scope |
|---|---|
| Defend merchant representment decisions | Offense / fraud-injection tooling |
| Score + route + draft evidence | Auto-submit without human review |
| Synthetic methodology evaluation | Claiming live scheme win rates |

Built for a student hackathon demonstration — **defense only**.
