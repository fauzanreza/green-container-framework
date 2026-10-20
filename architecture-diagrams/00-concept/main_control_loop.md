# Flowchart — Main Control Loop (MAPE-K Per-Container Decision)

> **Kode Sumber:** `framework/main.py` → fungsi `main()` (baris 191–503), khususnya loop per-container (baris 271–478), logika keputusan mode (baris 357–410), Micro-Freezing (baris 412–432), dan post-loop (baris 480–503)  
> **Posisi di Diagram:** Ini adalah **alur keseluruhan** yang menyatukan Layer 1–4 + Supplementary  
> **Kategori:** 🌟 INOVASI ALGORITMA (S2) — Closed-Loop MAPE-K Orchestration  

Dokumen ini menjelaskan alur kerja loop kontrol tertutup (*closed-loop control*) HECF. Agar mudah dipahami, dokumen disusun dari **gambaran umum 4 fase**, **diagram konseptual modular**, **diagram teknis detail**, hingga **panduan narasi langkah demi langkah** dan **kamus istilah**.

---

## 🧭 1. Gambaran Umum (Bird's-Eye View: Siklus 4 Fase)

HECF bekerja secara periodik seperti "satpam patroli cerdas" berbasis model **MAPE-K** (*Monitor - Analyze - Plan - Execute - Knowledge*):

```mermaid
flowchart LR
    P0["<b>Fase 0: Cold-Start</b><br/>Deteksi Server & Modul<br/><i>(1x di awal)</i>"]:::phase --> P1["<b>Fase 1: Monitor</b><br/>Bangun tidur & baca data<br/>CPU/RAM cgroupfs v2"]:::phase
    P1 --> P2["<b>Fase 2: Analyze & Plan</b><br/>Tiering, Tren EMA,<br/>Guardrail, & Mode"]:::phase
    P2 --> P3["<b>Fase 3: Execute</b><br/>Set cgroup cpu.max<br/>atau Micro-Freeze"]:::phase
    P3 --> P4["<b>Fase 4: Knowledge & Sleep</b><br/>Tulis metrics.csv &<br/>Tidur 10s/30s (Hemat Daya)"]:::phase
    P4 -->|Siklus Patroli Berikutnya| P1

    classDef phase fill:#e8f4fd,stroke:#2b6cb0,stroke-width:2px,color:#1a365d;
```

---

## 🧩 2. Alur Logika Konseptual (Tersusun per Fase)

Diagram konseptual berikut membagi alur keputusan per kontainer ke dalam kelompok fase yang logis dan bersih:

```mermaid
flowchart TD
    START(["START: Inisialisasi Sistem"]) --> COLD_START["Cold-Start: Deteksi Spesifikasi Host (CPU, RAM, Watt Sensor)"]
    COLD_START --> LOOP_START(["Mulai Siklus Patroli (While True)"])

    %% FASE 1: MONITOR
    subgraph FASE_MONITOR["Fase 1: Pengamatan & Pengambilan Data (Monitor)"]
        SLEEP["Adaptive Sleep: Tidur sejenak<br/>10s jika sibuk, 30s jika tenang"]
        DISCOVER["Service Discovery: Cari kontainer aktif sesuai Whitelist"]
        CEK_TARGET{"Ada Target Aktif?"}
        BACA_DATA["Akuisisi Metrik: Baca CPU & RAM riil via cgroups v2"]
        CEK_STALE{"Data Valid?<br/>Bukan Stale Data"}
        SKIP_STALE["Abaikan kontainer ini<br/>mungkin baru saja mati"]
    end

    LOOP_START --> SLEEP
    SLEEP --> DISCOVER
    DISCOVER --> CEK_TARGET
    CEK_TARGET -->|Tidak| SLEEP
    CEK_TARGET -->|Ya| BACA_DATA
    BACA_DATA --> CEK_STALE
    CEK_STALE -->|Data Rusak| SKIP_STALE

    %% FASE 2: ANALYZE & PLAN
    subgraph FASE_ANALYZE["Fase 2: Analisis Cerdas & Rencana (Analyze & Plan)"]
        TIER["Tier Detector: Evaluasi stabilitas beban (P95/P50)"]
        EMA["EMA Predictor: Prediksi tren beban ke depan (alpha=0.2)"]
        GUARDRAIL_CHECK{"Beban Darurat?<br/>CPU di atas 80% atau RAM di atas 90%<br/>pada 3 dari 5 sampel"}
        PLAN_GUARDRAIL["🚨 Aksi: GUARDRAIL<br/>Cekik kuota CPU 0.8 core & RAM 70%"]
        BURST_CHECK{"Lonjakan Mendadak?<br/>spike_ratio di atas 1.5"}
        PLAN_SCALEUP["⬆️ Aksi: PREEMPTIVE SCALE-UP<br/>Buka kuota unlimited agar tidak lag"]
        PLAN_TIER["Aksi Berdasarkan Karakter Beban:<br/>• Tier 1: Kuota Ketat 80%<br/>• Tier 2: Kuota Moderat 90%<br/>• Tier 3: Kuota Bebas 100%"]
    end

    CEK_STALE -->|Data Valid| TIER
    TIER --> EMA
    EMA --> GUARDRAIL_CHECK
    GUARDRAIL_CHECK -->|Ya: Overload| PLAN_GUARDRAIL
    GUARDRAIL_CHECK -->|Tidak: Aman| BURST_CHECK
    BURST_CHECK -->|Ya: Spike| PLAN_SCALEUP
    BURST_CHECK -->|Tidak: Normal| PLAN_TIER

    %% FASE 3: EXECUTE
    subgraph FASE_EXECUTE["Fase 3: Eksekusi Alokasi Resource (Execute)"]
        IDLE_CHECK{"Kontainer Menganggur?<br/>Idle tanpa request"}
        ACTION_FREEZE["❄️ Micro-Freeze Kontainer<br/>+ Reclaim memory (Daya ke 0 Watt)"]
        ACTION_SHAPE["Tulis Jatah Kuota ke Kernel<br/>via cgroupfs cpu.max"]
    end

    PLAN_GUARDRAIL --> IDLE_CHECK
    PLAN_SCALEUP --> IDLE_CHECK
    PLAN_TIER --> IDLE_CHECK
    IDLE_CHECK -->|Ya: Idle| ACTION_FREEZE
    IDLE_CHECK -->|Tidak: Aktif| ACTION_SHAPE

    %% FASE 4: KNOWLEDGE & POST-LOOP
    subgraph FASE_KNOWLEDGE["Fase 4: Telemetri & Penyesuaian Siklus (Knowledge)"]
        HITUNG_DAYA["Estimasi Konsumsi Daya (Watt) & Energi (kWh)"]
        TULIS_CSV["Catat 16 Kolom Telemetri ke metrics.csv"]
        EVAL_INTERVAL{"Ada kondisi darurat /<br/>beban CPU di atas 60%?"}
        SET_FAST["Set interval = 10s (Patroli Cepat)"]
        SET_SLOW["Set interval = 30s (Hemat Daya)"]
    end

    ACTION_FREEZE --> HITUNG_DAYA
    ACTION_SHAPE --> HITUNG_DAYA
    SKIP_STALE --> HITUNG_DAYA
    HITUNG_DAYA --> TULIS_CSV
    TULIS_CSV --> EVAL_INTERVAL
    EVAL_INTERVAL -->|Ya| SET_FAST
    EVAL_INTERVAL -->|Tidak| SET_SLOW
    SET_FAST --> SLEEP
    SET_SLOW --> SLEEP
```

---

## 🛠️ 3. Diagram Teknis Kode Aktual (`framework/main.py`)

Diagram ini memetakan kode aktual dengan seluruh percabangan mode operasional (`default_docker`, `static_cap`, `reactive_only`, dan `full_hecf`), ekstensi keamanan, serta modul *micro-freezer*:

```mermaid
flowchart TD
    START(["main() — Inisialisasi"]) --> INIT["<b>Cold-Start Setup:</b><br/>• profile_host() (CPU, RAM, sensor Watt)<br/>• _init_security() (Security modules)<br/>• Inisialisasi metrics.csv & modul pelacak"]

    INIT --> LOOP_START(["WHILE TRUE: Loop Polling"])

    subgraph PRE_LOOP["1. Persiapan Siklus Patroli"]
        CHECK_ACTIVE["Baca status toggle Dashboard (is_active)"]
        SLEEP_NODE["time.sleep(current_interval)<br/>10s saat beban tinggi, 30s saat normal"]
        READ_HW["Baca daya riil via hw_sensor.get_power_watts()"]
        DISCOVER["discover_containers(): Filter Whitelist & env HECF_TARGETS"]
        SEC_GATE["_apply_security_gates(): Image signing & Privilege guard"]
        NO_TARGET{"Target kosong?"}
    end

    LOOP_START --> CHECK_ACTIVE
    CHECK_ACTIVE --> SLEEP_NODE
    SLEEP_NODE --> READ_HW
    READ_HW --> DISCOVER
    DISCOVER --> SEC_GATE
    SEC_GATE --> NO_TARGET
    NO_TARGET -->|Ya| SLEEP_NODE
    NO_TARGET -->|Tidak| CONTAINER_LOOP

    subgraph PER_CONTAINER["2. Evaluasi per Target Kontainer"]
        CONTAINER_LOOP(["FOR EACH target container"])
        
        ZOMBIE_CHECK{"ZombieHealer:<br/>Perlu restart?"}
        DO_HEAL["heal(): Restart kontainer & skip shaping"]
        
        READ_CGROUP["monitor.get_stats():<br/>Baca cpu.stat, memory.current, memory.stat"]
        STALE_CHECK{"Data stale?<br/>Gagal baca"}
        DO_SKIP["Log warning & lewati kontainer ini"]

        CALC_L3["Hitung Metrik Cerdas:<br/>• tier_detector.add_sample() → P50, P95, spike_ratio<br/>• predictor.update() → EMA tren beban<br/>• guardrail.update() → Evaluasi ambang batas darurat"]

        MODE_SELECT{"Mode Operasional?"}

        BRANCH_DOCKER["default_docker:<br/>action = OBSERVE, quota = unlimited"]
        BRANCH_STATIC["static_cap:<br/>action = STATIC, quota = 80% (80000)"]
        BRANCH_REACTIVE["reactive_only:<br/>Jika Guardrail aktif → quota 80%<br/>Jika normal → quota unlimited"]

        subgraph FULL_HECF_LOGIC["Mode: full_hecf (Sistem yang Diajukan)"]
            GR_CHECK{"Guardrail aktif?<br/>3-of-5 overload"}
            DO_GR["action = GUARDRAIL<br/>quota = 80%, mem_ratio = 70%"]
            SPIKE_CHECK{"spike_ratio di atas 1.5?<br/>Burst traffic"}
            DO_PREEMPT["action = PREEMPTIVE_SCALEUP<br/>quota = unlimited (cegah lag)"]
            TIER_BRANCH{"Tier yang ter-commit?"}
            DO_T1["Tier 1: AGGRESSIVE (quota 80%, mem 80%)"]
            DO_T2["Tier 2: BALANCED (quota 90%)"]
            DO_T3["Tier 3: SOFT (quota unlimited)"]
        end

        subgraph FREEZE_LOGIC["Layer 4 Ext: Micro-Freezer"]
            MF_EVAL["micro_freezer.evaluate():<br/>Cek prioritas, idle counter, & traffic"]
            MF_RES{"Keputusan?"}
            DO_FREEZE["action = MICRO_FREEZE<br/>quota = unlimited, memory.reclaim"]
            DO_NORMAL["action tetap sesuai keputusan mode"]
        end

        APPLY_CGROUP["shaper.shape_container():<br/>Tulis cpu.max & memory.max ke kernel Linux"]
        EST_ENERGY["energy.estimate_all():<br/>Hitung konsumsi daya (Watt) & kWh"]
        APPEND_ROW["Susun baris data metrik (16 kolom)"]
    end

    CONTAINER_LOOP --> ZOMBIE_CHECK
    ZOMBIE_CHECK -->|Ya| DO_HEAL
    DO_HEAL --> APPEND_ROW
    ZOMBIE_CHECK -->|Tidak| READ_CGROUP
    READ_CGROUP --> STALE_CHECK
    STALE_CHECK -->|Ya| DO_SKIP
    DO_SKIP --> APPEND_ROW
    STALE_CHECK -->|Tidak| CALC_L3

    CALC_L3 --> MODE_SELECT
    MODE_SELECT -->|default_docker| BRANCH_DOCKER
    MODE_SELECT -->|static_cap| BRANCH_STATIC
    MODE_SELECT -->|reactive_only| BRANCH_REACTIVE
    MODE_SELECT -->|full_hecf| GR_CHECK

    GR_CHECK -->|Ya| DO_GR
    GR_CHECK -->|Tidak| SPIKE_CHECK
    SPIKE_CHECK -->|Ya| DO_PREEMPT
    SPIKE_CHECK -->|Tidak| TIER_BRANCH
    TIER_BRANCH -->|Tier 1| DO_T1
    TIER_BRANCH -->|Tier 2| DO_T2
    TIER_BRANCH -->|Tier 3| DO_T3

    BRANCH_DOCKER --> MF_EVAL
    BRANCH_STATIC --> MF_EVAL
    BRANCH_REACTIVE --> MF_EVAL
    DO_GR --> MF_EVAL
    DO_PREEMPT --> MF_EVAL
    DO_T1 --> MF_EVAL
    DO_T2 --> MF_EVAL
    DO_T3 --> MF_EVAL

    MF_EVAL --> MF_RES
    MF_RES -->|Freeze| DO_FREEZE
    MF_RES -->|Thaw atau Normal| DO_NORMAL
    DO_FREEZE --> EST_ENERGY
    DO_NORMAL --> APPLY_CGROUP
    APPLY_CGROUP --> EST_ENERGY
    EST_ENERGY --> APPEND_ROW

    subgraph POST_LOOP["3. Pasca-Loop: Telemetri & Penyesuaian"]
        CSV_WRITE["_write_csv_atomic(): Tulis seluruh baris ke metrics.csv"]
        CLEANUP["Cleanup: Hapus cache state kontainer yang sudah mati"]
        ESCALATED_CHECK{"Ada kontainer berstatus<br/>GUARDRAIL / AGGRESSIVE /<br/>BALANCED / EDOS_FREEZE?"}
        FAST_POLL["current_interval = 10s (Respon Cepat)"]
        ADAPTIVE_POLL["current_interval = get_adaptive_interval()<br/>CPU di atas 60% jadi 10s, lainnya 30s"]
    end

    APPEND_ROW -->|Kontainer berikutnya| CONTAINER_LOOP
    APPEND_ROW -->|Semua kontainer selesai| CSV_WRITE
    CSV_WRITE --> CLEANUP
    CLEANUP --> ESCALATED_CHECK
    ESCALATED_CHECK -->|Ya| FAST_POLL
    ESCALATED_CHECK -->|Tidak| ADAPTIVE_POLL
    FAST_POLL --> LOOP_START
    ADAPTIVE_POLL --> LOOP_START
```

