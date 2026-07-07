# Product Requirements Document (PRD)
## Hybrid Energy-Aware Container Framework (HECF)

**Status:** Final — Aligned to `PROPOSAL_THESIS_203012510019_V3`.
**Companion document:** `architecture.md` (Technical Design).

---

### 1. Project Overview & Philosophy

The **Hybrid Energy-Aware Container Framework (HECF)** is an adaptive, lightweight
Docker-native container management system. It is designed to operate efficiently in
resource-constrained environments, reducing unnecessary energy consumption while
preserving web-service latency and reliability — without the operational overhead
of heavy orchestrators like Kubernetes or Docker Swarm.

HECF's core scientific contribution is a **closed-loop control system (MAPE-K)**
that solves a well-documented trade-off in the literature: aggressive energy-saving
algorithms degrade latency/SLA, while latency-first systems waste energy. HECF
intervenes **preventively** (via EMA-driven trend detection) and **reactively**
(via the Guardrail), aiming to hold four core metrics — CPU Utilization, RAM Usage,
Energy Consumption, and Web Latency — in balance simultaneously, on a single host,
with no container migration.

---

### 2. Target Environment

- **Hardware:** resource-constrained servers, 1–4 vCPU / 1–4 GB RAM — covering
  VPS, UMKM/small-business servers, campus labs, and edge devices.
- **Minimum experimental hardware:** ≥2 cores @ ≥1.5GHz, ≥4GB RAM, ≥20GB storage.
  Constrained scenarios simulated via CPU pinning + cgroups limits:
  - Scenario 1: 1 vCPU / 1 GB RAM (entry-level VPS profile)
  - Scenario 2: 2 vCPU / 2 GB RAM (edge/IoT gateway profile)
- **OS:** Linux, kernel `≥ 5.10`, **cgroups v2** unified hierarchy required.
  Validated on Ubuntu Server LTS; targets Rocky Linux 9 for production home-server
  deployment.
- **Dependencies:** Python 3, `numpy`, `docker` SDK, `requests`, `locust`, `Flask`.
  No Kubernetes, Docker Swarm, Podman, or standalone containerd.

---

### 3. Objectives & Goals

Directly tied to the two Research Questions:

- **RQ1 — Design & build:** design and implement an energy-aware, lightweight
  container management framework that runs autonomously on low-spec servers without
  additional orchestration tooling.
- **RQ2 — Evaluate impact:** empirically evaluate the framework's effect on server
  resource-usage efficiency, energy consumption, and web service quality, compared
  to Docker's default resource management.

Concretely:
- **Energy Efficiency:** reduce energy consumption via real-time, preventive resource
  shaping — **target 10–20% reduction** vs. Default Docker baseline.
- **Zero Heavy-ML Overhead:** perform prediction/classification without any ML/DL
  library.
- **Stability under Spikes:** prevent server hang/OOM during traffic spikes via the
  Guardrail and Tier Detector.
- **SLA Preservation:** P95 latency stable **under 500ms**, framework overhead
  consistently **<5%** of total server capacity.
- **Idle Energy Savings:** via Micro-Freezing, achieve additional energy reduction
  during container idle windows beyond what vertical cgroups scaling provides.

---

### 4. Core Features & Functional Requirements

#### 4.1 4-Layer Adaptive Architecture

Full technical spec: `architecture.md` §3.

- **Layer 1: Environment Profiler**
  - Auto-detects host CPU/RAM capacity at init via `/proc/cpuinfo`, `/proc/meminfo`.
  - Attempts to detect hardware power sensors (Intel RAPL / AMD energy counters) for
    real-time electrical measurement (see §4.2).
  - Cold-Start Fallback: forces **Tier 2 (Balanced)** until 120 samples collected.
  - Container tagging: classifies containers as `priority` (never hard-capped) or
    `non-priority` (safe to throttle first) via Docker labels.

