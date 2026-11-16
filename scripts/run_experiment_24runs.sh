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

MODES=("default_docker" "static_cap" "reactive_only" "full_hecf")
TARGET="bench-json"

# Deteksi path RAPL
RAPL_PATH=""
for p in /sys/class/powercap/intel-rapl:0/energy_uj /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj; do
    if [ -r "$p" ]; then
        RAPL_PATH="$p"
        break
    fi
done

if [ -z "$RAPL_PATH" ]; then
    echo "[WARN] RAPL tidak terbaca tanpa sudo. Mencoba dengan sudo..."
    RAPL_CMD="sudo cat /sys/class/powercap/intel-rapl:0/energy_uj"
else
    RAPL_CMD="cat $RAPL_PATH"
fi

read_rapl() {
    eval "$RAPL_CMD" 2>/dev/null || echo "0"
}

read_nr_throttled() {
    local cid
    cid=$(docker inspect -f '{{.Id}}' "$TARGET")
    local cg="/sys/fs/cgroup/system.slice/docker-${cid}.scope/cpu.stat"
    if [ -f "$cg" ]; then
        awk '/nr_throttled/ {print $2}' "$cg"
    else
        echo "0"
    fi
}

reset_target_cgroup() {
    local cid
    cid=$(docker inspect -f '{{.Id}}' "$TARGET")
    local cg="/sys/fs/cgroup/system.slice/docker-${cid}.scope"
    if [ -d "$cg" ]; then
        sudo sh -c "echo 'max 100000' > $cg/cpu.max" 2>/dev/null || true
        sudo sh -c "echo '0' > $cg/cgroup.freeze" 2>/dev/null || true
    fi
}

echo '["bench-json"]' > targets.json

run_counter=0
for block in $(seq 1 6); do
    # Acak urutan 4 mode dalam blok ini menggunakan python3 stdlib
    SHUFFLED_MODES=($(python3 -c "import random; m=['default_docker','static_cap','reactive_only','full_hecf']; random.seed($block * 42); random.shuffle(m); print(' '.join(m))"))
    
    echo "============================================================"
    echo "MEMULAI BLOK $block / 6 — Urutan: ${SHUFFLED_MODES[*]}"
    echo "============================================================"

    for mode in "${SHUFFLED_MODES[@]}"; do
        run_counter=$((run_counter + 1))
        RUN_ID="b${block}_r${run_counter}_${mode}"
        echo "[$(date +%H:%M:%S)] >>> Run $run_counter/24: Mode=$mode (Blok $block)"

        # 1. Reset state & Manipulation Check
        reset_target_cgroup
        rm -f metrics.csv locustfiles/results_*.csv
        
        # Set mode & restart HECF
        export HECF_MODE="$mode"
        docker compose up -d --force-recreate hecf >/dev/null 2>&1
        sleep 5

        # Manipulation check: pastikan endpoint HTTP 200
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ || echo "000")
        if [ "$HTTP_CODE" != "200" ]; then
            echo "[ERROR] Manipulation check gagal! bench-json mengembalikan HTTP $HTTP_CODE"
            docker restart "$TARGET"
            sleep 5
        fi

        START_UJ=$(read_rapl)
        START_THROTTLE=$(read_nr_throttled)

        # 2. Jalankan 4 Fase Beban (Total 16 menit = 4 x 4m; dapat dioverride dengan PHASE_DURATION, misal 4m)
        PHASE_DUR="${PHASE_DURATION:-4m}"

        # Fase 1: Idle (4 menit) - tanpa Locust ताकि Micro-Freeze bisa terpicu di full_hecf
        echo "  - Fase 1/4: Idle ($PHASE_DUR)..."
        sleep "$PHASE_DUR"

        # Fase 2: Steady 25-35% host CPU (4 menit) -> ~30 users
        echo "  - Fase 2/4: Steady Load ($PHASE_DUR)..."
        docker compose run --rm -T locust-master \
            -f /mnt/locust/locustfile.py --host http://bench-json:8000 \
            --headless -u 30 -r 5 -t "$PHASE_DUR" --csv="/mnt/locust/${RUN_ID}_steady" >/dev/null 2>&1 || true

        # Fase 3: Microburst 25-72% host CPU (4 menit) -> ~100 users
        echo "  - Fase 3/4: Microburst Load ($PHASE_DUR)..."
        docker compose run --rm -T locust-master \
            -f /mnt/locust/locustfile.py --host http://bench-json:8000 \
            --headless -u 100 -r 25 -t "$PHASE_DUR" --csv="/mnt/locust/${RUN_ID}_burst" >/dev/null 2>&1 || true

        # Fase 4: Overload 85-95% host CPU (4 menit) -> ~220 users
        echo "  - Fase 4/4: Overload ($PHASE_DUR)..."
        docker compose run --rm -T locust-master \
            -f /mnt/locust/locustfile.py --host http://bench-json:8000 \
            --headless -u 220 -r 40 -t "$PHASE_DUR" --csv="/mnt/locust/${RUN_ID}_overload" >/dev/null 2>&1 || true

        END_UJ=$(read_rapl)
        END_THROTTLE=$(read_nr_throttled)

        # 3. Simpan artefak CSV per run
        cp -f metrics.csv "$RESULTS_DIR/metrics_${RUN_ID}.csv" 2>/dev/null || true
        cp -f locustfiles/${RUN_ID}_overload_stats.csv "$RESULTS_DIR/" 2>/dev/null || true

        # 4. Ekstrak ringkasan metrik dengan Python (stdlib + numpy saja)
        ROW=$(python3 - "$block" "$run_counter" "$mode" "$START_UJ" "$END_UJ" "$START_THROTTLE" "$END_THROTTLE" "$RESULTS_DIR/metrics_${RUN_ID}.csv" "locustfiles/${RUN_ID}_overload_stats.csv" << 'PYEOF'
import sys, csv, os
import numpy as np

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

oh_mean = float(np.mean(oh_list)) if oh_list else 0.0

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

echo "============================================================"
echo "EKSPERIMEN 24 RUN SELESAI. Menjalankan evaluasi statistik..."
echo "============================================================"
python3 scripts/analyze_24runs.py "$SUMMARY_CSV"
