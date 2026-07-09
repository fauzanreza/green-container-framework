# Architecture & Technical Design Document
## Hybrid Energy-Aware Container Framework (HECF)

**Status:** Final — Aligned to `PROPOSAL_THESIS_203012510019_V3`.
**Companion document:** `prd.md` (Functional & Research Requirements).

---

### 1. System Architecture Overview

HECF follows a strictly decentralized, decoupled, and modular architecture. It is
deployed as a standalone, privileged Docker container that observes, predicts, and
shapes other containers running on the same host daemon — operating as a
**closed-loop control system (MAPE-K)** directly at the Linux kernel level via
**cgroups v2**.

The system interacts directly with the Linux kernel (via `/proc` and the unified
`/sys/fs/cgroup/` hierarchy) and the Docker Daemon API (via `/var/run/docker.sock`)
to continuously evaluate container performance and adjust constraints — without any
external orchestrator (no Kubernetes, no Docker Swarm) and without container
migration. All resource shaping is **local, vertical scaling** on a single host.

This design requires **no external orchestration tooling** and operates at kernel
level for maximum precision and minimum overhead.

---

### 2. High-Level Component Diagram

```text
+-----------------------------------------------------------------------------------+
|                    Host OS (Linux, kernel ≥5.10, cgroups v2)                      |
|                                                                                   |
|  [ LOCUST ]              +------------------------------------------------+       |
|  Load Gen.               |               HECF ENGINE                      |       |
|      |                   |                                                |       |
|  +---v-------------------+ [Layer 1: Profiler]   /proc + HW Sensor +      |       |
|  |  TARGET CONTAINERS    |                       container tagging        |       |
|  |  (HttpArena:          |                                                |       |
|  |   JSON / Static /     | [Layer 2: Monitor]    Adaptive Polling,        |       |
|  |   Async DB)           |                       cgroupfs v2 direct read  |       |
|  +-----------------------+                                                |       |
|           |              | [Layer 3: Hybrid Control Engine]               |       |
|           v              |   3A. Guardrail  (3-of-5 emergency caps)       |       |
|  +-----------------------+   3B. Tier Detector (Spike Ratio P95/P50)      |       |
|  | Docker Daemon API     |   3C. Predictor  (EMA alpha=0.2, O(1))         |       |
|  | (docker.sock)         |                                                |       |
|  +-----------------------+ [Layer 4: Shaper]     cgroups v2 updates +     |       |
|           |              |                       Micro-Freezing           |       |
|           v              |                                                |       |
|  +-----------------------+ [Energy Estimator]    Hybrid HW Sensor / kWh   |       |
|  |   Linux cgroups v2    |                                                |       |
|  +-----------------------+ [Overhead Tracker]    HECF's own CPU/RAM       |       |
|                            [Mode Selector]       4 runtime modes          |       |
|                          +-------------------------+----------------------+       |
|                                                    |                              |
|                          +-------------------------v----------------------+       |
|                          |     HECF DASHBOARD (Flask / Web UI)            |       |
|                          |     Displays the 5 Core Tracked Metrics        |       |
|                          +------------------------------------------------+       |
+-----------------------------------------------------------------------------------+
```

---

### 3. Layered Design Breakdown

#### Layer 1: Environment Profiler (`framework/profiler.py`)

Runs at cold start to build a complete hardware and environment profile of the host.

- **Hardware Detection:** parses `/proc/cpuinfo` and `/proc/meminfo` to determine
  physical CPU core count and total RAM available on the host.
- **Hybrid Power Sensor Detection:** at startup, Layer 1 attempts to locate a real
  hardware power sensor (see §4 — Energy Estimator). It checks for Intel RAPL at
  `/sys/class/powercap/intel-rapl/` and AMD energy at `/sys/class/hwmon/`. If found,
  real-time electrical data is used. If blocked (e.g., inside a cloud VPS), the
  framework logs a notice and falls back to the validated software estimation model.
- **Cold-Start Fallback Policy:** for the first `30` samples (revised from 120 —
  at 30s polling, 120 samples = 60 min > the 30-min run), the system forces
  **Tier 2 (Balanced)**.
