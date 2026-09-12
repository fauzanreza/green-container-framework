# 🌿 Hybrid Energy-Aware Container Framework (HECF)

**A Closed-Loop, Adaptive, and Energy-Aware Docker Resource Management System**

![Python Version](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Docker Native](https://img.shields.io/badge/Docker-Native-2496ED.svg?logo=docker)
![Version](https://img.shields.io/badge/Version-2.1-orange.svg)
![Resource Overhead](https://img.shields.io/badge/Overhead-&lt;5%25-success.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 📖 Overview

The **Hybrid Energy-Aware Container Framework (HECF) v2.1** is a specialized container management daemon designed for resource-constrained edge and home server environments (typically 1–4 vCPUs, 1–4 GB RAM).

HECF implements a **closed-loop MAPE-K control architecture** (Monitor → Analyze → Plan → Execute) that runs autonomously alongside any Docker workload. It leverages the native Docker SDK and Linux `cgroups v2`, strictly avoiding heavy external orchestrators like Kubernetes or Docker Swarm. Built entirely in Python with `numpy`, the framework maintains a strict self-overhead target of under **5% CPU and RAM**.

The framework is the core subject of an S2 (Master's) thesis, with three primary algorithmic contributions in Layer 3 and Layer 4.

---

## 🏗️ 4-Layer Architecture

HECF is composed of four tightly integrated layers, plus a supplementary energy subsystem and an optional security extension:

### Layer 1 — Environment Profiler (`profiler.py`)

Bootstraps the framework by reading host hardware capabilities from `/proc/cpuinfo` and `/proc/meminfo`. Performs container discovery and tagging via the Docker SDK, applying a hardcoded exclusion list (`EXCLUDED_CONTAINERS`) and a runtime port-based auto-exclusion (`CRITICAL_PORTS_EXCLUDE`) to ensure critical infrastructure services (databases, VPNs, SSH) are never throttled. High-priority containers (`CRITICAL_PORTS_PRIORITY`) are detected and tagged automatically.

### Layer 2 — Monitoring Engine (`monitor.py`)

Reads `cpu.stat` and `memory.stat` directly from the cgroupfs hierarchy for each managed container. Implements **Adaptive Sampling Frequency**: the polling interval drops to **10 seconds** when any container exceeds 60% CPU load, and relaxes back to **30 seconds** at idle — minimizing overhead without sacrificing reaction time.

### Layer 3 — Hybrid Control Engine *(Core S2 Innovation)*

Three algorithms run in sequence on every polling cycle:

| Sub-Layer | Module | Algorithm | Innovation |
|---|---|---|---|
| **3A** | `guardrail.py` | **Reactive Guardrail** | 3-of-5 rolling window debouncing + PSI internal signal + EMA pre-warning threshold adjustment |
| **3B** | `tier_detector.py` | **Volatility Tier Detection** | P95/P50 spike ratio classifier over 120-sample window + hysteresis (3 samples) to prevent tier thrashing |
| **3C** | `predictor.py` | **EMA Load Predictor** | `Y(t) = α × cpu + (1-α) × Y(t-1)`, α=0.2, O(1) memory — prediction feeds back into 3A to lower the guardrail threshold ahead of bursts |

### Layer 4 — Adaptive Resource Shaper (`shaper.py`)

Writes enforcement decisions directly to Linux cgroups (`cpu.max`, `memory.max`, `memory.swap.max`) via the Docker SDK. Operates on four quota levels computed from `config.py`:

| Action | CPU Quota | Memory Cap |
|---|---|---|
| `GUARDRAIL` | 0.5 core (50 000 µs) | 70% of host RAM |
| `AGGRESSIVE` | 0.75 core (75 000 µs) | 80% of host RAM |
| `BALANCED` | 0.9 core (90 000 µs) | *(not capped)* |
| `SOFT` / `OBSERVE` | Unlimited | *(not capped)* |

---

## 🔒 Security & Micro-Freeze Extensions (`framework/security/`)

Opt-in security modules activated via `HECF_SECURITY_ENABLED=true` and `HECF_MICRO_FREEZE_ENABLED=true`:

| Module | Function |
|---|---|
| `image_signer.py` | Image trust verification at container discovery |
| `privilege_guard.py` | Flags containers running with `--privileged` or dangerous capabilities |
| `ebpf_sensor.py` | eBPF-based container behavioural scan |
| `ddos_filter.py` | Network packet-rate threshold classifier |
| `edos_guard.py` | Economic DoS detection → freeze instead of throttle |
| `micro_freezer.py` | **❄️ Micro-Freezing** — writes `cgroup.freeze=1` to suspend idle non-priority containers at 0% CPU with full state preservation |
| `tcp_backlog_manager.py` | Cold-start `net.core.somaxconn` headroom verification |
| `watchdog_thaw.py` | Auto-thaw watchdog with configurable max freeze duration |
| `duty_cycle_freezer.py` | Duty-cycle based freeze/thaw scheduling |
| `io_limiter.py` | cgroups I/O weight limiting |
| `net_limiter.py` | `tc`-based network bandwidth limiting (best-effort) |
| `sandbox_isolator.py` | Full isolation for eBPF-flagged anomalous containers |
| `zombie_healer.py` | Detects and heals zombie container processes |

All security modules default to **disabled/dry-run** — the core 4-layer engine is always active regardless of security configuration.

---

## ⚙️ Operation Modes

HECF supports four selectable modes via `HECF_MODE` environment variable:

| Mode | Description |
|---|---|
| `full_hecf` | **Default** — All 4 layers active: Guardrail + Tier Detection + EMA Prediction + Shaping |
| `reactive_only` | Guardrail active only; no tier detection or EMA |
| `static_cap` | All containers capped at 80% CPU quota, no adaptive logic |
| `default_docker` | Observe-only; HECF logs metrics but applies no resource limits |

---

## 🌎 Energy & Carbon Estimator (`energy.py`)

HECF uses a **hybrid hardware/software power model** — it uses a real Intel RAPL / AMD hwmon hardware sensor when available, and falls back to a linear CPU-to-power model otherwise:

$$P(t) = P_{idle} + (P_{max} - P_{idle}) \times \frac{\text{cpu\%}}{100}$$

Proportional energy apportionment distributes total host power across containers by CPU share. Carbon intensity uses the Indonesian grid factor of **0.78 kg CO₂e/kWh**.

Default power parameters (configurable via env vars):
- `P_idle = 15 W`, `P_max = 54 W` (Intel Core i3 Gen 4 target)

---

## 📊 Evaluation Metrics (17 Metrics, 5 Pillars)

| # | Metric | Unit | Hypothesis |
|---|---|---|---|
| **Pilar 1: Resource Stability** ||||
| 1 | CPU Utilization (mean) | % | H1 (RQ2) |
| 2 | CPU Variance | %² | H1 (RQ2) |
| 3 | Memory Usage (mean) | GB | H1 (RQ2) |
| 4 | Memory Variance | %² | H1 (RQ2) |
| **Pilar 2: Operational Performance** ||||
| 5 | Latency Average | ms | H2 (RQ2) |
| 6 | Latency p95 | ms | H2 (RQ2) |
| 7 | Throughput | req/s | H2 (RQ2) |
| 8 | Error Rate | % | H2 (RQ2) |
| 9 | Container Restarts | count | H2 (RQ2) |
| **Pilar 3: Energy & Efficiency** ||||
| 10 | Power Consumption (mean) | Watt | H1 (RQ2) |
| 11 | Energy Consumption (total) | kWh | H1 (RQ2) |
| 12 | Idle Resource Waste | % | H1 (RQ2) |
| 13 | Performance-per-Watt (PPW) | req/J | H1 (RQ2) |
| **Pilar 4: Environmental Impact** ||||
| 14 | Estimated CO₂e | g CO₂ | H1 (RQ2) |
| 15 | Carbon per Task (CIT) | g/req | H1 (RQ2) |
| 16 | Thermal Stability | °C var | H2 (RQ2) |
| **Pilar 5: Meta-Metrics** ||||
| 17 | Framework Overhead | % CPU & RAM | H2 (RQ1) |

---

## 🚀 Getting Started

### Prerequisites

- Linux with **cgroups v2** enabled (Rocky Linux 9 recommended)
- Docker Engine ≥ 24 & Docker Compose v3.8+
- Python 3.10+ *(for local dev/testing)*

### Quickstart

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-username/green-container-framework.git
   cd green-container-framework
   ```

2. **Review configuration**

   Open `framework/config.py` — all parameters are overridable via environment variables. Key defaults:

   | Env Var | Default | Description |
   |---|---|---|
   | `HECF_MODE` | `full_hecf` | Operation mode |
   | `HECF_DRY_RUN` | `False` | If `true`, no cgroup writes are made |
   | `HECF_GUARDRAIL_CPU_THRESHOLD` | `80.0` | CPU % to trigger guardrail |
   | `HECF_GUARDRAIL_RAM_THRESHOLD` | `90.0` | RAM % to trigger guardrail |
   | `HECF_EMA_ALPHA` | `0.2` | EMA smoothing factor |
   | `HECF_SECURITY_ENABLED` | `true` | Enable security extensions |
   | `HECF_MICRO_FREEZE_ENABLED` | `true` | Enable micro-freeze subsystem |

   ⚠️ **Note:** `HECF_DRY_RUN` defaults to `False` in production mode. Set to `true` for safe observation-only evaluation.

3. **Tag containers for management**

   Add labels to containers you want HECF to manage in your `docker-compose.yml`:

   ```yaml
   labels:
     - "hecf.priority=low"   # low | medium | high
   ```

   Or manage the whitelist interactively through the dashboard UI (`targets.json`).

4. **Deploy HECF daemon + Analytics Dashboard**

   ```bash
   docker compose up -d --build
   ```

5. **Access the HECF Analytics Dashboard**

   ```
   http://localhost:8092
   ```

   The dashboard provides live container tracking, per-container energy estimates, action history, and framework on/off toggle.

---

## 🧪 Load Testing

HECF ships with **HttpArena** (a lightweight JSON benchmark target) and **Locust** integration for workload simulation. Four standard profiles:

| Profile | Users | Description |
|---|---|---|
| Low | ~10 | Baseline idle validation |
| Medium | ~50 | Normal operations |
| High | ~150 | Peak application load |
| Spike | ~300+ | Crash testing / Guardrail trigger |

```bash
locust -f locustfiles/locustfile.py \
  --host http://localhost:8000 \
  --headless -u 150 -r 10 --run-time 30m
```

Or use the automated experiment runner:

```bash
python experiments/run_experiment.py
```

---

## 📁 Repository Structure

```text
green-container-framework/
├── framework/
│   ├── main.py              ← MAPE-K control loop entry point
│   ├── config.py            ← All tunable parameters (env-var overridable)
│   ├── profiler.py          ← Layer 1: Host profiling & container discovery
│   ├── monitor.py           ← Layer 2: cgroupfs stats reader + adaptive sampling
│   ├── guardrail.py         ← Layer 3A: 3-of-5 debouncing + PSI + EMA pre-warning
│   ├── tier_detector.py     ← Layer 3B: P95/P50 spike ratio classifier + hysteresis
│   ├── predictor.py         ← Layer 3C: EMA load predictor (α=0.2)
│   ├── shaper.py            ← Layer 4: cgroups cpu.max / memory.max writer
│   ├── energy.py            ← Supplementary: hybrid HW/SW power model
│   ├── modes.py             ← Operation mode definitions
│   ├── overhead_tracker.py  ← Self-overhead measurement
│   ├── hardware_sensor.py   ← Intel RAPL / AMD hwmon sensor reader
│   └── security/            ← Optional security & micro-freeze extensions
├── dashboard.py             ← Flask + Gunicorn analytics dashboard
├── architecture-diagrams/   ← Mermaid flowcharts for thesis defense
├── locustfiles/             ← Locust load test profiles
├── experiments/             ← Automated experiment runner
├── http-arena/              ← Benchmark target service
├── docker-compose.yml
├── requirements.txt
└── metrics.csv              ← Runtime telemetry output (15 columns, atomic write)
```

---

## 📜 License

Distributed under the [MIT License](LICENSE).
