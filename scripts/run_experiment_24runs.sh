#!/usr/bin/env bash
# ==============================================================================
# HECF S2 Thesis — 24-Run Randomized Block Experiment Runner (FASE 6)
# ==============================================================================
# Desain Eksperimen:
#   - 4 Mode: default_docker, static_cap, reactive_only, full_hecf
#   - 6 Blok x 4 Mode = 24 Run (urutan diacak per blok)
#   - Durasi per run: 16 menit (4 fase beban @ 4 menit: Idle, Steady, Microburst, Overload)
#   - Manipulation check sebelum setiap run (memastikan bench-json responsif & cgroup reset)
#   - Pengukuran RAPL langsung (energy_uj awal & akhir tiap fase dan tiap run)
# ==============================================================================

set -euo pipefail

RESULTS_DIR="experiment_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"
SUMMARY_CSV="$RESULTS_DIR/summary_24runs.csv"

echo "block,run_idx,mode,rapl_start_uj,rapl_end_uj,rapl_kwh,mean_rt_ms,p95_rt_ms,max_rt_ms,rps,fail_count,overhead_cpu_pct,freeze_sec,nr_throttled_delta" > "$SUMMARY_CSV"

# Parameter Konfigurasi Eksperimen (Bisa dioverride lewat environment variable):
#   REPLICATIONS : 1 untuk Tahap B (24 run = 6,4 jam), 3 untuk Tahap B+ (72 run = 19,2 jam)
#   PHASE_DURATION: 4m default (4m x 4 fase = 16 menit/run), atau 15s untuk smoke test
REPLICATIONS="${REPLICATIONS:-1}"
PHASE_DUR="${PHASE_DURATION:-4m}"
TOTAL_RUNS=$((6 * 4 * REPLICATIONS))

MODES=("default_docker" "static_cap" "reactive_only" "full_hecf")
TARGET="bench-json"

# Deteksi otomatis apakah docker-compose utama ada di ../portfolio-app
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GCF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ -f "$GCF_DIR/../portfolio-app/docker-compose.yml" ]; then
    COMPOSE_FILE="$GCF_DIR/../portfolio-app/docker-compose.yml"
    echo "[INFO] Menggunakan docker-compose utama: $COMPOSE_FILE (network: portfolio-network)"
else
    COMPOSE_FILE="$GCF_DIR/docker-compose.yml"
    echo "[INFO] Menggunakan docker-compose lokal: $COMPOSE_FILE"
fi

cd "$GCF_DIR"

# Deteksi path RAPL (baca via docker exec hecf karena container hecf privileged dan tidak butuh prompt sudo)
read_rapl() {
    docker exec hecf cat /sys/class/powercap/intel-rapl:0/energy_uj 2>/dev/null \
        || docker exec hecf cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj 2>/dev/null \
        || cat /sys/class/powercap/intel-rapl:0/energy_uj 2>/dev/null \
        || echo "0"
}

read_nr_throttled() {
    local cid
    cid=$(docker inspect -f '{{.Id}}' "$TARGET" 2>/dev/null || echo "")
    if [ -z "$cid" ]; then
        echo "0"
        return
    fi
    local cg="/sys/fs/cgroup/system.slice/docker-${cid}.scope/cpu.stat"
    if [ -f "$cg" ]; then
        awk '/nr_throttled/ {print $2}' "$cg"
    else
        echo "0"
    fi
}

reset_target_cgroup() {
    local cid
    cid=$(docker inspect -f '{{.Id}}' "$TARGET" 2>/dev/null || echo "")
    if [ -n "$cid" ]; then
        local cg="/sys/fs/cgroup/system.slice/docker-${cid}.scope"
        # Gunakan container hecf (privileged) untuk menulis ke cgroupfs tanpa butuh sudo di host
        docker exec hecf sh -c "echo 'max 100000' > $cg/cpu.max" 2>/dev/null || true
        docker exec hecf sh -c "echo '0' > $cg/cgroup.freeze" 2>/dev/null || true
    fi
}

echo '["bench-json"]' > "$GCF_DIR/targets.json"