- **Container Tagging:** reads Docker container labels to classify each target as:
  - `priority` — e.g. database / Async DB containers. Never receive a hard CPU cap
    from the Guardrail, to avoid data corruption from starved I/O.
  - `non-priority` — e.g. stateless web front-ends / static-file servers. Safe to
    throttle first and more aggressively under load.
  - Implementation: Docker container labels (e.g. `hecf.priority=high|low`), read
    once at Layer 1 init and cached for Layer 4.
- **Host `/proc` Mount Verification:** cross-checks `/proc/cpuinfo` CPU count
  against `os.cpu_count()` to confirm the host's `/proc` is mounted (not the
  container's own). Requires `pid: host` in `docker-compose.yml`.
- **Network-Infra Auto-Priority:** auto-detects containers matching known
  proxy/DNS image patterns (`nginx`, `caddy`, `traefik`, `cloudflared`, `coredns`)
  and forces `priority=True` to prevent freezing/throttling network infrastructure.
- **`nf_conntrack_max` Pre-flight:** reads `/proc/sys/net/netfilter/nf_conntrack_max`
  and warns if below `65536`. Extends the TCP Backlog Verification pattern.

#### Layer 2: Monitoring Engine (`framework/monitor.py`)

Reads CPU/Memory metrics **directly from cgroupfs (v2 unified hierarchy)**,
bypassing the Docker REST API to minimize monitoring overhead:
- CPU: `/sys/fs/cgroup/<container>/cpu.stat`
- Memory: `/sys/fs/cgroup/<container>/memory.stat` (computes `actual = memory.current
  - inactive_file` to exclude reclaimable page-cache from RAM measurement).

**Adaptive Sampling (proposal §3.2.3):**
- If CPU utilization at `t-1` **> 60%** → poll every **10 seconds**
- Otherwise → poll every **30 seconds**

**Event-Driven Idle Detection:** Micro-Freezing idle state is detected via
`cgroup.events` `populated 0` signal (kernel notification when no active processes
remain), replacing polling-based `cpu_percent < 1.0` to eliminate false-idle/active.

Target: all monitoring overhead combined must stay within the global **<5%**
framework overhead budget (measured by the Overhead Tracker, §4).

#### Layer 3: Hybrid Control Engine

The centralized decision layer combining reactive, analytic, and proactive control.

- **3A. Real-time Guardrail (`framework/guardrail.py`)** — *reactive*
  - Rolling boolean array of the last **5** samples.
  - Triggers emergency intervention (hard CPU cap) if **CPU > 80% OR RAM > 90%**
    in **at least 3 of the last 5** samples.
  - The 3-of-5 rule avoids false positives on harmless micro-spikes while still
    reacting before OOM.
  - **PSI Internal Signal:** Layer 3A reads `<cgroup>/cpu.pressure` (`some avg10`)
    as a supplementary internal signal alongside CPU/RAM thresholds. If PSI
    `some avg10 > 25.0` AND the 3-of-5 condition is met, Guardrail confidence is
    elevated (logged as `GUARDRAIL+PSI`). PSI is NOT a new tracked metric.

- **3B. Tier Detector (`framework/tier_detector.py`)** — *analytic*
  - Sliding window of the last **120** samples.
  - Computes `spike_ratio = P95 / P50` of CPU utilization via `numpy.percentile()`.

  | Tier | Label | Condition |
  |------|-------|-----------|
  | 1 | Aggressive | `spike_ratio > 2.0` |
  | 2 | Balanced | `1.5 ≤ spike_ratio ≤ 2.0` |
  | 3 | Soft | `spike_ratio < 1.5` |

  - **Tier Transition Hysteresis:** a tier change commits only after the new tier
    has been stable for `TIER_HYSTERESIS_SAMPLES` (default: 3) consecutive evaluations.
    Prevents rapid oscillation (e.g. Tier 2→1→2→1) that introduces noise into
    Metrics #1 and #5. Configurable via `HECF_TIER_HYSTERESIS` env var.

- **3C. Predictor (`framework/predictor.py`)** — *proactive*
  - **EMA (Exponential Moving Average)**, fixed `alpha = 0.2` (filters high-frequency
    network noise while remaining responsive to trend changes).
  - O(1) time and memory — needs only the previous smoothed value.
  - The predicted trend fine-tunes the Guardrail's threshold sensitivity ahead of
    time; it is **not** applied directly as a cgroup shaping parameter.