- **Layer 2: Monitoring Engine**
  - Reads CPU/Memory metrics **directly from cgroups v2 (cgroupfs)**, bypassing the
    Docker REST API to minimize overhead.
  - **Adaptive Sampling:** 10s interval when CPU(t-1) > 60%; 30s otherwise.

- **Layer 3: Hybrid Control Engine**
  - **3A. Guardrail:** emergency throttle if CPU > 80% OR RAM > 90% in ≥3 of last 5
    samples.
  - **3B. Tier Detection:** sliding window of 120 samples; `spike_ratio = P95/P50`.
    - Tier 1 (Aggressive): ratio > 2.0
    - Tier 2 (Balanced): 1.5 ≤ ratio ≤ 2.0
    - Tier 3 (Soft): ratio < 1.5
  - **3C. Prediction:** fixed-alpha (0.2) EMA, O(1) memory. Fine-tunes Guardrail
    threshold sensitivity ahead of time — **not** applied directly as a shaping input.

- **Layer 4: Adaptive Resource Shaping**
  - Translates Layer 3 decisions into live cgroups v2 parameter updates (`cpu.max`,
    `memory.max`, `memory.swap.max`) without container restarts.
  - Priority-aware: throttles `non-priority` containers first/harder under Tier 1.
  - **Micro-Freezing:** when a non-priority container is idle (no inbound requests)
    for ≥2 seconds, Layer 4 writes `cgroup.freeze = 1` to drop CPU usage to exactly
    **0%** while keeping the container resident in RAM. On the next request, the
    container thaws in **<1ms**. Hard cap: 500–1000ms per freeze cycle.
  - **TCP Backlog Verification:** at cold start, confirms the host's `somaxconn`
    value provides enough headroom to queue inbound packets during a freeze window
    without dropping connections.

#### 4.2 Energy Estimation — Hybrid Hardware/Software Model

HECF uses a tiered approach to produce the most accurate energy data possible for
the deployment environment:

- **Hardware-True Mode (bare-metal):** if Layer 1 detects Intel RAPL or AMD energy
  counters, the estimator reads real Joules from the motherboard and uses
  **Proportional Power Apportionment** to attribute power per container based on
  CPU usage share.

- **Software Estimation Mode (cloud VPS / virtualized):** if hardware sensors are
  blocked, falls back to the validated linear model (Jarus et al., 2014, <4% error):

  ```
  P(t) = P_idle + (P_max - P_idle) × CPU_utilization(t)
  ```

  `P_idle` and `P_max` are dynamically computed from the host's physical CPU core
  count (`cpu_count × 3.75W` and `cpu_count × 13.5W` respectively), making the
  model self-calibrating for the actual hardware environment.

- **Output:** Joule and kWh only. **No carbon/CO2e conversion of any kind** —
  explicitly removed from scope (proposal §1.6).

#### 4.3 Framework Overhead Tracking

HECF measures and reports its **own** CPU/RAM consumption as a first-class metric
("Framework Overhead"), separate from the containers it manages. Target: **<5%** of
total server capacity. Required to validate Hypothesis H2 and answer RQ1.

#### 4.4 Real-time Metrics Dashboard

- Lightweight Flask server (port 8092).
- Visualizes exactly the **5 evaluation metrics** defined in §9.
- No historical database; live aggregation from `metrics.csv` only.
- Container action states visible in the tracking table (e.g., MICRO_FREEZE,
  GUARDRAIL, AGGRESSIVE, BALANCED, SOFT).

#### 4.5 Operation Modes for Baseline Comparison

Runtime-selectable mode via environment variable:

| Mode | Behavior | Purpose |
|------|----------|---------|
| `default_docker` | Observes only, no shaping | Absolute baseline (Condition A) |
| `static_cap` | Fixed hard CPU cap (80%), no adaptive logic | Isolates value of adaptive control |
| `reactive_only` | Only Layer 3A (Guardrail) active | Isolates Tier Detection + EMA contribution |
| `full_hecf` | All 4 layers + Micro-Freezing active | The proposed system (Condition B) |

