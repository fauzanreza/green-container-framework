# Architecture & Technical Design Document
## Hybrid Energy-Aware Container Framework (HECF)

> **Status:** Aligned to `PROPOSAL_THESIS_203012510019_V2` (final thesis proposal).
> Companion document: `prd.md` (functional requirements).

---

### 1. System Architecture Overview

HECF follows a strictly decentralized, decoupled, and modular architecture. It is
deployed as a standalone, privileged Docker container that observes, predicts, and
shapes other containers running on the same host daemon — a **closed-loop control
system** operating directly at the Linux kernel level via **cgroups v2**.

The system interacts directly with the Linux kernel (via `/proc` and the unified
`cgroups v2` hierarchy) and the Docker Daemon API (via `docker.sock`) to continuously
evaluate container performance and adjust constraints — without any external
orchestrator (no Kubernetes, no Docker Swarm) and without container migration. All
resource shaping is **local, vertical scaling** on a single host.

### 2. High-Level Component Diagram

```text
+-----------------------------------------------------------------------------------+
|                          Host OS (Linux, kernel >=5.10, cgroups v2)               |
|                                                                                    |
|   +-------------------+        +---------------------------------------------+    |
|   | TARGET CONTAINERS | <----- |                 HECF ENGINE                 |    |
|   | (e.g. HttpArena:  |        |                                             |    |
|   |  JSON/Static/     |        |  [Layer 1: Profiler] (/proc + container     |    |
|   |  Async DB)        |        |   tagging: priority / non-priority)         |    |
|   +-------------------+        |                                             |    |
|            |                   |  [Layer 2: Monitor] (Adaptive Polling,      |    |
|            v                   |   cgroupfs v2 direct read)                  |    |
|   +-------------------+        |                                             |    |
|   | Docker Daemon API | -----> |  [Layer 3: Hybrid Control Engine]           |    |
|   | (docker.sock)     |        |    3A. Guardrail (3-of-5 emergency caps)    |    |
|   +-------------------+        |    3B. Tier Detector (Spike Ratio P95/P50)  |    |
|            |                   |    3C. Predictor (EMA alpha=0.2, O(1))      |    |
|            v                   |                                             |    |
|   +-------------------+        |  [Layer 4: Shaper] (cgroups v2 updates,     |    |
|   | Linux cgroups v2  | <----- |   priority-aware throttling)                |    |
|   +-------------------+        |                                             |    |
|                                 |  [Energy Estimator]  (Joule/kWh, no carbon)|    |
|                                 |  [Overhead Tracker]  (HECF's own CPU/RAM)  |    |
|                                 |  [Mode Selector]      (baseline comparison)|    |
|                                 +---------------------------------------------+    |
+-----------------------------------------------------------------------------------+
```

### 3. Layered Design Breakdown

#### Layer 1: Environment Profiler (`framework/profiler.py`)
- Parses system hardware context from `/proc/cpuinfo` and `/proc/meminfo` at cold start.
- Determines baseline safe-operating limits for downstream shaping modules.
- **Cold-Start Fallback Policy:** for the first `120` samples (before Layer 3B's
  sliding window has enough history), the system forces **Tier 2 (Balanced)**.
  Rationale (proposal §3.2.2): starting in Tier 1 (Aggressive) risks bad cold-start
  latency; starting in Tier 3 (Soft) risks resource exhaustion before enough data
  exists for an informed decision.
- **Container tagging (new):** reads container metadata/labels to classify each
  target container as:
  - `priority` — e.g. database / Async DB containers. Must never receive a hard CPU
    cap from the Guardrail, to avoid data corruption from starved I/O.
  - `non-priority` — e.g. stateless web front-ends / static-file servers. Safe to
    throttle first/more aggressively under load.
  - Recommended implementation: Docker container labels (e.g.
    `hecf.priority=high|low`), read once at Layer 1 init and cached for Layer 4.

#### Layer 2: Monitoring Engine (`framework/monitor.py`)
- Reads CPU/Memory metrics **directly from `cgroupfs` (v2 unified hierarchy)**,
  bypassing the Docker REST API to minimize overhead (e.g.
  `/sys/fs/cgroup/<container>/cpu.stat`, `memory.current` under cgroups v2 —
  replaces the old v1-style `cpuacct.usage` path).
- **Adaptive Sampling (exact rule, proposal §3.2.3):**
  - If CPU utilization at `t-1` **> 60%** → poll every **10 seconds**.
  - Otherwise (normal/idle) → poll every **30 seconds**.