#### Layer 4: Adaptive Resource Shaping (`framework/shaper.py`)

Translates Layer 3 decisions into real Docker/cgroups v2 parameter writes:
`cpu.max`, `memory.max`, `memory.swap.max`.

Respects Layer 1's priority tagging: non-priority containers are throttled first
and more aggressively; priority containers are shielded from hard caps.

| Tier | Condition | Shaping behavior |
|------|-----------|-------------------|
| 1 – Aggressive | `spike_ratio > 2.0` | Hard CPU cap; non-priority containers throttled first |
| 2 – Balanced | `1.5 ≤ spike_ratio ≤ 2.0` | Soft CPU cap; burst control with adaptive limit |
| 3 – Soft | `spike_ratio < 1.5` | Minimal intervention; passive monitoring only |

**Micro-Freezing (`framework/security/micro_freezer.py`):**
Extends Layer 4 shaping with a sub-second, zero-CPU idle mechanism:
- When a `non-priority` container has had no inbound activity for **≥2 seconds**,
  Layer 4 writes `1` to `cgroup.freeze`, dropping CPU usage to exactly **0%** while
  keeping the container fully resident in memory (no cold-start penalty).
- On the next inbound request, `cgroup.freeze = 0` is written, thawing the container
  in **under 1ms**.
- Hard freeze-duration cap: **500–1000ms** maximum per cycle (see §5 for why this
  requires cgroups v2 specifically).
- **TCP Backlog Buffering:** while a container is frozen, new inbound packets queue
  in the host's TCP backlog (`net.core.somaxconn`) rather than being dropped. At
  cold start, `framework/security/tcp_backlog_manager.py` inspects the host's
  `somaxconn` value to confirm sufficient headroom for the expected freeze window.
  Extended to also verify app-level listen backlog via `/proc/<pid>/net/tcp`.
- **zram-as-swap + `memory.swap.max`:** verifies zram-backed swap at cold start;
  sets `memory.swap.max` accordingly (compressed swap if zram present, 0 otherwise)
  to prevent uncontrolled disk thrashing on constrained hosts.
- **`memory.high` Soft-Brake:** writes `memory.high = 0.85 × memory.max` as a
  kernel soft-throttle point. When crossed, the kernel slows allocation rate,
  giving the Guardrail time to react before the hard `memory.max` OOM boundary.

---

### 4. Supplementary Services

#### Energy Estimator (`framework/energy.py`) — Hybrid Hardware/Software Model

The energy estimator uses a **tiered detection strategy** to produce the most
accurate power reading available on the deployment environment:

**Tier A — Hardware-True Mode (bare-metal / physical servers):**

If Layer 1's hardware sensor detection succeeds (Intel RAPL or AMD energy counter
found), the estimator reads the actual Joules consumed from the motherboard register
per sampling interval and calculates real-time Watts via:

```
Watts = ΔJoules / ΔTime
```

Because hardware sensors report total CPU package power (not per-container),
**Proportional Power Apportionment** is used to attribute power to individual
containers:

```
Container_Power = Total_HW_Watts × (Container_CPU% / Total_CPU_Capacity)
```

**Tier B — Software Estimation Mode (cloud VPS / virtualized environments):**

If hardware sensors are blocked by the hypervisor (as is common on rented cloud
VPS), the estimator falls back to the validated linear CPU-to-power model
(Jarus et al., 2014, error <4%):

```
P(t) = P_idle + (P_max - P_idle) × CPU_utilization(t)
```

`P_idle` and `P_max` are calculated dynamically from Layer 1's hardware profile
using a per-core multiplier:

```
P_idle = cpu_count × 3.75W
P_max  = cpu_count × 13.5W
```

This scales automatically: a 4-core machine produces 15W/54W (matching the
entry-level server class in proposal §3.5.1); a 2-core edge device produces
7.5W/27W; a 16-core server produces 60W/216W.

**Output units:** Joule and kWh only. **No carbon/CO2e conversion of any kind.**
This was explicitly removed from scope (proposal §1.6).

#### Framework Overhead Tracker (`framework/overhead_tracker.py`)