---

### 5. Non-Functional Requirements

- **Strict Library Constraints:** MUST NOT use Pandas, Scikit-Learn, PyTorch, or
  TensorFlow. Computation must be standard library + NumPy only. No ARIMA, ETS, or
  PROPHET-style forecasting.
- **Privileged Isolation:** HECF runs in its own Docker Compose service in
  privileged mode with mounts to `/var/run/docker.sock`, `/sys/fs/cgroup`,
  `/sys/class/powercap/` (optional), and `/sys/class/hwmon/` (optional).
- **Configurability:** all thresholds, window sizes, and constants centralized in
  `config.py` and independently overridable at runtime for the ±20% sensitivity sweep.
- **No environmental/carbon claims** anywhere in code, UI, logs, or docs.
- **Minimal footprint:** HECF's framework overhead must not exceed 5% of total server
  capacity under any measured condition.

---

### 6. Research Alignment

| Research Gap | Problem with Existing Solutions | How HECF Closes It |
|---|---|---|
| G1 — Overhead & monitoring paradox | Heavy orchestrators (K8s/Swarm) or ML-based control; heavy monitoring stacks (ELK/Zipkin) consume the same RAM/energy they try to save | O(1) EMA, Adaptive Sampling, direct cgroupfs reads, <5% overhead target, only 5 tracked metrics |
| G2 — Migration dependence | Nearly all reviewed literature saves energy via consolidation/migration across physical hosts | HECF is 100% local vertical scaling via cgroups + Micro-Freezing; no migration, works on single-host VPS |
| G3 — Energy vs. latency trade-off | Aggressive energy saving (e.g., Xu & Buyya: 44% energy saved, latency 174ms→425ms) wreck SLA | Guardrail + Tier Detection + proactive EMA + Micro-Freezing aim to cut energy without breaching P95 <500ms |

| Hypothesis | Statement | Validated by |
|---|---|---|
| H1 | HECF produces more stable resource usage and lower energy consumption than default Docker, under identical workload | Metrics 1–3 (CPU, RAM, Energy); paired t-test/Wilcoxon, Cohen's d, 95% CI |
| H2 | HECF does not degrade web service quality, and the framework's own overhead is not significant | Metrics 4–5 (Latency, Framework Overhead); paired comparison, 95% CI |

---

### 7. Testing & Validation Workloads

- **HttpArena:** **Baseline** category only — 3 workload types: JSON Processing,
  Static Files, Async DB (all as Docker containers).
- **Locust:** 4 traffic intensity profiles:
  - Low: 10–20% peak CPU
  - Medium: 40–60%
  - High: 70–85%
  - Spike: 90–100% burst, then drop to <30%
- **Baseline comparators:**
  1. Default Docker (no dynamic limitation) — absolute baseline
  2. Static Resource Allocation (fixed 80% CPU hard cap)
  3. Reactive Threshold-based System (Guardrail only, no Tier Detection/EMA)

---

### 8. Experimental Design Requirements

- **Independent variable:** resource management condition — Condition A (Default
  Docker) vs. Condition B (HECF active), plus 2 additional baselines for ablation.
- **Dependent variables (5 metrics, see §9):** CPU Utilization, Memory/RAM Usage,
  Energy Consumption, Web Latency (SLA), Framework Overhead.
- **Controlled variables:** identical hardware, OS, Docker Engine version, workload
  type/volume, and experiment duration across all runs.
- **Duration/replication:** ≥30 minutes per run with 5-minute warm-up excluded,
  replicated 3×.
- **Total executions:** `2 conditions × 3 HttpArena workload types × 4 load levels
  × 3 replications = 72 individual executions`, reproducible via
  `experiments/run_experiment.py`.

---

### 9. Metrics Specification (5 total — authoritative list)

