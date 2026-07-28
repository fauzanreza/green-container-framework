# Architecture Diagrams — HECF Thesis Defense

Kumpulan diagram arsitektur dan flowchart algoritma untuk sidang/defense tesis S2.
Setiap file `.md` mengandung Mermaid flowchart yang akurat berdasarkan kode sumber aktual.

> **Aturan:** Di setiap file, baris pertama mencantumkan path kode sumber asli yang menjadi dasar flowchart. Tidak ada spekulasi — setiap node dan percabangan diambil dari logika kode nyata.

---

## Struktur Direktori

```
architecture-diagrams/
│
├── README.md                          ← File ini
│
├── 00-concept/                        ← Diagram Konsep Besar
│   ├── big_picture.md                 ← MAPE-K Closed-Loop Overview
│   ├── tools_infrastructure.md        ← Docker, Kernel, Locust, HttpArena (Tools)
│   └── main_control_loop.md           ← Master Flowchart: Semua Layer Terintegrasi
│
├── layer-1-profiler/                  ← Layer 1: Environment Profiler
│   ├── 01_profile_host.md             ← [Tools] Hardware detection, /proc verification
│   ├── 02_discover_containers.md      ← [Tools] Container discovery & tagging & whitelist
│   └── 03_hardware_sensor.md          ← [Tools] Intel RAPL / AMD hwmon sensor detection
│
├── layer-2-monitor/                   ← Layer 2: Monitoring Engine
│   └── 01_monitor_get_stats.md        ← [Tools + Inovasi] cgroupfs reader + Adaptive Sampling
│
├── layer-3-control/                   ← Layer 3: Hybrid Control Engine ★ CORE S2
│   ├── 01_guardrail.md                ← [INOVASI] 3A: 3-of-5 Debouncing + PSI + EMA adjust
│   ├── 02_tier_detector.md            ← [INOVASI] 3B: P95/P50 Spike Ratio + Hysteresis
│   └── 03_ema_predictor.md            ← [INOVASI] 3C: EMA α=0.2, O(1) → Guardrail integration
│
├── layer-4-shaper/                    ← Layer 4: Adaptive Resource Shaping
│   ├── 01_shaper.md                   ← [Tools] cpu.max/memory.max/swap cgroups writer
│   ├── 02_micro_freezer.md            ← [INOVASI] Micro-Freezing: cgroup.freeze + idle detection
│   └── 03_tcp_backlog.md              ← [INOVASI] TCP Backlog capacity verification
│
└── supplementary/                     ← Supplementary Services
    └── 01_energy_estimator.md         ← [INOVASI] Hybrid HW/SW Energy Model + Proportional Apportionment
```

---

## Kategori Klasifikasi

| Kategori | Warna di Diagram | Deskripsi | Relevansi S2 |
|---|---|---|---|
| 🌟 **Inovasi Algoritma** | Layer 3 (oranye) + sebagian Layer 4 | Algoritma matematika & statistika yang menjadi kontribusi keilmuan tesis | **Core S2 thesis** |
| 🛠️ **Tools / Engineering** | Layer 1 (biru), Layer 2 (hijau), Shaper | Infrastruktur teknis untuk mengumpulkan/mengeksekusi data | S1-level |
| 📊 **Metodologi Evaluasi** | Supplementary, Locust, HttpArena | Instrumen pengujian hipotesis dan validasi statistik | Research Pipeline |
| ⚙️ **Konfigurasi** | config.py, modes.py, docker-compose | Parameter dan boilerplate deployment | Support |

---

## Cara Menggunakan untuk Defense

1. **Saat penguji bertanya "ini tools apa tesis?":**
   - Buka `00-concept/big_picture.md` → tunjukkan MAPE-K loop
   - Tunjuk kotak oranye (Layer 3) dan sebagian ungu (Layer 4 Micro-Freezing)
   - Katakan: "Inovasi tesis saya ada di sini"

2. **Saat penguji minta detail algoritma:**
   - Buka flowchart spesifik di `layer-3-control/` atau `layer-4-shaper/02_micro_freezer.md`
   - Setiap flowchart menunjukkan kode path asli dan penjelasan "Mengapa Ini Inovasi S2"

3. **Saat pembimbing minta pisah tools vs inovasi:**
   - Tabel di atas sudah memisahkan dengan jelas
   - File berlabel [Tools] vs [INOVASI] di struktur direktori
