# Product Requirements Document (PRD)
## Hybrid Green Container Framework (HGCF)

### 1. Project Overview & Philosophy
The **Hybrid Green Container Framework (HGCF)** is an adaptive, lightweight, and energy-aware Docker-native container management system. It is uniquely designed to operate efficiently within resource-constrained environments, ensuring that host servers utilize minimal energy while maintaining stable application performance. 

The primary philosophy of HGCF is to avoid the overhead of heavy orchestrators like Kubernetes or Docker Swarm. It operates autonomously via the Docker SDK for Python, keeping its system resource footprint strictly minimal (targeting <5% resource overhead).

### 2. Target Environment
- **Hardware:** Resource-constrained home servers (e.g., Intel Core i3 4th Gen).
- **Capacity:** 1-4 vCPUs and 1-4 GB RAM.
- **OS:** Rocky Linux 9 or compatible Linux distributions.
- **Dependencies:** Standard Python 3, `numpy`, `docker` SDK, `requests`, `locust` (for load testing), and `Flask` (for dashboarding).

### 3. Objectives & Goals
- **Energy Efficiency:** Minimize energy consumption of containerized applications through real-time resource shaping and capping based on intelligent heuristics.
- **Carbon Footprint Tracking:** Estimate and report the server's equivalent carbon emissions (CO₂e) using localized grid carbon intensity metrics.
- **Zero Heavy-ML Overhead:** Perform resource prediction and pattern classification without relying on large machine learning libraries (such as TensorFlow, PyTorch, or Pandas).
- **Stability under Spikes:** Prevent the server from crashing or suffering extreme resource starvation during traffic spikes through a robust, real-time guardrail system.

### 4. Core Features & Functional Requirements

#### 4.1. 4-Layer Adaptive Architecture
The framework must implement a strict 4-layer architecture:
- **Layer 1: Environment Profiler**
  - Automatically detects the host's CPU and RAM capacities upon initialization by reading `/proc/cpuinfo` and `/proc/meminfo`.
  - Implements a *Cold-Start Fallback* (Tier 2 - Balanced) if the system has not yet gathered sufficient metric samples (< 120 samples).
  
- **Layer 2: Monitoring Engine**
  - Extracts CPU and Memory metrics natively via the Docker Stats API and cgroups.
  - Implements **Adaptive Sampling**: Polling frequency must be exactly 10 seconds when CPU > 60%, and gracefully slow down to 30 seconds under normal/low load to save profiling overhead.

- **Layer 3: Hybrid Control Engine**
  - **3A. Real-time Guardrail:** Emergency throttle response. Activates if CPU > 80% or RAM > 90% in 3 out of the last 5 polling samples.
  - **3B. Tier Detection:** Sliding window of the last 120 samples. Calculates the `spike_ratio` (95th percentile / 50th percentile CPU usage).
    - *Aggressive (Tier 1):* Ratio > 2.0
    - *Balanced (Tier 2):* Ratio >= 1.5 and <= 2.0
    - *Soft (Tier 3):* Ratio < 1.5
  - **3C. Lightweight Prediction:** Uses an Adaptive Filter Moving Average (AFMV) based on variance/STDEV instead of standard Exponential Moving Average to predict short-term utilization trends efficiently.

- **Layer 4: Adaptive Resource Shaping**
  - Actively translates Layer 3's calculated decisions into real-time Docker cgroup parameters (`--cpu-quota`).
  - Gracefully limits or releases container boundaries dynamically without requiring container restarts.

#### 4.2. Energy & Carbon Estimation
- Uses a linear CPU-to-power estimation model without requiring physical smart meters.
- Applies standard coefficients for Intel i3 Gen 4: $P_{idle} = 15W$, $P_{max} = 65W$.
- Calculates Carbon Emisson assuming Indonesia's Grid Carbon Intensity ($0.78 \text{ kg } CO_{2}e/kWh$).

#### 4.3. Real-time Metrics Dashboard
- Provides a centralized web UI accessible via a lightweight Flask server.
- Visualizes the resource metrics, energy consumption, and carbon footprint estimated across 17 evaluation metrics in real-time.

### 5. Non-Functional Requirements
- **Strict Library Constraints:** MUST NOT use Pandas, Scikit-Learn, PyTorch, or TensorFlow. Computation must be executed purely via standard library and Numpy.
- **Privileged Isolation:** HGCF must be deployed in its own Docker compose service. It must run in privileged mode with mounts mapped to `/var/run/docker.sock` and `/sys/fs/cgroup`.
- **Configurability:** All thresholds, window sizes, and constants must be centralized in a single `config.py` file for ease of tuning.

### 6. Testing & Validation Workloads
- HGCF will be validated in an isolated environment against `HttpArena`.
- **Locust** will be used as a traffic load generator to simulate 4 distinctive intensity tiers: Low, Medium, High, and Spike.