- Target: monitoring overhead must stay within the global `<5%` framework overhead
  budget (see Overhead Tracker, §4).

#### Layer 3: Hybrid Control Engine
The centralized decision layer. Combines reactive, analytic, and proactive control.

- **3A. Real-time Guardrail (`framework/guardrail.py`)** — *reactive*
  - Maintains a rolling boolean evaluation array of the last **5** samples.
  - Triggers emergency intervention (hard CPU cap) if **CPU > 80% OR RAM > 90%** in
    **at least 3 of the last 5** samples.
  - The 3-of-5 rule is deliberately chosen to avoid false positives on harmless
    micro-spikes (e.g. JSON serialization bursts) while still reacting before OOM.

- **3B. Tier Detector (`framework/tier_detector.py`)** — *analytic*
  - Sliding window of the last **120** samples.
  - Computes `spike_ratio = P95 / P50` of CPU utilization (via `numpy.percentile()`).
  - Tier mapping:
    | Tier | Label | Condition |
    |------|-------|-----------|
    | 1 | Aggressive | `spike_ratio > 2.0` |
    | 2 | Balanced | `1.5 <= spike_ratio <= 2.0` |
    | 3 | Soft | `spike_ratio < 1.5` |

- **3C. Predictor (`framework/predictor.py`)** — *proactive*
  - Implements **EMA (Exponential Moving Average)**, fixed smoothing factor
    `alpha = 0.2` (empirically chosen to filter high-frequency network noise).
  - O(1) time and memory — needs only the previous smoothed value (t-1).
  - **Important:** the predicted trend is **not** applied directly to cgroup
    parameters. It is used only to fine-tune the Guardrail's threshold sensitivity
    ahead of time, giving the system earlier readiness for anomalies.

#### Layer 4: Adaptive Resource Shaping (`framework/shaper.py`)
- Translates Layer 3 decisions into real Docker/cgroups v2 parameter updates:
  `--cpus`, `--cpu-quota` (or `cpu.max` under v2), `--memory`, `--memory-swap`.
- Respects Layer 1's priority tagging: non-priority containers are throttled first
  and more aggressively; priority containers are shielded from hard caps.
- Tier-driven shaping behavior (proposal Table 3.1):

  | Tier | Condition | Shaping behavior |
  |------|-----------|-------------------|
  | 1 – Aggressive | `spike_ratio > 2.0` | Hard CPU cap on all containers; throttle non-priority containers |
  | 2 – Balanced | `1.5 <= spike_ratio <= 2.0` | Soft CPU cap; burst control with adaptive limit |
  | 3 – Soft | `spike_ratio < 1.5` | Minimal intervention; passive monitoring only |

### 4. Supplementary Services

#### Energy Estimator (`framework/energy.py`)
- Linear CPU-to-power model, validated by Jarus et al. (error <4%):

  ```
  P(t) = P_idle + (P_max - P_idle) x CPU_utilization(t)
  ```

- Default constants (configurable per real host CPU): `P_idle ≈ 15W`,
  `P_max ≈ 54W` (entry-level server class, proposal §3.5.1).
- Total energy = numerical integration of `P(t)` over the experiment duration.
- **No carbon/CO2e conversion of any kind.** This was explicitly removed in the final
  proposal scope (§1.6).

#### Framework Overhead Tracker (`framework/overhead_tracker.py`) — NEW
- Measures HECF's **own** CPU and RAM consumption (the process(es) running the
  framework itself), separate from the target containers it monitors.
- Feeds Metric 5 ("Framework Overhead") — required to validate Hypothesis H2 and
  answer RQ1. Target: `<5%` of total server capacity.

#### Mode Selector (`framework/modes.py`) — NEW
- Runtime-configurable operation mode, needed to reproduce the thesis's comparative
  experiment design (see §7 below):
  - `default_docker` — HECF observes but performs no shaping (absolute baseline).
  - `static_cap` — fixed hard cap (default 80% CPU), no adaptive logic.
  - `reactive_only` — only Layer 3A (Guardrail) active; Tier Detector and Predictor
    disabled. Used to isolate the contribution of Tier Detection + EMA.
  - `full_hecf` — all four layers active (the proposed system).

#### Metrics Dashboard (`dashboard.py`)
- Independent lightweight Flask server (port 8092, unchanged).
- Ingests `metrics.csv` generated by the HECF core loop.
- Visualizes **exactly 5 metrics** (not 17): CPU Utilization, Memory/RAM Usage,
  Energy Consumption, Web Latency (SLA), Framework Overhead.
- No historical database requirement — live aggregation only.