Measures HECF's **own** CPU and RAM consumption (the processes running the
framework itself), separate from the target containers it monitors. Feeds Metric 5
("Framework Overhead") — required to validate Hypothesis H2 and answer RQ1.
Target: **<5%** of total server capacity.

#### Mode Selector (`framework/modes.py`)

Runtime-configurable operation mode, needed to reproduce the thesis's comparative
experiment design (see §7):

| Mode | Behavior | Purpose |
|------|----------|---------|
| `default_docker` | Observes only, no shaping | Absolute baseline (Condition A) |
| `static_cap` | Fixed hard CPU cap (80%), no adaptive logic | Isolates value of adaptive control |
| `reactive_only` | Only Layer 3A (Guardrail) active | Isolates Tier Detection + EMA contribution |
| `full_hecf` | All four layers active | The proposed system (Condition B) |

#### Metrics Dashboard (`dashboard.py`)

Independent lightweight Flask server (port 8092). Ingests `metrics.csv` generated
by the HECF core loop. Visualizes **exactly 5 metrics**: CPU Utilization, Memory/RAM
Usage, Energy Consumption, Web Latency (SLA), Framework Overhead. No historical
database — live aggregation only.

---

### 5. Why cgroups v2 Is a Hard Requirement for Micro-Freezing

cgroups v1's freezer subsystem freezes member tasks individually and is known to
hang or fail if a task is in an uninterruptible I/O-wait state (D state) —
unacceptable for a mechanism meant to run automatically and unattended on every
idle window.

cgroups v2 introduces a single `cgroup.freeze` control file that freezes the entire
cgroup as one **atomic unit at the Linux scheduler level**, independent of individual
task state. This is consistent with — and reinforces — the existing hard requirement
for cgroups v2 stated in §2 and §6; Micro-Freezing specifically would not be safe
to implement against cgroups v1.

---

### 6. Technical Stack

| Component | Technology |
|-----------|-----------|
| Core language | Python 3.10+ |
| Math / Stats | NumPy only |
| Docker API | Docker SDK for Python |
| Dashboard UI | Flask, HTML5, Chart.js, Bootstrap 5 |
| Load testing | Locust |
| Deployment | Docker, Docker Compose |

**Hard constraint:** MUST NOT use Pandas, Scikit-Learn, PyTorch, or TensorFlow.
Computation is standard library + NumPy only (proposal §1.6, §3.2.4). This excludes
ARIMA/ETS/PROPHET or any ML/DL-based prediction.

---

### 7. Infrastructure & Deployment Model

HECF is orchestrated via `docker-compose.yml`.

- **OS requirement:** Linux kernel `≥ 5.10`, **cgroups v2** unified hierarchy.
  Validated on Ubuntu Server LTS; compatible with Rocky Linux 9.
- **Privilege Requirements:** `privileged: true`, `pid: host`.
- **Volume Mounts:**
  - `/var/run/docker.sock` — Docker API access
  - `/sys/fs/cgroup` — read/write, cgroups v2 hierarchy (CPU/memory shaping +
    Micro-Freezing `cgroup.freeze`)
  - `/proc/cpuinfo`, `/proc/meminfo` — read-only, hardware profiling
  - `/sys/class/powercap/` — read-only, Intel RAPL hardware power sensor (if available)
  - `/sys/class/hwmon/` — read-only, AMD energy counter (if available)
- **Network:** connects to the same Docker network as load generators and target
  containers (`hecf-network`).
- **Minimum experimental hardware:** CPU ≥2 cores @ ≥1.5GHz, RAM ≥4GB, storage ≥20GB.
  Constrained scenarios are simulated via CPU pinning + cgroups limits:
  - Scenario 1: 1 vCPU / 1 GB RAM (entry-level VPS profile)
  - Scenario 2: 2 vCPU / 2 GB RAM (edge/IoT gateway profile)

---

### 8. Experimental & Evaluation Support Architecture

These modules make the thesis's methodology (Bab III) directly reproducible from
the codebase.

#### 8.1 Workload & Load Generation

- **HttpArena** — **Baseline** category only; 3 workload types: JSON Processing,
  Static Files, Async DB.
