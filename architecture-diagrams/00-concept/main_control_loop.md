# Flowchart — Main Control Loop (MAPE-K Per-Container Decision)

> **Kode Sumber:** `framework/main.py` → fungsi `main()` (baris 190–480), khususnya loop per-container (baris 270–460)
> **Posisi di Diagram:** Ini adalah **alur keseluruhan** yang menyatukan Layer 1–4 + Supplementary
> **Kategori:** 🌟 INOVASI ALGORITMA (S2) — Closed-Loop MAPE-K Orchestration

Flowchart ini menunjukkan bagaimana semua algoritma terintegrasi dalam satu **siklus kontrol tertutup** per polling cycle. Inilah "otak utama" HECF.

```mermaid
flowchart TD
    START(["main() — HECF Control Loop Start"])

    INIT["<b>Cold-Start Initialization</b><br/>• profile_host() → cpu_count, mem, P_idle, P_max, hw_sensor<br/>• _init_security() → security modules<br/>• Initialize: Monitor, Guardrail, TierDetector, EMAPredictor<br/>• current_interval = 30s"]

    LOOP_START(["WHILE TRUE — Polling Cycle"])

    CHECK_ACTIVE["Baca framework_status.json<br/>is_active = True/False"]
    SLEEP["time.sleep(current_interval)<br/>(10s atau 30s, adaptif)"]
    READ_HW["Baca hardware power sensor<br/>(jika tersedia)"]

    DISCOVER["<b>Layer 1:</b> discover_containers()<br/>Discover + Tag + Whitelist Filter"]
    SECURITY_GATE["Security Gate:<br/>Image signing + Privilege guard"]
    NO_TARGETS{"Tidak ada<br/>container?"}
    WAIT["Warning: No targets<br/>Kembali ke loop"]

    OVERHEAD["overhead_tracker.get_overhead()<br/>Ukur CPU/RAM HECF sendiri"]

    CONTAINER_LOOP(["FOR EACH container in targets"])

    subgraph PER_CONTAINER["Per-Container Processing"]
        L2_MONITOR["<b>Layer 2:</b> monitor.get_stats(name, id)<br/>Baca cpu.stat, memory.stat dari cgroupfs"]
        STALE{"Stats<br/>stale?"}
        SKIP_STALE["Skip shaping<br/>(container mungkin mati)"]

        L3B["<b>Layer 3B:</b> tier_detector.add_sample(name, cpu)<br/>tier_int = tier_detector.get_tier(name)<br/><i>P95/P50 + Hysteresis</i>"]
        L3C["<b>Layer 3C:</b> ema_pred = predictor.update(name, cpu)<br/><i>Y(t) = α × cpu + (1-α) × Y(t-1)</i>"]
        L3A["<b>Layer 3A:</b> guardrail.update(name, cpu, mem, ema_pred)<br/><i>3-of-5 rolling + PSI + EMA threshold adjust</i>"]

        MODE_CHECK{"MODE?"}

        DEFAULT_DOCKER["default_docker:<br/>action = OBSERVE<br/>quota = unlimited"]
        STATIC_CAP["static_cap:<br/>action = STATIC<br/>quota = 80% fixed"]
        REACTIVE_ONLY["reactive_only:<br/>Guardrail aktif → GUARDRAIL<br/>Tidak aktif → SOFT"]

        subgraph FULL_HECF["full_hecf (Sistem yang Diajukan)"]
            GR_ACTIVE{"Guardrail<br/>aktif?"}
            GR_ACTION["action = GUARDRAIL<br/>quota = 50000 (0.5 core)<br/>mem_ratio = 0.70"]
            TIER_BRANCH{"tier_int?"}
            T1["Tier 1 → AGGRESSIVE<br/>quota = 75000 (0.75 core)<br/>mem_ratio = 0.80"]
            T2["Tier 2 → BALANCED<br/>quota = 90000 (0.9 core)"]
            T3["Tier 3 → SOFT<br/>quota = unlimited"]
        end

        MICRO_FREEZE_CHECK["<b>Layer 4 ext:</b> Micro-Freeze evaluate<br/>Cek idle + populated + safety"]
        MF_RESULT{"Freeze<br/>eligible?"}
        MF_ACTION["action = MICRO_FREEZE<br/>cgroup.freeze = 1<br/>quota = skip (CPU already 0%)"]
        MF_THAW["Container di-thaw<br/>Resume normal shaping"]

        L4_SHAPE["<b>Layer 4:</b> shape_container()<br/>Tulis cpu.max, memory.max ke cgroups"]

        ENERGY_EST["<b>Supplementary:</b> estimate_all()<br/>Hitung power (W) dan energy (kWh)"]

        CSV_ROW["Kumpulkan CSV row:<br/>time, name, cpu, mem, tier,<br/>action, power, energy, ema,<br/>alpha, spike_ratio, p50, p95,<br/>overhead_cpu, overhead_mem"]
    end

    CSV_WRITE["Atomic CSV write:<br/>Append semua row ke metrics.csv"]
    CLEANUP["Cleanup state container<br/>yang sudah hilang"]
    ADAPTIVE["current_interval =<br/>get_adaptive_interval(max_cpu_seen)"]

    START --> INIT
    INIT --> LOOP_START
    LOOP_START --> CHECK_ACTIVE
    CHECK_ACTIVE --> SLEEP
    SLEEP --> READ_HW
    READ_HW --> DISCOVER
    DISCOVER --> SECURITY_GATE
    SECURITY_GATE --> NO_TARGETS
    NO_TARGETS -->|Ya| WAIT
    WAIT --> LOOP_START
    NO_TARGETS -->|Tidak| OVERHEAD
    OVERHEAD --> CONTAINER_LOOP

    CONTAINER_LOOP --> L2_MONITOR
    L2_MONITOR --> STALE
    STALE -->|Ya| SKIP_STALE

    STALE -->|Tidak| L3B
    L3B --> L3C
    L3C --> L3A

    L3A --> MODE_CHECK
    MODE_CHECK -->|default_docker| DEFAULT_DOCKER
    MODE_CHECK -->|static_cap| STATIC_CAP
    MODE_CHECK -->|reactive_only| REACTIVE_ONLY
    MODE_CHECK -->|full_hecf| GR_ACTIVE

    GR_ACTIVE -->|Ya| GR_ACTION
    GR_ACTIVE -->|Tidak| TIER_BRANCH
    TIER_BRANCH -->|1| T1
    TIER_BRANCH -->|2| T2
    TIER_BRANCH -->|3| T3

    GR_ACTION --> MICRO_FREEZE_CHECK
    T1 --> MICRO_FREEZE_CHECK
    T2 --> MICRO_FREEZE_CHECK
    T3 --> MICRO_FREEZE_CHECK
    DEFAULT_DOCKER --> ENERGY_EST
    STATIC_CAP --> MICRO_FREEZE_CHECK
    REACTIVE_ONLY --> MICRO_FREEZE_CHECK

    MICRO_FREEZE_CHECK --> MF_RESULT
    MF_RESULT -->|Ya, freeze| MF_ACTION
    MF_RESULT -->|Thaw| MF_THAW
    MF_RESULT -->|Tidak| L4_SHAPE

    MF_ACTION --> ENERGY_EST
    MF_THAW --> L4_SHAPE
    L4_SHAPE --> ENERGY_EST
    ENERGY_EST --> CSV_ROW

    CSV_ROW -->|Container berikutnya| CONTAINER_LOOP
    CSV_ROW -->|Semua selesai| CSV_WRITE
    SKIP_STALE -->|Container berikutnya| CONTAINER_LOOP

    CSV_WRITE --> CLEANUP
    CLEANUP --> ADAPTIVE
    ADAPTIVE --> LOOP_START
```
