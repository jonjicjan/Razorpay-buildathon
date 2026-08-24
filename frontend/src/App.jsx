import { useEffect, useMemo, useState } from "react";

const emptyCase = {
  chargeback_id: "cb_live",
  reason_code: "item_not_received",
  merchant_category: "ecommerce",
  amount: 3650,
  delivery_confirmed: 1,
  three_d_secure: 1,
  device_fingerprint_match: 1,
  ip_geolocation_match: 1,
  customer_email_opened: 1,
  customer_tenure_days: 540,
  customer_prior_disputes: 0,
  transaction_velocity_24h: 1,
  days_since_transaction: 16,
  amount_vs_customer_avg: 0.9,
  transaction_date: "2025-11-01",
  dispute_date: "2025-11-17",
  tracking_id: "TRK48291033",
  delivery_timestamp: "2025-11-03 16:40:00",
  merchant_policy:
    "30-day returns on unused goods. Signature on delivery is accepted proof of receipt.",
  duplicate_chargeback: false,
};

const ACTION_COPY = {
  DO_NOT_FIGHT: {
    title: "Do not fight",
    meaning: "Low chance of winning. Save analyst time.",
    next: "No evidence package for this tier.",
  },
  MANUAL_REVIEW: {
    title: "Manual review",
    meaning: "Mixed signals. A human should inspect first.",
    next: "No automatic evidence for this tier.",
  },
  RECOMMEND_CONTEST: {
    title: "Recommend contest",
    meaning: "Stronger winnability. Assemble a representment package.",
    next: "Evidence package can be generated now.",
  },
};

const LO = 0.35;
const HI = 0.65;

function cleanPayload(payload) {
  const next = { ...emptyCase, ...payload, duplicate_chargeback: false };
  for (const key of [
    "tracking_id",
    "delivery_timestamp",
    "merchant_policy",
    "transaction_date",
    "dispute_date",
  ]) {
    if (next[key] === "" || next[key] === undefined) next[key] = null;
  }
  for (const key of [
    "delivery_confirmed",
    "three_d_secure",
    "device_fingerprint_match",
    "ip_geolocation_match",
    "customer_email_opened",
    "customer_tenure_days",
    "customer_prior_disputes",
    "transaction_velocity_24h",
    "days_since_transaction",
  ]) {
    next[key] = Number(next[key] ?? 0);
  }
  if (next.transaction_velocity_24h < 1) next.transaction_velocity_24h = 1;
  if (next.days_since_transaction < 1) next.days_since_transaction = 1;
  next.amount = Number(next.amount);
  if (next.amount_vs_customer_avg === "" || next.amount_vs_customer_avg == null) {
    next.amount_vs_customer_avg = null;
  } else {
    next.amount_vs_customer_avg = Number(next.amount_vs_customer_avg);
  }
  return next;
}

const CSV_COLUMNS = [
  "chargeback_id",
  "reason_code",
  "merchant_category",
  "amount",
  "delivery_confirmed",
  "three_d_secure",
  "device_fingerprint_match",
  "ip_geolocation_match",
  "customer_email_opened",
  "customer_tenure_days",
  "customer_prior_disputes",
  "transaction_velocity_24h",
  "days_since_transaction",
  "amount_vs_customer_avg",
  "transaction_date",
  "dispute_date",
  "tracking_id",
  "delivery_timestamp",
  "merchant_policy",
];

const MAX_CSV_ROWS = 50;

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;
  const pushCell = () => {
    row.push(cell);
    cell = "";
  };
  const pushRow = () => {
    if (row.length > 1 || (row.length === 1 && row[0].trim() !== "")) {
      rows.push(row);
    }
    row = [];
  };

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];
    if (inQuotes) {
      if (ch === '"' && next === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        cell += ch;
      }
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      pushCell();
    } else if (ch === "\n") {
      pushCell();
      pushRow();
    } else if (ch === "\r") {
      // ignore; handle \r\n via \n
    } else {
      cell += ch;
    }
  }
  pushCell();
  pushRow();
  return rows;
}