> **Catatan Teknis Penting:**
> 1. **`PREEMPTIVE_SCALEUP`**: Pada mode `full_hecf`, saat tidak ada status Guardrail, sistem mengecek `spike_ratio > 1.5` terlebih dahulu. Jika terdeteksi lonjakan mendadak, kuota CPU langsung dilepas (*unlimited*) agar lonjakan request diserap dengan cepat tanpa lag.
> 2. **Evaluasi Micro-Freezing**: Dijalankan setelah keputusan alokasi resource dibuat (pada seluruh mode yang mengaktifkan micro-freezer). Jika kontainer idle, pembekuan mengesampingkan pembatasan kuota normal.
> 3. **Interval Cepat Dipaksa (10s)**: Interval dipercepat ke 10 detik apabila ada kontainer dalam status `GUARDRAIL`, `AGGRESSIVE`, `BALANCED`, atau `EDOS_FREEZE` agar proses mitigasi maupun de-eskalasi berlangsung responsif.

---

## 🎙️ 4. Panduan Menjelaskan Alur Langkah demi Langkah

Jika Anda perlu mempresentasikan diagram ini, ikuti alur narasi berikut:

| No | Tahap | Apa yang Terjadi? | Mengapa Dilakukan? (Tujuan) |
| :---: | :--- | :--- | :--- |
| **0** | **Cold-Start Setup** | Sistem mendeteksi spesifikasi server (jumlah CPU, RAM total, sensor daya listrik). | Agar batasan kuota dihitung proporsional terhadap kapasitas asli server fisik. |
| **1** | **Adaptive Sleep** | Framework tidur sejenak (**30 detik** saat tenang, atau **10 detik** saat sibuk). | **Hemat daya host.** Menghindari loop CPU 100% dan menjaga overhead HECF tetap $<5\%$. |
| **2** | **Discovery & Validation** | Mencari kontainer target via Docker API dan membaca file status kernel (`cgroupfs v2`). Jika data tidak terbaca (**stale**), kontainer dilewati. | Mencegah crash jika kontainer baru saja dimatikan atau sistem sedang sibuk membaca virtual file. |
| **3** | **Analisis Cerdas (Layer 3)** | Menghitung kestabilan beban (**Tier Detector**), memprediksi tren masa depan (**EMA**), dan mengecek kondisi bahaya (**Guardrail**). | Menghasilkan keputusan berbasis data riil dan prediksi, bukan sekadar aturan statis. |
| **4** | **Pengambilan Keputusan** | <ul><li>**Overload Bahaya?** $\to$ Aktifkan Guardrail (cekik CPU).</li><li>**Lonjakan Mendadak?** $\to$ Pre-emptive Scale-up (lepas batas).</li><li>**Normal?** $\to$ Ikuti Tier (Tier 1: ketat, Tier 2: sedang, Tier 3: bebas).</li></ul> | Menyeimbangkan penghematan energi dengan jaminan SLA performa aplikasi. |
| **5** | **Micro-Freeze & Cgroup Write** | Jika aplikasi menganggur (idle), bekukan prosesnya. Jika aktif, tulis nilai kuota ke kernel Linux (`cpu.max`). | Mengurangi daya kontainer idle hingga mendekati 0 Watt tanpa mematikan aplikasi. |
| **6** | **Pencatatan & Penyesuaian** | Hitung konsumsi daya (Watt & kWh), tulis ke `metrics.csv`, dan tentukan interval tidur putaran berikutnya. | Menyediakan data eksperimen yang lengkap dan akurat secara *atomic*. |