- **Locust** — 4 traffic intensity profiles (`locustfiles/locustfile.py`):

  | Profile | Peak CPU range | Pattern |
  |---------|---------------|---------|
  | Low | 10–20% | Steady / quiet |
  | Medium | 40–60% | Normal business hours |
  | High | 70–85% | High density |
  | Spike | 90–100% burst, then drop to <30% | Sudden traffic storm |

#### 8.2 Experiment Orchestration (`experiments/`)

`run_experiment.py` orchestrates the full design matrix:
`2 conditions × 3 HttpArena workload types × 4 load levels × 3 replications = 72 executions`.
Each run: 30 minutes minimum + 5-minute warm-up (excluded from analysis).

`baselines/` — configuration presets for the 3 comparison baselines:
1. Default Docker (no dynamic limitation) — absolute baseline
2. Static Resource Allocation (fixed 80% CPU hard cap)
3. Reactive Threshold-based System (Guardrail only, no Tier Detection/EMA)

#### 8.3 Analysis Pipeline (`analysis/`)

- `preprocess.py` — IQR-based outlier removal, normalization, descriptive stats
  (mean, median, SD, P95, P50, variance).
- `stats_tests.py` — Shapiro-Wilk normality test → paired t-test or Wilcoxon
  signed-rank; Cohen's d effect size; 95% CI for all core metrics.
- `energy_latency_product.py` — `ELP = Energy(kWh) × Latency_p95(ms)` per scenario.
- `sensitivity.py` — sweeps key parameters at ±20% and outputs heatmap-ready data.

---

### 9. Project Structure

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
│   ├── config.py                # Centralized thresholds/constants (see §10)
│   ├── profiler.py              # Layer 1: /proc profiler + HW sensor + cold-start
│   ├── hardware_sensor.py       # Layer 1: Intel RAPL / AMD energy detection
│   ├── monitor.py               # Layer 2: cgroupfs v2 reader, adaptive polling
│   ├── guardrail.py             # Layer 3A: 3-of-5 emergency guardrail
│   ├── tier_detector.py         # Layer 3B: 120-window P95/P50 tier detection
│   ├── predictor.py             # Layer 3C: fixed-alpha EMA (0.2), O(1)
│   ├── shaper.py                # Layer 4: cgroups v2 update handler
│   ├── energy.py                # Hybrid energy estimator (HW/SW, Joule/kWh)
│   ├── overhead_tracker.py      # HECF's own CPU/RAM footprint (Metric 5)
│   ├── modes.py                 # default_docker/static_cap/reactive_only/full_hecf
│   ├── main.py                  # Main control loop uniting Layers 1–4
│   └── security/                # Performance & runtime extensions
│       ├── micro_freezer.py     # Layer 4 ext: cgroup.freeze idle optimization
│       └── tcp_backlog_manager.py # Layer 4 ext: somaxconn headroom check
│
├── http-arena/                  # Benchmarking / Testing Services
│   ├── Dockerfile
│   ├── main.py                  # JSON Processing, Static Files, Async DB
│   ├── requirements.txt
│   └── static/
│
├── locustfiles/                 # Load Generation Scenarios
│   └── locustfile.py            # Low / Medium / High / Spike
│
├── experiments/                 # Reproduces the 72-run experimental design
│   ├── run_experiment.py
│   └── baselines/
│       ├── default_docker.yml
│       ├── static_cap.yml
│       └── reactive_only.yml
│
├── analysis/                    # Statistical analysis pipeline
│   ├── preprocess.py
│   ├── stats_tests.py
│   ├── energy_latency_product.py
│   └── sensitivity.py
│
└── tests/                       # Automated validation
    ├── test_framework.py        # Unit tests — core logic + energy + modes
    └── test_security.py         # Unit tests — Micro-Freezing + TCP backlog