### 5. Technical Stack
- **Core Language:** Python 3.10+
- **Math/Stats:** NumPy only
- **API Interfacing:** Docker SDK for Python (`docker`)
- **Reporting UI:** Flask, HTML5, Chart.js, Bootstrap 5
- **Load Testing (Internal CI/Evaluation):** Locust
- **Deployment:** Docker, Docker Compose
- **Hard constraint:** MUST NOT use Pandas, Scikit-Learn, PyTorch, or TensorFlow —
  computation is standard library + NumPy only (proposal §1.6, §3.2.4). This
  excludes ARIMA/ETS/PROPHET or any ML/DL-based prediction.

### 6. Infrastructure & Deployment Model
HECF is orchestrated strictly via `docker-compose.yml`.
- **OS requirement:** Linux, kernel `>= 5.10`, **cgroups v2** unified hierarchy
  enabled. Validated against Ubuntu Server LTS in the thesis experimental
  environment; also compatible with Rocky Linux 9 for production/home-server use.
- **Privilege Requirements:** `privileged: true`, `pid: host`.
- **Volume Mounts:**
  - `/var/run/docker.sock` (API access)
  - `/sys/fs/cgroup` (read-write, cgroups **v2** unified hierarchy — for CPU/memory
    shaping)
  - `/proc/cpuinfo` & `/proc/meminfo` (read-only, for profiling)
- **Container Networking:** connects to the same Docker network as the load
  generators and target containers for full observability (e.g. `hecf-network`).
- **Minimum experimental hardware:** CPU ≥2 cores (physical or virtual) @ ≥1.5GHz,
  RAM ≥4GB, storage ≥20GB. Constrained scenarios are simulated via CPU pinning +
  cgroups memory limits on top of this baseline:
  - Scenario 1: 1 vCPU / 1 GB RAM (entry-level VPS profile)
  - Scenario 2: 2 vCPU / 2 GB RAM (edge/IoT gateway profile)

### 7. Experimental & Evaluation Support Architecture — NEW

These modules exist to make the thesis's methodology (Bab III) directly reproducible
from the codebase, not just described in the paper.

#### 7.1 Workload & Load Generation
- **HttpArena** — subset limited to the **Baseline** category only, 3 workload
  types: JSON Processing, Static Files, Async DB.
- **Locust** — 4 traffic intensity profiles (`locustfiles/locustfile.py`), exact
  peak-CPU ranges:
  | Profile | Peak CPU range | Pattern |
  |---|---|---|
  | Low | 10–20% | steady/quiet |
  | Medium | 40–60% | normal business hours |
  | High | 70–85% | high density |
  | Spike | 90–100% burst, then drop to <30% | sudden traffic storm |

#### 7.2 Experiment Orchestration (`experiments/`)
- `run_experiment.py` — orchestrates the full design matrix:
  `2 conditions (Default Docker / HECF active) × 3 HttpArena workload types ×
  4 load levels × 3 replications = 72 individual executions`.
  Each run: 30 min minimum + 5 min warm-up (excluded from analysis).
- `baselines/` — configuration presets for the 3 comparison baselines used to
  isolate HECF's specific contribution:
  1. Default Docker (no dynamic limitation) — absolute baseline
  2. Static Resource Allocation (fixed 80% CPU hard cap)
  3. Reactive Threshold-based System (Guardrail only, no Tier Detection/EMA)

#### 7.3 Analysis Pipeline (`analysis/`)
- `preprocess.py` — IQR-based outlier removal, cross-scenario normalization,
  per-period aggregation, descriptive stats (mean, median, SD, P95, P50, variance).
- `stats_tests.py` — Shapiro-Wilk normality test → paired t-test (normal) or
  Wilcoxon signed-rank (non-normal); Cohen's d effect size; 95% CI for all core
  metrics.
- `energy_latency_product.py` — computes `ELP = Energy(kWh) x Latency_p95(ms)`
  per scenario; HECF is considered effective if its ELP is lower than baseline.
- `sensitivity.py` — sweeps key parameters (`GUARDRAIL_CPU_THRESHOLD`,
  `TIER1_RATIO`, `TIER2_RATIO`, `EMA_ALPHA`, `TIER_WINDOW`) at ±20% to measure
  impact on resource stability and energy consumption; outputs heatmap-ready data.

### 8. Project Structure Anatomy