---

## 📖 5. Kamus Istilah Teknis (Glosarium)

* **MAPE-K (*Monitor, Analyze, Plan, Execute, Knowledge*)**: Pola arsitektur standar komputasi otonom di mana sistem mengamati dirinya sendiri dan melakukan adaptasi secara otomatis tanpa intervensi manual.
* **Adaptive Sleep Interval (10s / 30s)**: Mekanisme tidur berkala yang fleksibel: 30 detik saat beban rendah demi meminimalkan penggunaan daya oleh framework sendiri, atau 10 detik saat beban tinggi/darurat agar respon mitigasi cepat.
* **Stale Data**: Data pembacaan cgroupfs v2 yang usang, kosong, atau gagal diambil (misalnya karena kontainer baru saja berhenti atau terhapus). Sistem menandainya agar tidak salah menjatah CPU.
* **Cold-Start**: Tahap awal ketika HECF pertama kali dihidupkan untuk mengenali profil perangkat keras dan mengumpulkan sampel awal sebelum menerapkan kebijakan agresif.
* **Guardrail (3-of-5 samples)**: Rem darurat. Jika penggunaan CPU $>80\%$ atau RAM $>90\%$ terjadi pada minimal 3 dari 5 sampel pemantauan terakhir, sistem langsung melakukan throttling ketat demi menyelamatkan stabilitas host.
* **EMA (*Exponential Moving Average*)**: Algoritma statistik berbobot eksponensial ($\alpha = 0.2$) yang memproyeksikan arah kenaikan atau penurunan beban CPU di masa depan.
* **Pre-emptive Scale-Up**: Pelepasan batas kuota CPU (*unlimited*) saat terdeteksi lonjakan lalu lintas yang curam (`spike_ratio > 1.5`) agar antrean request tidak tertahan (*lag*) dan latensi p95 tetap aman.
* **Micro-Freezing & Thaw**: 
  - *Freeze:* Membekukan proses kontainer menggunakan *cgroup freezer* saat tidak ada request, membebaskan cache memori, dan menurunkan konsumsi daya ke level terendah.
  - *Thaw:* Mencairkan dan mengaktifkan kembali kontainer begitu ada aktivitas komputasi atau traffic baru.
* **Cgroups v2 (*Control Groups*)**: Fitur kernel Linux modern yang digunakan HECF untuk membatasi dan mengisolasi resource CPU (`cpu.max`) dan memori (`memory.max`) secara langsung di level sistem operasi.
* **Hysteresis**: Mekanisme penundaan perpindahan status (memerlukan 3 sampel berturut-turut) untuk mencegah perubahan status yang terlalu sering atau tidak stabil akibat fluktuasi sesaat.
