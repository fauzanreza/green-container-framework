<div align="center">
  <h1>🌿 Hybrid Green Container Framework (HGCF)</h1>
  <p><b>An Adaptive, Lightweight, and Energy-Aware Docker Management System</b></p>
  
  <p>
    <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python Version" />
    <img src="https://img.shields.io/badge/Docker-Native-2496ED.svg?logo=docker" alt="Docker Native" />
    <img src="https://img.shields.io/badge/Overhead-&lt;5%25-success.svg" alt="Resource Overhead" />
    <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" />
  </p>
</div>

<hr />

## 📖 Overview

The **Hybrid Green Container Framework (HGCF) v1.01** is a specialized container management solution primarily designed for resource-constrained edge/home server environments (typically 1-4 vCPUs and 1-4 GB RAM). 

HGCF operates semi-autonomously by leveraging the native Docker SDK and Linux `cgroups`, strictly avoiding heavy external orchestrators like Kubernetes or Docker Swarm. Built strictly utilizing Python and `numpy`, the framework ensures maximum efficiency with a strict system overhead priority of under **5%**.

## 🏗️ 4-Layer Architecture

HGCF is composed of a tightly integrated, hierarchical 4-Layer architecture:

### 1. Environment Profiler (`profiler.py`)
Automatically reads the host’s baseline hardware capabilities by mounting `/proc/cpuinfo` and `/proc/meminfo`. Uses a Fallback Tier 2 (Balanced) approach natively when the framework boots up cold (fewer than 120 samples available).

### 2. Monitoring Engine (`monitor.py`)
Pulls metrics continuously from the Docker Stats API and host cgroups. Utilizes an innovative **Adaptive Sampling Frequency**: it samples aggressively every 10 seconds under heavy load (>60% CPU) and relaxes to 30 seconds when resting idle.

### 3. Hybrid Control Engine (`engine.py`, `guardrail.py`, `tier_detector.py`, `predictor.py`)
Features a 3-stage predictive-reactive AI logic:
- **Real-time Guardrail:** Kicks in dynamically if CPU > 80% or RAM > 90% in 3 out of the last 5 samples to prevent crashing.
- **Tier Detection:** Analyzes a sliding window of 120 samples applying ratio classifiers (Aggressive, Balanced, Soft).
- **Lightweight Prediction:** Utilizes a modified Adaptive Filter Moving Average (AFMV) to predict the short-term burstiness securely without bloated Machine Learning libraries.

### 4. Adaptive Resource Shaping (`shaper.py`)
Interprets the intelligent decisions from Layer 3 and enforces hard Linux `cgroups` rules instantly via real-time Docker parameter adjustments (`--cpus`, `--cpu-quota`, `--memory`).

---

## 🌎 Energy & Carbon Estimator 

HGCF uses a linear CPU-to-power mathematical model completely omitting the need for external hardware IoT power meters:
- **Processor Target:** Intel Core i3 Gen 4 ($P_{idle} = 15W$, $P_{max} = 65W$)
- **Environment:** Evaluated utilizing the Indonesian power grid carbon intensity of **0.78 kg $CO_2e$/kWh**.

---

## 📊 Comprehensive 17 Metrics Evaluation

The architecture maps completely to 5 Evaluation Pillars comprising precisely 17 key metrics, rigorously linking theoretical hypotheses (H1, H2) with Research Questions (RQ1, RQ2):

### Pilar 1: Resource Stability
1. **CPU Utilization (mean)** `[%]` - H1 (RQ2)
2. **CPU Variance** `[%²]` - H1 (RQ2)
3. **Memory Usage (mean)** `[GB]` - H1 (RQ2)
4. **Memory Variance** `[%²]` - H1 (RQ2)

### Pilar 2: Operational Performance (via Locust)
5. **Latency Average** `[ms]` - H2 (RQ2)
6. **Latency p95** `[ms]` - H2 (RQ2)
7. **Throughput** `[req/s]` - H2 (RQ2)
8. **Error Rate** `[%]` - H2 (RQ2)
9. **Container Restart** `[count]` - H2 (RQ2)

### Pilar 3: Energy & Efficiency
10. **Power Consumption (mean)** `[Watt]` - H1 (RQ2)
11. **Energy Consumption (total)** `[kWh]` - H1 (RQ2)
12. **Idle Resource Waste** `[%]` - H1 (RQ2)
13. **Performance-per-Watt (PPW)** `[req/J]` - H1 (RQ2)

### Pilar 4: Environmental Impact
14. **Estimated CO₂e** `[gCO₂]` - H1 (RQ2)
15. **Carbon per Task (CIT)** `[g/req]` - H1 (RQ2)
16. **Thermal Stability** `[°C var]` - H2 (RQ2)

### Pilar 5: Meta-Metrics
17. **Framework Overhead** `[% CPU & RAM]` - H2 (RQ1)

---

## 🚀 Getting Started

HGCF is deployed alongside its very own lightweight Analytics UI Dashboard.

### Prerequisites
- Docker & Docker-Compose (v3.8+)
- Rocky Linux 9 (or fully compatible Linux environments supporting Cgroups).

### Quickstart

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/green-container-framework.git
   cd green-container-framework
   ```

2. **Configure Permissions (Crucial)**
   The agent utilizes the host’s socket and metrics files. Open `framework/config.py` and ensure parameters fit your environment. Be sure to configure target lists in `docker-compose.yml`.
   
   ⚠️ _**Note:** By default `DRY_RUN = True`. For production enforcement shaping, edit `config.py` and set it to `False`._

3. **Deploy HGCF Daemon & UI**
   ```bash
   docker compose up -d --build
   ```

4. **Access the Beszel-style HGCF Analytics Dashboard**
   Navigate to:
   ```url
   http://localhost:8092
   ```

## 🧪 Testing Workload
To artificially simulate load against your services, we incorporate HttpArena and **Locust**. Four benchmark profiles are available natively via Locust:
- **Low**: Baseline Idle Validation
- **Medium**: Normal Operations
- **High**: Peak Application Load
- **Spike**: Crash Testing / Guardrail trigger testing.

Run Locust directly using:
```bash
locust -f locustfiles/locustfile.py --host http://<TARGET_URI> --headless -u 150 -r 10 --run-time 30m
```

## 📜 License
Distribute your code openly cleanly under the [MIT License](LICENSE).
