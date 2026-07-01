# Product Requirements Document (PRD)
## Hybrid Energy-Aware Container Framework (HECF)

> **Status:** Aligned to `PROPOSAL_THESIS_203012510019_V2` (final thesis proposal).
> **Supersedes:** All earlier "Hybrid Green Container Framework (HGCF)" PRDs.
> Companion document: `architecture.md` (technical design). Use both together as the
> refactoring spec.

---

### 0. Migration Notes (read first)

See `architecture.md` §0 for the full technical delta table. In PRD terms, the scope
reduction across revisions means:

1. **Drop** all carbon/CO2e/environmental-impact features and copy. This was a
   requirement in the old scope; the final proposal's Batasan Penelitian (§1.6)
   explicitly excludes it: *"Tidak dilakukan estimasi emisi karbon atau analisis
   dampak lingkungan."*
2. **Shrink** the dashboard from "17 evaluation metrics" down to exactly 5 (4 core +
   1 meta-metric). This is intentional, not a simplification bug — proposal §3.5
   frames the narrower metric set as avoiding "monitoring paradox" (citing Dinga et
   al., where heavy monitoring itself wastes the resources it's supposed to save).
3. **Rename** the product from HGCF to HECF everywhere (config keys, container
   names, network names, docs, log strings).
4. **Add** capabilities that did not exist in the old PRD: container priority
   tagging, framework self-overhead tracking, and a baseline/mode switch needed to
   reproduce the thesis's comparative experiments.
5. **Tighten** the predictor spec: fixed EMA alpha (0.2), not adaptive.

---

### 1. Project Overview & Philosophy
The **Hybrid Energy-Aware Container Framework (HECF)** is an adaptive, lightweight
Docker-native container management system. It is designed to operate efficiently in
resource-constrained environments, reducing unnecessary energy consumption while
preserving web-service latency and reliability — without the operational overhead
of heavy orchestrators like Kubernetes or Docker Swarm.

HECF's core scientific contribution is a **closed-loop control system** that solves
a well-documented trade-off in the literature: aggressive energy-saving algorithms
degrade latency/SLA, while latency-first systems waste energy. HECF intervenes
**preventively** (via EMA-driven trend detection) rather than only reactively,
aiming to hold four core metrics — CPU Utilization, RAM Usage, Energy Consumption,
and Web Latency — in balance simultaneously, on a single host, with no migration.

### 2. Target Environment
- **Hardware:** resource-constrained servers, 1–4 vCPU / 1–4 GB RAM (VPS,
  UMKM/small-business servers, campus labs, edge devices).
- **Minimum experimental hardware:** ≥2 cores @ ≥1.5GHz, ≥4GB RAM, ≥20GB storage,
  with 1vCPU/1GB and 2vCPU/2GB scenarios simulated on top via cgroups pinning.
- **OS:** Linux, kernel `>= 5.10`, **cgroups v2** required. Validated on Ubuntu
  Server LTS for the thesis experiments; also targets Rocky Linux 9 for production
  home-server deployment.
- **Dependencies:** Python 3, `numpy`, `docker` SDK, `requests`, `locust` (load
  testing), `Flask` (dashboard). No Kubernetes, Docker Swarm, Podman, or standalone
  containerd.

### 3. Objectives & Goals
Directly tied to the thesis's two Research Questions:

- **RQ1 — Design & build:** design and implement an energy-aware, lightweight
  container management framework that runs autonomously on low-spec servers
  without any additional orchestration tooling.
- **RQ2 — Evaluate impact:** empirically evaluate the framework's effect on server
  resource-usage efficiency, energy consumption, and web service quality, compared
  to Docker's default resource management.

Concretely:
- **Energy Efficiency:** reduce energy consumption via real-time, preventive
  resource shaping — **target 10–20% reduction** vs. Default Docker baseline
  (proposal Table 2.3, HECF row).
- **Zero Heavy-ML Overhead:** perform prediction/classification without
  Pandas/Scikit-Learn/PyTorch/TensorFlow.
- **Stability under Spikes:** prevent server hang/OOM during traffic spikes via a
  robust real-time guardrail.
- **SLA Preservation:** target **P95 latency stable under 500ms**, with framework
  overhead consistently **<5%**.

### 4. Core Features & Functional Requirements

#### 4.1. 4-Layer Adaptive Architecture
Full technical spec lives in `architecture.md` §3; functional requirements below.

- **Layer 1: Environment Profiler**
  - Auto-detects host CPU/RAM capacity at init via `/proc/cpuinfo`, `/proc/meminfo`.
  - Cold-Start Fallback: forces **Tier 2 (Balanced)** until 120 samples collected.
  - **Container tagging (new requirement):** classifies each managed container as
    `priority` (e.g. databases — never hard-capped) or `non-priority` (e.g.
    stateless web front-ends — safe to throttle first).

- **Layer 2: Monitoring Engine**
  - Extracts CPU/Memory metrics **directly from cgroups v2 (cgroupfs)**, not the
    Docker REST API, to minimize overhead.
  - **Adaptive Sampling** (exact rule): 10s interval when CPU(t-1) > 60%; 30s
    interval otherwise.

- **Layer 3: Hybrid Control Engine**
  - **3A. Real-time Guardrail:** hard emergency throttle if CPU > 80% OR RAM > 90%
    in ≥3 of the last 5 polling samples.
  - **3B. Tier Detection:** sliding window of last 120 samples; `spike_ratio =
    P95/P50` of CPU usage.
    - Aggressive (Tier 1): ratio > 2.0
    - Balanced (Tier 2): 1.5 ≤ ratio ≤ 2.0
    - Soft (Tier 3): ratio < 1.5
  - **3C. Lightweight Prediction:** fixed-alpha (0.2) EMA, O(1) memory. Used to
    fine-tune Guardrail threshold sensitivity ahead of time — **not** applied
    directly as a shaping input.

- **Layer 4: Adaptive Resource Shaping**
  - Translates Layer 3 decisions into live cgroups v2 parameters (`--cpu-quota` /
    `cpu.max`, `--memory`, `--memory-swap`) without container restarts.
  - Priority-aware: throttles `non-priority` containers first/harder under Tier 1.

#### 4.2. Energy Estimation (carbon tracking removed)
- Linear CPU-to-power estimation model, no physical power meter required:
  `P(t) = P_idle + (P_max - P_idle) × CPU_utilization(t)`.
- Default coefficients: `P_idle ≈ 15W`, `P_max ≈ 54W` (entry-level server class;
  configurable per actual hardware).
- Output units: Joule and kWh only. **No carbon-equivalent (CO2e) conversion, no
  grid-carbon-intensity coefficient, no environmental-impact reporting** — this was
  explicitly cut from scope (see §0.1 above).

#### 4.3. Framework Overhead Tracking (new requirement)
- HECF must measure and report its **own** CPU/RAM consumption as a first-class
  metric ("Framework Overhead"), separate from the containers it manages.
- This is required to validate Hypothesis H2 and answer RQ1 — not optional
  instrumentation.
- Target: **<5%** of total server capacity, measured against idle baseline.

#### 4.4. Real-time Metrics Dashboard (scope reduced: 5 metrics, not 17)
- Centralized web UI via lightweight Flask server (port 8092).
- Visualizes exactly the 5 evaluation metrics defined in §7 below, in real time.
- No large historical database; live aggregation from `metrics.csv` only.

#### 4.5. Operation Modes for Baseline Comparison (new requirement)
To reproduce the thesis's comparative methodology, the framework must support a
runtime-selectable mode:

| Mode | Behavior | Purpose |
|---|---|---|
| `default_docker` | Observes only, no shaping | Absolute baseline (Condition A) |
| `static_cap` | Fixed hard CPU cap (default 80%), no adaptive logic | Isolates value of adaptive control vs. a naive static cap |
| `reactive_only` | Only Layer 3A (Guardrail) active; Tier Detector + Predictor disabled | Isolates the specific contribution of Tier Detection + EMA prediction |
| `full_hecf` | All 4 layers active | The proposed system (Condition B) |

### 5. Non-Functional Requirements
- **Strict Library Constraints:** MUST NOT use Pandas, Scikit-Learn, PyTorch, or
  TensorFlow. Computation must be standard library + NumPy only. No ARIMA, ETS, or
  PROPHET-style forecasting.
- **Privileged Isolation:** HECF runs in its own Docker Compose service, in
  privileged mode, with mounts to `/var/run/docker.sock` and `/sys/fs/cgroup`
  (**cgroups v2** unified hierarchy).
- **Configurability:** all thresholds/window sizes/constants centralized in a
  single `config.py` (see `architecture.md` §9 for the full parameter table), and
  independently overridable at runtime to support the ±20% sensitivity sweep.
- **No environmental/carbon claims** anywhere in code, UI, logs, or docs.

### 6. Research Alignment (why these requirements exist)

This section exists so an implementing engineer/AI agent understands *why* a
requirement is non-negotiable — it maps directly to what the thesis defense will be
scored against.

| Research Gap | What existing solutions get wrong | How HECF requirements close it |
|---|---|---|
| G1 — Overhead & monitoring paradox | Heavy orchestrators (K8s/Swarm) or ML/Game-Theory control; heavy monitoring stacks (ELK/Zipkin) themselves waste RAM/energy | O(1) EMA/AFMV, Adaptive Sampling, direct cgroupfs reads, <5% overhead target, only 5 tracked metrics |
| G2 — Migration dependence | Nearly all reviewed literature saves energy via consolidation/migration across physical hosts | HECF is 100% local vertical scaling via cgroups; no migration, works on single-host VPS |
| G3 — Energy vs. latency trade-off | Aggressive energy savings (e.g. Xu & Buyya: 44% energy saved, latency 174ms→425ms) wreck SLA | Guardrail + Tier Detection + proactive EMA aim to cut energy without breaching the P95 <500ms latency target |

| Hypothesis | Statement | Validated by |
|---|---|---|
| H1 | HECF produces more stable resource usage and lower energy consumption than default Docker, under identical workload | Metrics 1–3 (CPU, RAM, Energy); paired t-test/Wilcoxon, Cohen's d, 95% CI |
| H2 | HECF does not degrade web service quality (latency, success rate), and the framework's own overhead is not significant | Metrics 4–5 (Latency, Framework Overhead); paired comparison, 95% CI |

### 7. Testing & Validation Workloads

- **HttpArena:** subset limited to **Baseline** category only — 3 workload types:
  JSON Processing, Static Files, Async DB (all as Docker containers).
- **Locust:** load generator, 4 traffic intensity profiles:
  - Low: 10–20% peak CPU
  - Medium: 40–60%
  - High: 70–85%
  - Spike: 90–100% burst, then drop to <30%
- **Baseline comparators** (in addition to Default Docker vs. HECF):
  1. Default Docker (no dynamic limitation) — absolute baseline
  2. Static Resource Allocation (hard cap 80% CPU)
  3. Reactive Threshold-based System (Guardrail only, no Tier Detection/EMA)

### 8. Experimental Design Requirements

- **Independent variable:** resource management condition — Condition A (Default
  Docker) vs. Condition B (HECF active), plus the two extra baselines in §7 for the
  ablation-style comparison in proposal §4.4.4.
- **Dependent variables (5 metrics, see §9):** CPU Utilization, Memory/RAM Usage,
  Energy Consumption, Web Latency (SLA), Framework Overhead.
- **Controlled variables:** identical hardware, OS, Docker Engine version, workload
  type/volume, and experiment duration across all runs.
- **Constraint scenarios:** Scenario 1 (1 vCPU/1GB — entry-level VPS), Scenario 2
  (2 vCPU/2GB — edge/IoT gateway).
- **Duration/replication:** each condition × workload × load-level combination runs
  ≥30 minutes with a 5-minute warm-up excluded from analysis, replicated 3×.
- **Total executions:** `2 conditions × 3 HttpArena workload types × 4 load levels
  × 3 replications = 72 individual executions`. This must be reproducible via
  `experiments/run_experiment.py`.

### 9. Metrics Specification (5 total — this is the authoritative list)

| # | Metric | Unit | Hypothesis | RQ |
|---|---|---|---|---|
| 1 | CPU Utilization | % / cgroups limit | H1 | RQ2 |
| 2 | Memory/RAM Usage | MB/GB | H1 | RQ2 |
| 3 | Energy Consumption | Joule / kWh (linear estimate, no carbon) | H1 | RQ2 |
| 4 | Web Latency (SLA) | ms (P95) / average response time | H2 | RQ2 |
| 5 | Framework Overhead | % CPU & RAM consumed by HECF itself | H2 | RQ1 |

No 6th metric, no carbon/environmental metric, no arbitrary "17-metric" panel — this
was a deliberate scope decision to avoid the monitoring-overhead paradox (§6, G1).

### 10. Statistical Analysis Requirements

All analysis at significance level α = 0.05:
- Preprocessing: IQR-based outlier removal, cross-scenario normalization,
  per-period aggregation, descriptive stats (mean, median, SD, P95, P50, variance).
- Normality check: Shapiro-Wilk.
- Comparison test: paired t-test (if normal) or Wilcoxon signed-rank (if not).
- Effect size: Cohen's d.
- Confidence interval: 95% CI reported for all 5 core metrics.
- Energy-Latency Product: `ELP = Energy(kWh) × Latency_p95(ms)` per scenario; HECF
  is considered effective if its ELP is lower than the baseline's.
- Sensitivity analysis: sweep `GUARDRAIL_CPU_THRESHOLD`, tier ratios (1.5/2.0),
  `EMA_ALPHA`, and `TIER_WINDOW` at ±20%; report as heatmap/contour table.

### 11. Explicit Out-of-Scope (do not re-add these)

- Kubernetes, Docker Swarm, Podman, or any multi-host orchestration.
- Container migration between physical hosts.
- Carbon/CO2e emission estimation or environmental-impact analysis of any kind.
- Any ML/DL library (Pandas, Scikit-Learn, PyTorch, TensorFlow) or ML-based
  forecasting (ARIMA, ETS, PROPHET).
- Physical power-meter hardware integration (software estimation only).
- More than 5 tracked evaluation metrics.
- Adaptive/variable EMA alpha (must be fixed at 0.2 per the final proposal).