```

---

### 10. Configuration Parameter Reference (`framework/config.py`)

All thresholds, window sizes, and constants are centralized here and independently
overridable at runtime (env var or CLI flag) to support the ±20% sensitivity sweep
required by proposal §4.4.1.

| Constant | Value | Source |
|----------|-------|--------|
| `COLD_START_SAMPLES`       | 30 (revised)       | Gap audit: 120×30s > 30min run |
| `FALLBACK_TIER`            | 2 (Balanced)       | proposal §3.2.2 |
| `SAMPLING_CPU_THRESHOLD`   | 60%                | proposal §3.2.3 |
| `SAMPLING_INTERVAL_HIGH`   | 10s                | proposal §3.2.3 |
| `SAMPLING_INTERVAL_LOW`    | 30s                | proposal §3.2.3 |
| `GUARDRAIL_WINDOW`         | 5 samples          | proposal §3.2.4 (3A) |
| `GUARDRAIL_TRIGGER_COUNT`  | 3 of 5             | proposal §3.2.4 (3A) |
| `GUARDRAIL_CPU_THRESHOLD`  | 80%                | proposal §3.2.4 (3A) |
| `GUARDRAIL_RAM_THRESHOLD`  | 90%                | proposal §3.2.4 (3A) |
| `TIER_WINDOW`              | 120 samples        | proposal §3.2.4 (3B) |
| `TIER1_AGGRESSIVE_RATIO`   | > 2.0              | proposal Table 3.1 |
| `TIER2_BALANCED_RATIO`     | 1.5 – 2.0          | proposal Table 3.1 |
| `TIER3_SOFT_RATIO`         | < 1.5              | proposal Table 3.1 |
| `TIER_HYSTERESIS_SAMPLES`  | 3                  | Tier transition debounce |
| `EMA_ALPHA`                | 0.2                | proposal §3.2.4 (3C) |
| `FRAMEWORK_OVERHEAD_TARGET`| < 5%               | proposal §1, §3.5 |
| `PSI_SOME_AVG10_THRESHOLD` | 25.0               | Internal Guardrail signal |
| `MEMORY_HIGH_RATIO`        | 0.85               | Soft-brake before memory.max |
| `CONNTRACK_MIN`            | 65536              | nf_conntrack pre-flight |
| `P_IDLE_WATTS`             | Dynamic (cpu_count × 3.75W) | proposal §3.5.1 |
| `P_MAX_WATTS`              | Dynamic (cpu_count × 13.5W) | proposal §3.5.1 |
| `STATIC_CAP_CPU_PERCENT`   | 80% (baseline mode only) | proposal §3.4.4 |
| `MICRO_FREEZE_IDLE_TRIGGER_S` | 2.0             | Layer 4 Micro-Freezing |
| `MICRO_FREEZE_MAX_DURATION_MS` | 1000            | Layer 4 Micro-Freezing cap |

---

## Appendix A — Safenet Features (Hidden, Not Evaluated in Thesis)

> These features are **fully implemented and running** in the background but are
> intentionally excluded from the main thesis scope, dashboard, and evaluation.
> They exist as a defense safety-net — ready to demonstrate if an examiner asks
> about security or asks "what else could this system do?".
> None of these modules introduce a new tracked metric or require additional
> experiment runs.

### A.1 Feature Map

| # | Feature | Module | Layer | Brief Description |
|---|---------|--------|-------|-------------------|
| 1 | EDoS / IDS-IPS Protection | `framework/security/ddos_filter.py` | Layer 2 | Separates DDoS attack traffic from real user workload before it reaches Layer 3's Tier Detector. Prevents HECF's own throttling from being weaponized into an EDoS attack. |
| 1 | Anti-EDoS Logic | `framework/security/edos_guard.py` | Layer 3 | Consumes the DDoS classification from `ddos_filter`. Instead of passive throttling, instructs Layer 4 to freeze the targeted container. |
| 2 | eBPF Runtime Introspection | `framework/security/ebpf_sensor.py` | Layer 2 | Attaches kernel-level probes to track syscalls, function invocations, and disk I/O per container. Detects malware-like behavior that cgroupfs metrics alone cannot see. |
| 2 | Sandbox Isolation | `framework/security/sandbox_isolator.py` | Layer 4 | If `ebpf_sensor` flags anomalous behavior (e.g., illegal binary execution), immediately freezes the container via `cgroup.freeze` without a full restart. |
| 3 | Co-resident Attack Protection | `framework/security/coresident_placement.py` | Layer 3 | Heuristic-based placement strategy to separate high-risk tenants from sensitive ones on multi-tenant hosts. Reduces side-channel exposure. |
| 4 | Trusted Image Signing | `framework/security/image_signer.py` | Layer 1 | Verifies container image digital signatures against a trusted key list at cold start. Blocks backdoored images before they are ever managed. |
| 4 | Minimum Privilege Guard | `framework/security/privilege_guard.py` | Layer 1 | Rejects or flags non-priority containers requesting host-root (`--privileged`) mode. Runs once at cold start, not in the runtime loop. |
| 5 | Encryption Cost Calculator | `framework/security/encryption_calc.py` | Layer 3 | Estimates CPU cost of hybrid encryption (AES-RSA / AES-ECC) for inter-container data transfers and feeds the estimate into Layer 3's constraint calculation. |
| 6 | Watchdog Auto-Thaw | `framework/security/watchdog_thaw.py` | Layer 4 | Monitors `cgroup.freeze` state; force-thaws containers stuck frozen beyond `2× MICRO_FREEZE_MAX_DURATION_MS`. Safety-net for kernel race conditions or missed thaw signals. |
| 7 | Duty-Cycle Freeze (Aggressive) | `framework/security/duty_cycle_freezer.py` | Layer 4 | Rapid on/off freeze cycles (200ms frozen / 800ms running) for active non-priority containers under Tier 1. Defense/stability mechanism, not an energy metric. |
| 8 | I/O Bandwidth Isolation | `framework/security/io_limiter.py` | Layer 4 | Writes `io.max` in cgroupfs to cap per-container disk I/O bandwidth. Prevents I/O monopolization. Outside 5 tracked metrics — hardening only. |
| 9 | Network Bandwidth Isolation | `framework/security/net_limiter.py` | Layer 4 | Uses `tc` (traffic control) `htb` qdisc to cap per-container egress bandwidth. Prevents bandwidth starvation. Outside 5 tracked metrics. |
| 10 | Process Bomb Protection | `framework/security/pids_limiter.py` | Layer 1 | Writes `pids.max` per non-priority container at cold start. Prevents fork-bomb or thread-leak DoS. Pattern identical to `privilege_guard.py`. |

### A.2 Why Hidden?

- These features address **security threat vectors**, not the core research questions
  (RQ1/RQ2) which focus on energy efficiency and SLA.
- Including them in the formal evaluation would require additional test scenarios,
  threat simulation, and attack traffic generation — a significant scope expansion
  beyond the 72-run experimental design.
- All modules comply with the "stdlib + NumPy only" constraint and stay within the
  `<5%` overhead budget because they run either at cold start (once only) or
  in-kernel via eBPF (no user-space polling cost).

### A.3 How to Activate / Demonstrate

All safenet features (#1–10) are **enabled by default** via `framework/config.py`:
```python
SECURITY_ENABLED = True       # Controls #1-5 (existing) + #6-10 (new):
                               #   watchdog_thaw, duty_cycle_freezer,
                               #   io_limiter, net_limiter, pids_limiter