```text
.
├── architecture.md              # This document
├── prd.md                       # Product Requirements Document
├── docker-compose.yml           # Infrastructure orchestration config
├── Dockerfile                   # Production image build instructions
├── requirements.txt             # numpy, docker, flask, requests, locust
├── dashboard.py                 # Flask app — 5 metrics only (port 8092)
│
├── framework/                   # Core HECF Logic Module
│   ├── __init__.py
│   ├── config.py                 # Centralized thresholds/constants (see §9)
│   ├── profiler.py               # Layer 1: /proc profiler + cold-start fallback
│   │                              #          + priority/non-priority tagging
│   ├── monitor.py                # Layer 2: cgroupfs v2 reader, adaptive polling
│   ├── guardrail.py              # Layer 3A: 3-of-5 emergency guardrail
│   ├── tier_detector.py          # Layer 3B: 120-window P95/P50 tier detection
│   ├── predictor.py              # Layer 3C: fixed-alpha EMA (0.2), O(1)
│   ├── shaper.py                 # Layer 4: cgroups v2 update handler
│   ├── energy.py                 # Energy estimator (Joule/kWh) — no carbon
│   ├── overhead_tracker.py       # NEW: HECF's own CPU/RAM footprint (Metric 5)
│   ├── modes.py                  # NEW: default_docker/static_cap/reactive_only/full_hecf
│   └── main.py                   # Main control loop uniting Layers 1-4
│
├── http-arena/                   # Benchmarking / Testing Services (Baseline subset)
│   ├── Dockerfile
│   ├── main.py                   # JSON Processing, Static Files, Async DB
│   ├── requirements.txt
│   └── static/
│
├── locustfiles/                  # Load Generation Scenarios
│   └── locustfile.py             # Low / Medium / High / Spike (exact % ranges)
│
├── experiments/                  # NEW: reproduces the 72-run experimental design
│   ├── run_experiment.py
│   └── baselines/
│       ├── default_docker.yml
│       ├── static_cap.yml
│       └── reactive_only.yml
│
├── analysis/                     # NEW: statistical analysis pipeline
│   ├── preprocess.py
│   ├── stats_tests.py
│   ├── energy_latency_product.py
│   └── sensitivity.py
│
└── tests/                        # Automated validation
    └── test_framework.py         # Unit tests ensuring core logic functions without regressions
```

### 9. Configuration Parameter Reference (`framework/config.py`)

All thresholds, window sizes, and constants must be centralized here for tuning and
for the sensitivity-analysis sweep (§7.3).

| Constant | Value | Source (proposal §) |
|---|---|---|
| `COLD_START_SAMPLES` | 120 | §3.2.2 |
| `FALLBACK_TIER` | 2 (Balanced) | §3.2.2 |
| `SAMPLING_CPU_THRESHOLD` | 60% | §3.2.3 |
| `SAMPLING_INTERVAL_HIGH` | 10s (when CPU(t-1) > threshold) | §3.2.3 |
| `SAMPLING_INTERVAL_LOW` | 30s (otherwise) | §3.2.3 |
| `GUARDRAIL_WINDOW` | 5 samples | §3.2.4 (3A) |
| `GUARDRAIL_TRIGGER_COUNT` | 3 of 5 | §3.2.4 (3A) |
| `GUARDRAIL_CPU_THRESHOLD` | 80% | §3.2.4 (3A) |
| `GUARDRAIL_RAM_THRESHOLD` | 90% | §3.2.4 (3A) |
| `TIER_WINDOW` | 120 samples | §3.2.4 (3B) |
| `TIER1_AGGRESSIVE_RATIO` | > 2.0 | §3.2.4 (3B), Table 3.1 |
| `TIER2_BALANCED_RATIO` | 1.5 – 2.0 | §3.2.4 (3B), Table 3.1 |
| `TIER3_SOFT_RATIO` | < 1.5 | §3.2.4 (3B), Table 3.1 |
| `EMA_ALPHA` | 0.2 | §3.2.4 (3C) |
| `FRAMEWORK_OVERHEAD_TARGET` | < 5% | §1, §3.5, Table 3.2 |
| `P_IDLE_WATTS` | 15 (default, configurable) | §3.5.1 |
| `P_MAX_WATTS` | 54 (default, configurable) | §3.5.1 |
| `STATIC_CAP_CPU_PERCENT` | 80% (baseline mode only) | §3.4.4, §4.4.4 |

All five listed sensitivity-analysis parameters (`GUARDRAIL_CPU_THRESHOLD`,
`TIER1_AGGRESSIVE_RATIO`/`TIER2_BALANCED_RATIO`, `EMA_ALPHA`, `TIER_WINDOW`) must be
independently overridable at runtime (env var or CLI flag) to support the ±20%
sweep required by proposal §4.4.1.