# Pastikan container bench-json dan hecf berjalan dari COMPOSE_FILE utama (portfolio-app)
docker compose -f "$COMPOSE_FILE" up -d hecf bench-json >/dev/null 2>&1 || true

run_counter=0
for rep in $(seq 1 "$REPLICATIONS"); do
for block in $(seq 1 6); do
    # Acak urutan 4 mode dalam blok ini menggunakan python3 stdlib
    SEED=$((rep * 100 + block * 42))
    SHUFFLED_MODES=($(python3 -c "import random; m=['default_docker','static_cap','reactive_only','full_hecf']; random.seed($SEED); random.shuffle(m); print(' '.join(m))"))
    
    echo "============================================================"
    echo "REPLIKASI $rep/$REPLICATIONS — BLOK $block/6 — Urutan: ${SHUFFLED_MODES[*]}"
    echo "============================================================"

    for mode in "${SHUFFLED_MODES[@]}"; do
        run_counter=$((run_counter + 1))
        RUN_ID="rep${rep}_b${block}_r${run_counter}_${mode}"
        echo "[$(date +%H:%M:%S)] >>> Run $run_counter/$TOTAL_RUNS: Mode=$mode (Rep $rep, Blok $block)"

        # 1. Reset state & Manipulation Check
        reset_target_cgroup
        echo '["bench-json"]' > "$GCF_DIR/targets.json"
        # Kosongkan file metrics.csv secara in-place (JANGAN rm -f karena sedang di-bind-mount!)
        : > "$GCF_DIR/metrics.csv"
        rm -f "$GCF_DIR"/locustfiles/results_*.csv
        
        # Set mode & recreate HECF menggunakan COMPOSE_FILE utama (portfolio-app) tanpa menyentuh container lain
        export HECF_MODE="$mode"
        if ! HECF_MODE="$mode" docker compose -f "$COMPOSE_FILE" up -d --no-deps --force-recreate hecf >/dev/null 2>&1; then
            echo "[WARN] Force-recreate hecf butuh hapus container lama..."
            docker rm -f hecf >/dev/null 2>&1 || true
            HECF_MODE="$mode" docker compose -f "$COMPOSE_FILE" up -d --no-deps hecf
        fi
        sleep 5

        # Manipulation check: pastikan bench-json berjalan di network yang sama dan merespons HTTP 200
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ || echo "000")
        if [ "$HTTP_CODE" != "200" ]; then
            echo "[WARN] Manipulation check HTTP $HTTP_CODE — menyalakan ulang bench-json di $COMPOSE_FILE..."
            docker rm -f "$TARGET" >/dev/null 2>&1 || true
            docker compose -f "$COMPOSE_FILE" up -d --no-deps "$TARGET"
            sleep 5
        fi

        START_UJ=$(read_rapl)
        START_THROTTLE=$(read_nr_throttled)

        # 2. Jalankan 4 Fase Beban (Total 16 menit = 4 x 4m; dapat dioverride dengan PHASE_DURATION, misal 4m)
        PHASE_DUR="${PHASE_DURATION:-4m}"

        # Fase 1: Idle (4 menit) - tanpa Locust agar Micro-Freeze bisa terpicu di full_hecf
        echo "  - Fase 1/4: Idle ($PHASE_DUR)..."
        sleep "$PHASE_DUR"

        # Fase 2: Steady 25-35% host CPU (4 menit) -> ~30 users
        echo "  - Fase 2/4: Steady Load ($PHASE_DUR)..."
        docker compose -f "$COMPOSE_FILE" run --rm --no-deps -T -e WORKLOAD_TYPE=json locust-master \
            -f /mnt/locust/locustfile.py --host http://bench-json:8000 \
            --headless -u 30 -r 5 -t "$PHASE_DUR" --csv="/mnt/locust/${RUN_ID}_steady" >/dev/null 2>&1 || true

        # Fase 3: Microburst 25-72% host CPU (4 menit) -> ~100 users
        echo "  - Fase 3/4: Microburst Load ($PHASE_DUR)..."
        docker compose -f "$COMPOSE_FILE" run --rm --no-deps -T -e WORKLOAD_TYPE=json locust-master \
            -f /mnt/locust/locustfile.py --host http://bench-json:8000 \
            --headless -u 100 -r 25 -t "$PHASE_DUR" --csv="/mnt/locust/${RUN_ID}_burst" >/dev/null 2>&1 || true

        # Fase 4: Overload 85-95% host CPU (4 menit) -> ~220 users
        echo "  - Fase 4/4: Overload ($PHASE_DUR)..."
        docker compose -f "$COMPOSE_FILE" run --rm --no-deps -T -e WORKLOAD_TYPE=json locust-master \
            -f /mnt/locust/locustfile.py --host http://bench-json:8000 \
            --headless -u 220 -r 40 -t "$PHASE_DUR" --csv="/mnt/locust/${RUN_ID}_overload" >/dev/null 2>&1 || true

        END_UJ=$(read_rapl)
        END_THROTTLE=$(read_nr_throttled)

        # 3. Simpan artefak CSV per run
        cp -f metrics.csv "$RESULTS_DIR/metrics_${RUN_ID}.csv" 2>/dev/null || true
        cp -f locustfiles/${RUN_ID}_overload_stats.csv "$RESULTS_DIR/" 2>/dev/null || true

        # 4. Ekstrak ringkasan metrik dengan Python 100% stdlib (tanpa dependency eksternal di host)
        ROW=$(python3 - "$block" "$run_counter" "$mode" "$START_UJ" "$END_UJ" "$START_THROTTLE" "$END_THROTTLE" "$RESULTS_DIR/metrics_${RUN_ID}.csv" "locustfiles/${RUN_ID}_overload_stats.csv" << 'PYEOF'
import sys, csv, os

block, run_idx, mode, s_uj, e_uj, s_th, e_th, m_csv, l_csv = sys.argv[1:]
s_uj, e_uj = int(s_uj), int(e_uj)
delta_uj = e_uj - s_uj
if delta_uj < 0:
    # Handle RAPL wrap-around (~262 GJ default max range)
    delta_uj += 262143328850
rapl_kwh = (delta_uj / 1_000_000.0) / 3_600_000.0
th_delta = max(0, int(e_th) - int(s_th))

oh_list, freeze_max, kwh_sum = [], 0.0, 0.0
if os.path.exists(m_csv):
    with open(m_csv) as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                oh_list.append(float(row.get("overhead_cpu", 0)))
                freeze_max = max(freeze_max, float(row.get("freeze_seconds", 0)))
                kwh_sum += float(row.get("energy_kwh", 0))
            except Exception:
                pass

if rapl_kwh <= 0:
    rapl_kwh = kwh_sum

oh_mean = (sum(oh_list) / len(oh_list)) if oh_list else 0.0

mean_rt, p95_rt, max_rt, rps, fails = 0.0, 0.0, 0.0, 0.0, 0
if os.path.exists(l_csv):
    with open(l_csv) as f:
        r = csv.DictReader(f)
        for row in r:
            if row.get("Name") == "Aggregated" or row.get("Type") == "Aggregated":
                mean_rt = float(row.get("Average Response Time", 0) or 0)
                p95_rt = float(row.get("95%", 0) or 0)
                max_rt = float(row.get("Max Response Time", 0) or 0)
                rps = float(row.get("Requests/s", 0) or 0)
                fails = int(row.get("Failure Count", 0) or 0)

print(f"{block},{run_idx},{mode},{s_uj},{e_uj},{rapl_kwh:.9f},{mean_rt:.2f},{p95_rt:.2f},{max_rt:.2f},{rps:.2f},{fails},{oh_mean:.2f},{freeze_max:.3f},{th_delta}")
PYEOF
)
        echo "$ROW" >> "$SUMMARY_CSV"
        echo "  -> Selesai: $ROW"
        sleep 10
    done
done
done

echo "============================================================"
echo "EKSPERIMEN $TOTAL_RUNS RUN SELESAI. Menjalankan evaluasi statistik..."
echo "============================================================"
python3 scripts/analyze_24runs.py "$SUMMARY_CSV"