function coerceBinary(value) {
  if (value == null) return null;
  const v = String(value).trim().toLowerCase();
  if (v === "" || v === "null" || v === "na" || v === "n/a") return null;
  if (["1", "true", "yes", "y"].includes(v)) return 1;
  if (["0", "false", "no", "n"].includes(v)) return 0;
  const n = Number(v);
  return Number.isFinite(n) ? (n ? 1 : 0) : null;
}

function rowToCase(headers, values) {
  const raw = {};
  headers.forEach((h, i) => {
    const key = String(h || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "_");
    if (!key) return;
    const val = values[i] == null ? "" : String(values[i]).trim();
    raw[key] = val === "" || val.toLowerCase() === "null" ? null : val;
  });

  const binaryKeys = [
    "delivery_confirmed",
    "three_d_secure",
    "device_fingerprint_match",
    "ip_geolocation_match",
    "customer_email_opened",
  ];
  for (const key of binaryKeys) {
    if (key in raw) raw[key] = coerceBinary(raw[key]);
  }

  return cleanPayload({
    ...emptyCase,
    ...raw,
    chargeback_id: raw.chargeback_id || `csv_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
  });
}

function casesFromCsv(text) {
  const table = parseCsv(text);
  if (table.length < 2) {
    throw new Error("CSV needs a header row and at least one data row.");
  }
  const headers = table[0];
  const normalized = headers.map((h) =>
    String(h || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "_")
  );
  const required = ["reason_code", "amount"];
  for (const col of required) {
    if (!normalized.includes(col)) {
      throw new Error(`CSV is missing required column: ${col}`);
    }
  }
  const dataRows = table.slice(1, 1 + MAX_CSV_ROWS);
  return dataRows.map((values, idx) => ({
    row: idx + 1,
    case: rowToCase(headers, values),
  }));
}

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
          : text || res.statusText;
    throw new Error(message);
  }
  return data;
}

function fmt(n, digits = 3) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toFixed(digits);
}

function WinGauge({ value }) {
  const v = Math.max(0, Math.min(1, Number(value) || 0));
  const angle = -90 + v * 180;
  const color = v < LO ? "var(--danger)" : v < HI ? "var(--warn)" : "var(--ok)";
  return (
    <div className="gauge" aria-label={`Winnability ${v.toFixed(2)}`}>
      <svg viewBox="0 0 200 120" className="gauge-svg">
        <path
          d="M20 100 A80 80 0 0 1 180 100"
          className="gauge-track"
          fill="none"
        />
        <path
          d="M20 100 A80 80 0 0 1 180 100"
          className="gauge-fill"
          fill="none"
          style={{
            stroke: color,
            strokeDasharray: `${v * 251.2} 251.2`,
          }}
        />
        <line
          x1="100"
          y1="100"
          x2="100"
          y2="28"
          className="gauge-needle"
          style={{
            transform: `rotate(${angle}deg)`,
            transformOrigin: "100px 100px",
            stroke: color,
          }}
        />
        <circle cx="100" cy="100" r="6" className="gauge-hub" />
      </svg>
      <div className="gauge-readout">
        <strong style={{ color }}>{v.toFixed(2)}</strong>
        <span>winnability</span>
      </div>
    </div>
  );
}

function TierTrack({ value, action }) {
  const v = Math.max(0, Math.min(1, Number(value) || 0));
  return (
    <div className="tier-track-wrap">
      <div className="tier-track" aria-hidden="true">
        <div className="tier-zone z-low" style={{ width: `${LO * 100}%` }}>
          <span>Do not fight</span>
        </div>
        <div
          className="tier-zone z-mid"
          style={{ width: `${(HI - LO) * 100}%` }}
        >
          <span>Review</span>
        </div>
        <div className="tier-zone z-high" style={{ width: `${(1 - HI) * 100}%` }}>
          <span>Contest</span>
        </div>
        <div className="tier-marker" style={{ left: `${v * 100}%` }} />
      </div>
      <div className="tier-scale">
        <span>0.00</span>
        <span>0.35</span>
        <span>0.65</span>
        <span>1.00</span>
      </div>
      <p className="tier-caption">
        Score <strong>{v.toFixed(2)}</strong> maps to{" "}
        <strong>{ACTION_COPY[action]?.title || action}</strong> via policy bands.
      </p>
    </div>
  );
}

function SignalBars({ signals }) {
  if (!signals?.length) return <p className="muted">No signals for this run.</p>;
  const max = Math.max(...signals.map((s) => s.gain), 0.001);
  return (
    <div className="bar-list">
      {signals.map((s) => (
        <div key={s.feature} className="bar-row">
          <div className="bar-label">{s.feature}</div>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{ width: `${(s.gain / max) * 100}%` }}
            />
          </div>
          <div className="bar-val">{s.gain.toFixed(1)}</div>
        </div>
      ))}
    </div>
  );
}

function BaselineBars({ baselines }) {
  const rows = [
    { name: "Rule", key: "rule", color: "#64748b" },
    { name: "LogReg", key: "logreg", color: "#3b82a8" },
    { name: "Tree", key: "tree", color: "#2a7a8c" },
    { name: "XGBoost", key: "xgboost", color: "#0f766e" },
  ];
  return (
    <div className="viz-card">
      <h3>PR-AUC by model</h3>
      <p className="viz-sub">Higher is better ranking under class imbalance</p>
      <div className="bar-list tall">
        {rows.map((r) => {
          const val = baselines?.[r.key]?.pr_auc ?? 0;
          return (
            <div key={r.key} className="bar-row">
              <div className="bar-label">{r.name}</div>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{
                    width: `${Math.max(val, 0.02) * 100}%`,
                    background: r.color,
                  }}
                />
              </div>
              <div className="bar-val">{fmt(val)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MetricBars({ row }) {
  if (!row) return null;
  const items = [
    { label: "Precision", value: row.precision },
    { label: "Recall", value: row.recall },
    { label: "F1", value: row.f1 },
    { label: "PR-AUC", value: row.pr_auc },
  ];
  return (
    <div className="metric-bars">
      {items.map((item) => (
        <div key={item.label} className="metric-bar-item">
          <div className="metric-bar-head">
            <span>{item.label}</span>
            <strong>{fmt(item.value)}</strong>
          </div>
          <div className="bar-track">
            <div
              className="bar-fill accent"
              style={{ width: `${Math.max(item.value || 0, 0.02) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function ConfusionViz({ cm }) {
  if (!cm) return null;
  const cells = [
    { key: "tn", label: "True Neg", sub: "Correctly skipped", val: cm.tn, tone: "ok" },
    { key: "fp", label: "False Pos", sub: "Fought & lost", val: cm.fp, tone: "warn" },
    { key: "fn", label: "False Neg", sub: "Missed a win", val: cm.fn, tone: "danger" },
    { key: "tp", label: "True Pos", sub: "Correctly contested", val: cm.tp, tone: "ok" },
  ];
  const max = Math.max(...cells.map((c) => c.val), 1);
  return (
    <div className="cm-grid">
      {cells.map((c) => (
        <div
          key={c.key}
          className={`cm-tile ${c.tone}`}
          style={{ "--intensity": 0.18 + (c.val / max) * 0.55 }}
        >
          <span>{c.label}</span>
          <strong>{c.val}</strong>
          <small>{c.sub}</small>
        </div>
      ))}
    </div>
  );
}

function FlowPipeline({ activeStep }) {
  const steps = [
    { id: 1, label: "Case", sub: "Intake" },
    { id: 2, label: "ML", sub: "Score" },
    { id: 3, label: "Rules", sub: "Tier" },
    { id: 4, label: "Evidence", sub: "Package" },
    { id: 5, label: "Human", sub: "Review" },
  ];
  return (
    <div className="flow">
      {steps.map((step, idx) => (
        <div key={step.id} className="flow-item-wrap">
          <div
            className={`flow-item ${activeStep >= step.id ? "on" : ""} ${
              activeStep === step.id ? "current" : ""
            }`}
          >
            <div className="flow-num">{step.id}</div>
            <div>
              <strong>{step.label}</strong>
              <span>{step.sub}</span>
            </div>
          </div>
          {idx < steps.length - 1 ? <div className="flow-arrow" /> : null}
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("desk");
  const [seeds, setSeeds] = useState([]);
  const [activeSeed, setActiveSeed] = useState(null);
  const [form, setForm] = useState(emptyCase);
  const [decision, setDecision] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("checking");
  const [statusDetail, setStatusDetail] = useState("Checking API…");
  const [batchRows, setBatchRows] = useState([]);
  const [batchProgress, setBatchProgress] = useState("");
  const [csvName, setCsvName] = useState("");

  async function refreshHealth() {
    try {
      const h = await api("/api/health");
      if (h.ready) {
        setStatus("online");
        setStatusDetail("System ready");
      } else {
        setStatus("degraded");
        setStatusDetail("API up · some artifacts missing");
      }
      return h;
    } catch {
      setStatus("offline");
      setStatusDetail("API offline — start backend on :8000");
      return null;
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      const h = await refreshHealth();
      if (cancelled) return;
      try {
        const [seedData, metricData] = await Promise.all([
          api("/api/demo-seeds"),
          api("/api/metrics"),
        ]);
        if (!cancelled) {
          setSeeds(seedData.cases || []);
          setMetrics(metricData);
        }
      } catch (err) {
        if (!cancelled && h) setError(String(err.message || err));
      }
    }
    boot();
    const id = setInterval(refreshHealth, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const activeStep = useMemo(() => {
    if (evidence?.package) return 5;
    if (decision) return decision.action === "RECOMMEND_CONTEST" ? 4 : 3;
    if (busy) return 2;
    return 1;
  }, [decision, evidence, busy]);

  function update(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function runPredict(casePayload = form) {
    setBusy(true);
    setError("");
    setEvidence(null);
    try {
      const result = await api("/api/predict", {
        method: "POST",
        body: JSON.stringify(cleanPayload(casePayload)),
      });
      setDecision(result);
      return result;
    } catch (err) {
      setError(String(err.message || err));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function runEvidence(casePayload = form) {
    setBusy(true);
    setError("");
    try {
      const result = await api("/api/generate-evidence", {
        method: "POST",
        body: JSON.stringify(cleanPayload(casePayload)),
      });
      setEvidence(result);
      if (result.action) {
        setDecision((prev) =>
          prev
            ? { ...prev, action: result.action, winnability: result.winnability }
            : {
                winnability: result.winnability,
                action: result.action,
                reasons: [],
                llm_allowed: result.action === "RECOMMEND_CONTEST",
                hard_stop: false,
                top_signals: [],
              }
        );
      }
      return result;
    } catch (err) {
      setError(String(err.message || err));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function loadSeed(seed) {
    const next = cleanPayload({ ...emptyCase, ...seed.case });
    setActiveSeed(seed.id);
    setForm(next);
    setDecision(null);
    setEvidence(null);
    const scored = await runPredict(next);
    if (scored?.action === "RECOMMEND_CONTEST") {
      await runEvidence(next);
    }
  }

  async function scoreBatch(parsed) {
    setBusy(true);
    setError("");
    setBatchProgress(`Scoring 0 / ${parsed.length}…`);
    const scored = [];
    try {
      for (let i = 0; i < parsed.length; i += 1) {
        const item = parsed[i];
        setBatchProgress(`Scoring ${i + 1} / ${parsed.length}…`);
        try {
          const result = await api("/api/predict", {
            method: "POST",
            body: JSON.stringify(item.case),
          });
          scored.push({
            ...item,
            winnability: result.winnability,
            action: result.action,
            error: null,
          });
        } catch (err) {
          scored.push({
            ...item,
            winnability: null,
            action: null,
            error: String(err.message || err),
          });
        }
      }
      setBatchRows(scored);
      setBatchProgress(`Scored ${scored.length} rows`);
    } finally {
      setBusy(false);
    }
  }

  async function onCsvSelected(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Please upload a .csv file.");
      return;
    }
    setCsvName(file.name);
    setActiveSeed(null);
    try {
      const text = await file.text();
      const parsed = casesFromCsv(text);
      if (!parsed.length) {
        throw new Error("No data rows found in CSV.");
      }
      await scoreBatch(parsed);
    } catch (err) {
      setBatchRows([]);
      setError(String(err.message || err));
      setBatchProgress("");
    }
  }

  async function loadBatchRow(item) {
    if (!item?.case) return;
    setActiveSeed(null);
    setForm(item.case);
    setDecision(null);
    setEvidence(null);
    const scored = await runPredict(item.case);
    if (scored?.action === "RECOMMEND_CONTEST") {
      await runEvidence(item.case);
    }
  }

  function downloadTemplate() {
    const header = CSV_COLUMNS.join(",");
    const blob = new Blob([`${header}\n`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "chargeback_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const test = metrics?.test?.xgboost;
  const baselines = metrics?.test;
  const actionInfo = decision ? ACTION_COPY[decision.action] : null;

  return (
    <div className="app">
      <div className={`status-bar ${status}`}>
        <span className="dot" />
        <span>{statusDetail}</span>
        {status === "offline" ? (
          <button type="button" className="linkish" onClick={refreshHealth}>
            Retry
          </button>
        ) : null}
      </div>

      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">AI Risk Manager · Defense only</p>
          <h1>Chargeback Sentinel</h1>
          <p className="lede">
            Predict which disputes are worth fighting. Route with deterministic
            policy. Assemble grounded evidence only for high-winnability cases.
          </p>
        </div>
        <aside className="hero-side">
          <h2>Evaluator path</h2>
          <ol>
            <li>Click demo cases 1 → 2 → 3</li>
            <li>Read gauge + tier band</li>
            <li>Review evidence on case 3</li>
            <li>Open Metrics visuals</li>
          </ol>
        </aside>
      </header>

      <FlowPipeline activeStep={activeStep} />

      <div className="tabs">
        <button className={tab === "desk" ? "active" : ""} onClick={() => setTab("desk")}>
          Live desk
        </button>
        <button
          className={tab === "metrics" ? "active" : ""}
          onClick={() => setTab("metrics")}
        >
          Metrics & charts
        </button>
        <button
          className={tab === "judgment" ? "active" : ""}
          onClick={() => setTab("judgment")}
        >
          AI judgment
        </button>
      </div>

      {error ? <div className="error banner-error">{error}</div> : null}

      {tab === "desk" ? (
        <div className="workspace">
          <section className="panel">
            <div className="panel-head">
              <div>
                <p className="step-label">Step 1</p>
                <h2>Select a chargeback</h2>
              </div>
            </div>
            <div className="seed-row">
              {seeds.map((seed, i) => (
                <button
                  key={seed.id}
                  className={`seed ${activeSeed === seed.id ? "selected" : ""} seed-${seed.id}`}
                  onClick={() => loadSeed(seed)}
                  disabled={busy || status === "offline"}
                >
                  <div className="seed-top">
                    <span className="seed-num">{i + 1}</span>
                    <strong>{seed.label}</strong>
                  </div>
                  <span>{seed.blurb}</span>
                </button>
              ))}
            </div>

            <div className="csv-upload">
              <div className="csv-head">
                <div>
                  <p className="step-label">Or upload a batch</p>
                  <h3>CSV chargebacks</h3>
                  <p className="muted">
                    One case per row. Max {MAX_CSV_ROWS} rows. Binary fields
                    accept 0/1 or yes/no.
                  </p>
                </div>
                <div className="csv-links">
                  <a href="/sample_chargebacks.csv" download>
                    Sample CSV
                  </a>
                  <button
                    type="button"
                    className="linkish"
                    onClick={downloadTemplate}
                  >
                    Empty template
                  </button>
                </div>
              </div>
              <label className={`csv-drop ${busy ? "disabled" : ""}`}>
                <input
                  type="file"
                  accept=".csv,text/csv"
                  disabled={busy || status === "offline"}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    onCsvSelected(file);
                    e.target.value = "";
                  }}
                />
                <span className="csv-drop-title">
                  {busy && batchProgress
                    ? batchProgress
                    : "Drop a CSV here or click to browse"}
                </span>
                <span className="csv-drop-meta">
                  {csvName
                    ? `Last file: ${csvName}`
                    : "Columns must include reason_code and amount"}
                </span>
              </label>

              {batchRows.length ? (
                <div className="batch-table-wrap">
                  <table className="batch-table">
                    <thead>
                      <tr>
                        <th>Row</th>
                        <th>ID</th>
                        <th>Reason</th>
                        <th>Amount</th>
                        <th>Win %</th>
                        <th>Tier</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {batchRows.map((item) => (
                        <tr key={`${item.row}-${item.case.chargeback_id}`}>
                          <td>{item.row}</td>
                          <td className="mono">{item.case.chargeback_id}</td>
                          <td>{item.case.reason_code}</td>
                          <td>{Number(item.case.amount).toLocaleString()}</td>
                          <td>
                            {item.error
                              ? "—"
                              : `${Math.round((item.winnability || 0) * 100)}%`}
                          </td>
                          <td>
                            {item.error ? (
                              <span className="batch-err" title={item.error}>
                                Error
                              </span>
                            ) : (
                              <span className={`batch-tier ${item.action}`}>
                                {ACTION_COPY[item.action]?.title || item.action}
                              </span>
                            )}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="linkish"
                              disabled={busy || !!item.error}
                              onClick={() => loadBatchRow(item)}
                            >
                              Open
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>

            <details className="advanced" open>
              <summary>All model inputs</summary>
              <div className="grid">
                <label>
                  Reason code
                  <select
                    value={form.reason_code}
                    onChange={(e) => update("reason_code", e.target.value)}
                  >
                    <option value="unauthorized">unauthorized</option>
                    <option value="item_not_received">item_not_received</option>
                    <option value="not_as_described">not_as_described</option>
                  </select>
                </label>
                <label>
                  Merchant category
                  <select
                    value={form.merchant_category}
                    onChange={(e) => update("merchant_category", e.target.value)}
                  >
                    <option value="ecommerce">ecommerce</option>
                    <option value="digital_goods">digital_goods</option>
                    <option value="travel">travel</option>
                    <option value="grocery">grocery</option>
                    <option value="fashion">fashion</option>
                    <option value="subscriptions">subscriptions</option>
                    <option value="services">services</option>
                  </select>
                </label>
                <label>
                  Amount (INR)
                  <input
                    type="number"
                    value={form.amount}
                    onChange={(e) => update("amount", Number(e.target.value))}
                  />
                </label>
                <label>
                  Amount vs customer avg
                  <input
                    type="number"
                    step="0.01"
                    value={form.amount_vs_customer_avg ?? ""}
                    onChange={(e) =>
                      update(
                        "amount_vs_customer_avg",
                        e.target.value === "" ? null : Number(e.target.value)
                      )
                    }
                  />
                </label>
                <label>
                  Delivery confirmed
                  <select
                    value={form.delivery_confirmed}
                    onChange={(e) =>
                      update("delivery_confirmed", Number(e.target.value))
                    }
                  >
                    <option value={1}>yes</option>
                    <option value={0}>no</option>
                  </select>
                </label>
                <label>
                  3DS
                  <select
                    value={form.three_d_secure}
                    onChange={(e) =>
                      update("three_d_secure", Number(e.target.value))
                    }
                  >
                    <option value={1}>yes</option>
                    <option value={0}>no</option>
                  </select>
                </label>
                <label>
                  Device fingerprint match
                  <select
                    value={form.device_fingerprint_match}
                    onChange={(e) =>
                      update("device_fingerprint_match", Number(e.target.value))
                    }
                  >
                    <option value={1}>yes</option>
                    <option value={0}>no</option>
                  </select>
                </label>
                <label>
                  IP geolocation match
                  <select
                    value={form.ip_geolocation_match ?? 0}
                    onChange={(e) =>
                      update("ip_geolocation_match", Number(e.target.value))
                    }
                  >
                    <option value={1}>yes</option>
                    <option value={0}>no</option>
                  </select>
                </label>
                <label>
                  Customer email opened
                  <select
                    value={form.customer_email_opened ?? 0}
                    onChange={(e) =>
                      update("customer_email_opened", Number(e.target.value))
                    }
                  >
                    <option value={1}>yes</option>
                    <option value={0}>no</option>
                  </select>
                </label>
                <label>
                  Customer tenure (days)
                  <input
                    type="number"
                    value={form.customer_tenure_days}
                    onChange={(e) =>
                      update("customer_tenure_days", Number(e.target.value))
                    }
                  />
                </label>
                <label>
                  Prior disputes
                  <input
                    type="number"
                    value={form.customer_prior_disputes}
                    onChange={(e) =>
                      update("customer_prior_disputes", Number(e.target.value))
                    }
                  />
                </label>
                <label>
                  Velocity (24h)
                  <input
                    type="number"
                    value={form.transaction_velocity_24h}
                    onChange={(e) =>
                      update("transaction_velocity_24h", Number(e.target.value))
                    }
                  />
                </label>
                <label>
                  Days since transaction
                  <input
                    type="number"
                    value={form.days_since_transaction}
                    onChange={(e) =>
                      update("days_since_transaction", Number(e.target.value))
                    }
                  />
                </label>
                <label>
                  Tracking id
                  <input
                    value={form.tracking_id || ""}
                    onChange={(e) =>
                      update("tracking_id", e.target.value || null)
                    }
                  />
                </label>
                <label>
                  Delivery timestamp
                  <input
                    value={form.delivery_timestamp || ""}
                    onChange={(e) =>
                      update("delivery_timestamp", e.target.value || null)
                    }
                  />
                </label>
                <label className="span-2">
                  Merchant policy
                  <input
                    value={form.merchant_policy || ""}
                    onChange={(e) =>
                      update("merchant_policy", e.target.value || null)
                    }
                  />
                </label>
              </div>
              <div className="actions">
                <button
                  disabled={busy || status === "offline"}
                  onClick={() => runPredict()}
                >
                  {busy ? "Working…" : "Re-score with these inputs"}
                </button>
                <button
                  className="secondary"
                  disabled={
                    busy ||
                    status === "offline" ||
                    decision?.action !== "RECOMMEND_CONTEST"
                  }
                  onClick={() => runEvidence()}
                >
                  Assemble evidence
                </button>
              </div>
            </details>
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <p className="step-label">Decision view</p>
                <h2>Score · tier · evidence</h2>
              </div>
            </div>

            {decision ? (
              <>
                <div className="viz-row">
                  <div className="viz-card">
                    <h3>Winnability gauge</h3>
                    <WinGauge value={decision.winnability} />
                  </div>
                  <div className="viz-card grow">
                    <h3>Policy tier band</h3>
                    <TierTrack
                      value={decision.winnability}
                      action={decision.action}
                    />
                    <div className={`action-pill ${decision.action}`}>
                      {actionInfo?.title}
                    </div>
                    <p className="action-copy">{actionInfo?.meaning}</p>
                  </div>
                </div>

                <div className="viz-row">
                  <div className="viz-card">
                    <h3>Why this tier</h3>
                    <ul className="list">
                      {(decision.reasons || []).map((r) => (
                        <li key={r}>{r}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="viz-card grow">
                    <h3>Top model signals</h3>
                    <SignalBars signals={decision.top_signals} />
                  </div>
                </div>

                {decision.action === "RECOMMEND_CONTEST" && !evidence?.package ? (
                  <div className="actions">
                    <button
                      disabled={busy || status === "offline"}
                      onClick={() => runEvidence()}
                    >
                      Assemble evidence
                    </button>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="empty-state">
                <div className="empty-visual" aria-hidden="true" />
                <p>Select a demo case to see the gauge, tier band, and signals.</p>
              </div>
            )}

            <div className="divider" />

            <div className="panel-head">
              <div>
                <p className="step-label">Evidence</p>
                <h2>Representment package</h2>
              </div>
            </div>

            {evidence?.blocked_reason ? (
              <div className="note warn">{evidence.blocked_reason}</div>
            ) : null}

            {evidence?.package ? (
              <>
                <div className="proxy-strip">
                  <div>
                    <span>Source</span>
                    <strong>{evidence.package.source}</strong>
                  </div>
                  <div>
                    <span>Completeness</span>
                    <strong>{evidence.proxy_metrics?.completeness_score}</strong>
                  </div>
                  <div>
                    <span>Unsupported claims</span>
                    <strong>
                      {evidence.proxy_metrics?.unsupported_claim_rate}
                    </strong>
                  </div>
                </div>
                <div className="evidence-grid">
                  {(evidence.package.evidence_package || []).map((item) => (
                    <div
                      className="evidence-item"
                      key={`${item.priority}-${item.type}`}
                    >
                      <div className="evidence-meta">
                        <span>#{item.priority}</span>
                        <span className={`strength ${item.strength}`}>
                          {item.strength}
                        </span>
                      </div>
                      <strong>{item.type.replaceAll("_", " ")}</strong>
                      <p>{item.description}</p>
                    </div>
                  ))}
                </div>
                <h3>Representment draft</h3>
                <div className="draft">{evidence.package.representment_draft}</div>
                <h3>Gaps</h3>
                <ul className="list">
                  {(evidence.package.evidence_gaps || []).map((g) => (
                    <li key={g}>{g}</li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="muted">
                Evidence appears for Recommend Contest (demo case 3).
              </p>
            )}
          </section>
        </div>
      ) : null}

      {tab === "metrics" ? (
        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="step-label">Held-out evaluation</p>
              <h2>Metrics & visualizations</h2>
            </div>
          </div>
          <div className="note warn">
            {metrics?.disclaimer ||
              "Synthetic data validates methodology — not production performance."}
          </div>

          {test ? (
            <>
              <div className="viz-row">
                <div className="viz-card grow">
                  <h3>Final model snapshot</h3>
                  <MetricBars row={test} />
                </div>
                <BaselineBars baselines={baselines} />
              </div>

              <div className="viz-row">
                <div className="viz-card grow">
                  <h3>
                    Confusion matrix @ {fmt(test.threshold, 2)}
                  </h3>
                  <ConfusionViz cm={test.confusion_matrix} />
                </div>
                <div className="viz-card">
                  <h3>Baseline table</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Model</th>
                          <th>P</th>
                          <th>R</th>
                          <th>PR-AUC</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          ["Rule", baselines?.rule],
                          ["LogReg", baselines?.logreg],
                          ["Tree", baselines?.tree],
                          ["XGBoost", baselines?.xgboost],
                        ].map(([name, row]) => (
                          <tr
                            key={name}
                            className={name === "XGBoost" ? "hl" : ""}
                          >
                            <td>{name}</td>
                            <td>{fmt(row?.precision)}</td>
                            <td>{fmt(row?.recall)}</td>
                            <td>{fmt(row?.pr_auc)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {metrics?.cost_model?.assumptions ? (
                    <p className="tiny">
                      FP ₹{metrics.cost_model.assumptions.fp_unit_cost_inr} · FN ₹
                      {metrics.cost_model.assumptions.fn_unit_cost_inr}{" "}
                      (placeholders)
                    </p>
                  ) : null}
                </div>
              </div>
            </>
          ) : (
            <p>Metrics unavailable.</p>
          )}
        </section>
      ) : null}

      {tab === "judgment" ? (
        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="step-label">Architecture</p>
              <h2>Right tool, right place</h2>
            </div>
          </div>
          <div className="judgment-grid">
            <article>
              <div className="j-tag">ML</div>
              <h3>XGBoost</h3>
              <p>Scores tabular features for dispute winnability.</p>
            </article>
            <article>
              <div className="j-tag">Rules</div>
              <h3>Policy engine</h3>
              <p>Maps score to Do not fight / Review / Contest.</p>
            </article>
            <article>
              <div className="j-tag">LLM</div>
              <h3>Evidence writer</h3>
              <p>Builds packages only for Contest — never classifies.</p>
            </article>
            <article>
              <div className="j-tag">Human</div>
              <h3>Final review</h3>
              <p>No auto-submission. Analyst remains in control.</p>
            </article>
          </div>
        </section>
      ) : null}
    </div>
  );
}