| # | Metric | Unit | Hypothesis | RQ |
|---|---|---|---|---|
| 1 | CPU Utilization | % / cgroups limit | H1 | RQ2 |
| 2 | Memory/RAM Usage | MB/GB | H1 | RQ2 |
| 3 | Energy Consumption | Joule / kWh (hybrid HW/SW model, no carbon) | H1 | RQ2 |
| 4 | Web Latency (SLA) | ms (P95) / average response time | H2 | RQ2 |
| 5 | Framework Overhead | % CPU & RAM consumed by HECF itself | H2 | RQ1 |

No 6th metric and no carbon/environmental metric.

---

### 10. Statistical Analysis Requirements

All analysis at significance level α = 0.05:
- **Preprocessing:** IQR-based outlier removal, cross-scenario normalization,
  per-period aggregation, descriptive stats (mean, median, SD, P95, P50, variance).
- **Normality check:** Shapiro-Wilk.
- **Comparison test:** paired t-test (if normal) or Wilcoxon signed-rank (if not).
- **Effect size:** Cohen's d.
- **Confidence interval:** 95% CI reported for all 5 core metrics.
- **Energy-Latency Product:** `ELP = Energy(kWh) × Latency_p95(ms)` per scenario;
  HECF is considered effective if its ELP is lower than the baseline.
- **Sensitivity analysis:** sweep `GUARDRAIL_CPU_THRESHOLD`, tier ratios (1.5/2.0),
  `EMA_ALPHA`, and `TIER_WINDOW` at ±20%; report as heatmap/contour table.

---

### 11. Explicit Out-of-Scope

- Kubernetes, Docker Swarm, Podman, or any multi-host orchestration.
- Container migration between physical hosts.
- Carbon/CO2e emission estimation or environmental-impact analysis of any kind.
- Any ML/DL library (Pandas, Scikit-Learn, PyTorch, TensorFlow) or ML-based
  forecasting (ARIMA, ETS, PROPHET).
- More than 5 tracked evaluation metrics.
- Adaptive/variable EMA alpha (fixed at 0.2 per the final proposal).
- Physical power-meter hardware integration (software estimation fallback is used
  when hardware sensors are unavailable).

---

## Appendix A — Safenet Features (Hidden, Not Evaluated in Thesis)

> These features are **fully implemented and silently running** but are intentionally
> excluded from the main thesis scope, dashboard UI, and formal evaluation.
> They exist as a safety-net for the defense — ready to demonstrate if an examiner
> raises questions about security hardening or extended energy savings.

| # | Feature | File | Purpose |
|---|---------|------|---------|
| 1 | EDoS / IDS-IPS Protection | `framework/security/ddos_filter.py` | Separates DDoS attack traffic from real workload before Layer 3 analysis. |
| 1 | Anti-EDoS Logic | `framework/security/edos_guard.py` | Freezes containers under attack instead of passive throttling (avoids weaponizing HECF's own caps). |
| 2 | eBPF Runtime Introspection | `framework/security/ebpf_sensor.py` | Kernel-level syscall and I/O tracking per container. Detects malware activity invisible to cgroupfs. |
| 2 | Sandbox Isolation | `framework/security/sandbox_isolator.py` | Immediately freezes containers flagged with anomalous behavior via `cgroup.freeze`. |
| 3 | Co-resident Attack Protection | `framework/security/coresident_placement.py` | Heuristic placement to separate high-risk from sensitive tenants on multi-tenant hosts. |
| 4 | Trusted Image Signing | `framework/security/image_signer.py` | Verifies container image signatures at cold start. Blocks backdoored images before runtime. |
| 4 | Minimum Privilege Guard | `framework/security/privilege_guard.py` | Flags non-priority containers requesting `--privileged` mode at cold start. |
| 5 | Encryption Cost Calculator | `framework/security/encryption_calc.py` | Estimates hybrid encryption (AES-RSA / AES-ECC) CPU cost before inter-container transfers. |

All modules are unit-tested in `tests/test_security.py` and enabled via
`SECURITY_ENABLED = True` in `framework/config.py`.
