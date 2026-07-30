# Flowchart — Profiler.discover_containers() (Layer 1)

> **Kode Sumber:** `framework/profiler.py` → class `EnvironmentProfiler`, fungsi `discover_containers()` (baris 91–170)
> **Posisi di Diagram:** Layer 1 — Environment Profiler → Container Discovery
> **Kategori:** 🛠️ TOOLS & INFRASTRUKTUR (S1)

Sistem pencarian target otomatis melalui socket Docker. Dilengkapi dengan deteksi keamanan (Safety Gate) yang mencegah modifikasi pada container infrastruktur dan database secara hardcoded untuk meminimalisasi risiko sistem crash.

```mermaid
flowchart TD
    START(["discover_containers()"])

    CONNECT["Connect ke Docker API (docker.from_env)"]
    CONN_ERR{"Koneksi gagal?"}
    RETURN_EMPTY(["Return []"])

    LOAD_CONFIG["Load TARGET_CONTAINERS & CONTAINER_PRIORITY"]

    LOOP(["Iterasi container dalam client.containers.list()"])

    CHECK_SELF{"container.name<br/>== HECF_CONTAINER_NAME?"}
    SKIP_SELF["Skip (Hindari self-throttling)"]

    CHECK_EXCLUDED{"container.name in<br/>EXCLUDED_CONTAINERS?"}
    SKIP_EXCLUDED["Skip (Infrastruktur kritis)"]

    CHECK_PORTS["Inspeksi container.ports"]
    PORT_DB{"Port DB terbuka?<br/>(3306, 5432, 6379, 27017)"}
    SKIP_DB["Skip (Mencegah korupsi DB)"]

    PORT_WEB{"Port Web terbuka?<br/>(80, 443, 8080)"}
    PRIO_WEB["Set weight = 2 (Medium Prio)"]

    CHECK_MANUAL_PRIO{"container.name in<br/>CONTAINER_PRIORITY?"}
    PRIO_MANUAL["Override weight dari config"]
    CHECK_LABEL{"Label 'hecf.priority' ada?"}
    PRIO_LABEL["Override weight dari label"]

    CHECK_NAME{"Regex match (nginx|traefik)?"}
    PRIO_PROXY["Set weight = 3 (High Prio)"]

    APPEND["Append ke container_targets"]
    NEXT["Lanjut ke container berikutnya"]

    WRITE_JSON["Tulis container_targets ke<br/>targets.json (untuk Dashboard)"]

    FILTER_TARGETS{"TARGET_CONTAINERS<br/>tidak kosong?"}
    DO_FILTER["Filter container_targets<br/>hanya yang ada di list"]
    KEEP_ALL["Keep semua container_targets"]

    RETURN(["Return container_targets"])

    START --> CONNECT
    CONNECT --> CONN_ERR
    CONN_ERR -->|Ya| RETURN_EMPTY
    CONN_ERR -->|Tidak| LOAD_CONFIG
    LOAD_CONFIG --> LOOP

    LOOP --> CHECK_SELF
    CHECK_SELF -->|Ya| SKIP_SELF
    CHECK_SELF -->|Tidak| CHECK_EXCLUDED
    SKIP_SELF --> NEXT

    CHECK_EXCLUDED -->|Ya| SKIP_EXCLUDED
    CHECK_EXCLUDED -->|Tidak| CHECK_PORTS
    SKIP_EXCLUDED --> NEXT

    CHECK_PORTS --> PORT_DB
    PORT_DB -->|Ya| SKIP_DB
    PORT_DB -->|Tidak| PORT_WEB
    SKIP_DB --> NEXT

    PORT_WEB -->|Ya| PRIO_WEB
    PORT_WEB -->|Tidak| CHECK_MANUAL_PRIO
    PRIO_WEB --> CHECK_MANUAL_PRIO

    CHECK_MANUAL_PRIO -->|Ya| PRIO_MANUAL
    CHECK_MANUAL_PRIO -->|Tidak| CHECK_LABEL
    PRIO_MANUAL --> CHECK_NAME
    CHECK_LABEL -->|Ya| PRIO_LABEL
    CHECK_LABEL -->|Tidak| CHECK_NAME
    PRIO_LABEL --> CHECK_NAME

    CHECK_NAME -->|Ya| PRIO_PROXY
    CHECK_NAME -->|Tidak| APPEND
    PRIO_PROXY --> APPEND
    APPEND --> NEXT

    NEXT -->|Masih ada| LOOP
    NEXT -->|Selesai| WRITE_JSON

    WRITE_JSON --> FILTER_TARGETS
    FILTER_TARGETS -->|Ya| DO_FILTER
    FILTER_TARGETS -->|Tidak| KEEP_ALL
    DO_FILTER --> RETURN
    KEEP_ALL --> RETURN
```

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["START: Service Discovery"])

    HUBUNGI["Fetch Docker API container_list"]
    GAGAL{"Apakah Terjadi<br/>API Error?"}
    KOSONG(["END: Abort, Return Empty List"])

    BACA_PENGATURAN["Load Config:<br/>Priority Map & Target List"]

    PERIKSA(["Iterasi Container Target"])

    DIRI_SENDIRI{"Apakah Self-Instance<br/>(HECF Engine)?"}
    LEWAT1["Bypass: Hindari Self-Control"]

    DILARANG{"Apakah Masuk<br/>Exclusion List?"}
    LEWAT2["Bypass: Infrastruktur Kritis"]

    CEK_PORT["Inspeksi Port Binding"]
    PORT_BAHAYA{"Apakah Expose DB Ports?<br/>(3306, 5432, dll)"}
    LEWAT3["Bypass: Hindari I/O Corrupt"]

    PORT_WEB{"Apakah Expose Web Ports?<br/>(80, 443, dll)"}
    PENTING_WEB["Set Prio: Web Service"]

    CEK_SETTING{"Apakah Ada<br/>Manual Priority?"}
    PAKAI_MANUAL["Apply Manual Weight"]
    CEK_LABEL{"Apakah Ada<br/>Label Priority?"}
    PAKAI_LABEL["Apply Label Weight"]

    CEK_NAMA{"Apakah Nama Cocok Regex Infra<br/>(nginx/traefik)?"}
    PENTING_INFRA["Set Prio: Network Infra"]

    MASUKKAN["Register ke Inventaris"]

    LANJUT["Next Container"]

    TULIS["Sync ke targets.json (Dashboard)"]

    CEK_WHITELIST{"Apakah Whitelist Mode<br/>Aktif?"}
    WHITELIST["Apply Whitelist Filter"]
    SEMUA["Promiscuous Mode (All)"]

    SELESAI(["END: Return Filtered Targets"])

    START --> HUBUNGI
    HUBUNGI --> GAGAL
    GAGAL -->|Ya| KOSONG
    GAGAL -->|Tidak| BACA_PENGATURAN
    BACA_PENGATURAN --> PERIKSA

    PERIKSA --> DIRI_SENDIRI
    DIRI_SENDIRI -->|Ya| LEWAT1
    DIRI_SENDIRI -->|Tidak| DILARANG
    LEWAT1 --> LANJUT

    DILARANG -->|Ya| LEWAT2
    DILARANG -->|Tidak| CEK_PORT
    LEWAT2 --> LANJUT

    CEK_PORT --> PORT_BAHAYA
    PORT_BAHAYA -->|Ya| LEWAT3
    PORT_BAHAYA -->|Tidak| PORT_WEB
    LEWAT3 --> LANJUT

    PORT_WEB -->|Ya| PENTING_WEB
    PORT_WEB -->|Tidak| CEK_SETTING
    PENTING_WEB --> CEK_SETTING

    CEK_SETTING -->|Ya| PAKAI_MANUAL
    CEK_SETTING -->|Tidak| CEK_LABEL
    PAKAI_MANUAL --> CEK_NAMA
    CEK_LABEL -->|Ya| PAKAI_LABEL
    CEK_LABEL -->|Tidak| CEK_NAMA
    PAKAI_LABEL --> CEK_NAMA

    CEK_NAMA -->|Ya| PENTING_INFRA
    CEK_NAMA -->|Tidak| MASUKKAN
    PENTING_INFRA --> MASUKKAN
    MASUKKAN --> LANJUT

    LANJUT -->|Iterating| PERIKSA
    LANJUT -->|Done| TULIS

    TULIS --> CEK_WHITELIST
    CEK_WHITELIST -->|Ya| WHITELIST
    CEK_WHITELIST -->|Tidak| SEMUA
    WHITELIST --> SELESAI
    SEMUA --> SELESAI
```