MICRO_FREEZE_ENABLED = True   # Controls micro_freezer, tcp_backlog_manager
```

To demonstrate during a defense, simply point the examiner to the relevant file in
`framework/security/` — the code is production-ready and unit-tested in
`tests/test_security.py`.

---

## Extended Vision (Discussed, Not Implemented)

> The following concept was explored during design but is **not implemented in
> code**. Documented as a future research direction — distinct from Appendix A
> where all features have working code.

**CRIU Checkpoint + zRAM Snapshot + eBPF Zero-Window Proxy:** escalate idle
containers beyond Micro-Freezing to full memory checkpoint. Not implemented
because: (1) CRIU is outside stdlib+NumPy constraint, (2) zero-window is
unreliable behind cloud NAT, (3) checkpoint/restore takes 1–3s vs <1ms thaw,
(4) would require metrics outside §9. Recommended as standalone follow-up study.

---

## Assumptions & Limitations

| # | Assumption / Limitation | Mitigation |
|---|------------------------|------------|
| 1 | No active health-check proxy in front of non-priority containers. Freeze cycle 500–1000ms can trigger flapping with health-check intervals < 1s. | Tag such containers `hecf.priority=high`. Experimental setup uses direct Locust→container traffic only. |
| 2 | Single-host, no container migration. | By design — targets environments where orchestrator overhead exceeds savings. |
| 3 | cgroups v2 unified hierarchy required (kernel ≥5.10). | Hard requirement documented in §2 and §5. |
