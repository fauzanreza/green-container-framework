#!/usr/bin/env bash
# ==============================================================================
# HECF S2 Thesis — Stage B (24-Run PoC) & Stage B+ (72-Run Main) RCBD Runner
# ==============================================================================
# Desain Eksperimen:
#   - 4 Mode: default_docker, static_cap, reactive_only, full_hecf
#   - 6 Blok x 4 Mode = 24 Run (Stage B PoC, 6.4 jam) atau x 3 Replikasi = 72 Run (Stage B+ Main, 19.2 jam)
#   - Durasi per run: 16 menit (4 fase beban @ 4 menit: Idle, Steady, Microburst, Overload)
#   - Struktur direktori hierarkis rapi di experiment_results/session_<STAGE>_<TIMESTAMP>/
#   - Otomatis men-generate Jupyter Notebook (analysis_summary.ipynb) + Laporan Gate 2 (statistical_report.md)
# ==============================================================================

set -euo pipefail

# Parameter Konfigurasi Eksperimen (Bisa dioverride lewat environment variable):
#   REPLICATIONS  : 1 untuk Tahap B (24 run = 6,4 jam), 3 untuk Tahap B+ (72 run = 19,2 jam)
#   PHASE_DURATION: 4m default (4m x 4 fase = 16 menit/run), atau 15s untuk smoke test
REPLICATIONS="${REPLICATIONS:-1}"
PHASE_DUR="${PHASE_DURATION:-4m}"
TOTAL_RUNS=$((6 * 4 * REPLICATIONS))

if [ "$PHASE_DUR" = "15s" ] || [ "$PHASE_DUR" = "10s" ] || [ "$PHASE_DUR" = "30s" ]; then
    STAGE_TAG="smoke_test_${TOTAL_RUNS}runs"
elif [ "$REPLICATIONS" -ge 3 ]; then
    STAGE_TAG="stage_B_plus_72runs"
else
    STAGE_TAG="stage_B_poc_24runs"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GCF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$GCF_DIR"

SESSION_TS="$(date +%Y%m%d_%H%M%S)"
RESULTS_DIR="$GCF_DIR/experiment_results/session_${STAGE_TAG}_${SESSION_TS}"
mkdir -p "$RESULTS_DIR"
SUMMARY_CSV="$RESULTS_DIR/summary_all_runs.csv"

echo "rep,block,run_idx,mode,rapl_start_uj,rapl_end_uj,rapl_pkg_kwh,target_kwh,mean_rt_ms,p95_rt_ms,max_rt_ms,rps,fail_count,overhead_cpu_pct,freeze_sec,nr_throttled_delta,guardrail_triggers,tier1_triggers,microfreeze_triggers" > "$SUMMARY_CSV"

MODES=("default_docker" "static_cap" "reactive_only" "full_hecf")
TARGET="bench-json"

# Deteksi otomatis apakah docker-compose utama ada di ../portfolio-app
if [ -f "$GCF_DIR/../portfolio-app/docker-compose.yml" ]; then
    COMPOSE_FILE="$GCF_DIR/../portfolio-app/docker-compose.yml"
    echo "[INFO] Menggunakan docker-compose utama: $COMPOSE_FILE (network: portfolio-network)"
else
    COMPOSE_FILE="$GCF_DIR/docker-compose.yml"
    echo "[INFO] Menggunakan docker-compose lokal: $COMPOSE_FILE"
fi
echo "[INFO] Direktori Sesi Eksperimen : $RESULTS_DIR"

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
        docker exec hecf sh -c "echo 'max 100000' > $cg/cpu.max" 2>/dev/null || true
        docker exec hecf sh -c "echo '0' > $cg/cgroup.freeze" 2>/dev/null || true
    fi
}

write_csv_header() {
    echo "time,container_name,cpu_percent,mem_percent,tier,action,power_watt,energy_kwh,ema_pred,alpha,spike_ratio,p50,p95,overhead_cpu,overhead_mem,freeze_seconds" > "$GCF_DIR/metrics.csv"
}

echo '["bench-json"]' > "$GCF_DIR/targets.json"
docker compose -f "$COMPOSE_FILE" up -d hecf bench-json >/dev/null 2>&1 || true

run_counter=0
for rep in $(seq 1 "$REPLICATIONS"); do
for block in $(seq 1 6); do
    SEED=$((rep * 100 + block * 42))
    SHUFFLED_MODES=($(python3 -c "import random; m=['default_docker','static_cap','reactive_only','full_hecf']; random.seed($SEED); random.shuffle(m); print(' '.join(m))"))
    
    echo "============================================================"
    echo "REPLIKASI $rep/$REPLICATIONS — BLOK $block/6 — Urutan: ${SHUFFLED_MODES[*]}"
    echo "============================================================"

    for mode in "${SHUFFLED_MODES[@]}"; do
        run_counter=$((run_counter + 1))
        RUN_ID="rep${rep}_b${block}_r${run_counter}_${mode}"
        
        # Buat hierarki folder terstruktur per kondisi/workload/block/rep:
        # experiment_results/session_.../<mode>/json/block_<N>/rep_<M>/
        RUN_DIR="$RESULTS_DIR/$mode/json/block_${block}/rep_${rep}"
        mkdir -p "$RUN_DIR"

        echo "[$(date +%H:%M:%S)] >>> Run $run_counter/$TOTAL_RUNS: Mode=$mode (Rep $rep, Blok $block)"

        # 1. Reset state & Manipulation Check
        reset_target_cgroup
        echo '["bench-json"]' > "$GCF_DIR/targets.json"
        # Tulis ulang header metrics.csv secara in-place agar csv.DictReader selalu punya nama kolom!
        write_csv_header
        rm -f "$GCF_DIR"/locustfiles/results_*.csv "$GCF_DIR"/locustfiles/tmp_run_*.csv
        
        # Set mode & recreate HECF
        export HECF_MODE="$mode"
        if ! HECF_MODE="$mode" docker compose -f "$COMPOSE_FILE" up -d --no-deps --force-recreate hecf >/dev/null 2>&1; then
            docker rm -f hecf >/dev/null 2>&1 || true
            HECF_MODE="$mode" docker compose -f "$COMPOSE_FILE" up -d --no-deps hecf
        fi
        sleep 5

        # Manipulation check: pastikan bench-json merespons HTTP 200
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ || echo "000")
        if [ "$HTTP_CODE" != "200" ]; then
            echo "[WARN] Manipulation check HTTP $HTTP_CODE — menyalakan ulang bench-json..."
            docker rm -f "$TARGET" >/dev/null 2>&1 || true
            docker compose -f "$COMPOSE_FILE" up -d --no-deps "$TARGET"
            sleep 5
        fi

        # Simpan info metadata run
        cat <<EOF > "$RUN_DIR/run_metadata.txt"
Run ID       : $RUN_ID
Run Index    : $run_counter / $TOTAL_RUNS
Mode         : $mode
Workload     : json (bench-json)
Block        : $block / 6
Replication  : $rep / $REPLICATIONS
Phase Dur    : $PHASE_DUR (4 phases: Idle, Steady, Microburst, Overload)
Started At   : $(date "+%Y-%m-%d %H:%M:%S")
EOF

        START_UJ=$(read_rapl)
        START_THROTTLE=$(read_nr_throttled)

        # 2. Jalankan 4 Fase Beban
        # Fase 1: Idle - tanpa Locust agar Micro-Freeze terpicu di full_hecf
        echo "  - Fase 1/4: Idle ($PHASE_DUR)..."
        sleep "$PHASE_DUR"
        cp -f "$GCF_DIR/metrics.csv" "$RUN_DIR/phase1_idle_server_metrics.csv" 2>/dev/null || true

        # Fase 2: Steady 25-35% host CPU -> 30 users
        echo "  - Fase 2/4: Steady Load ($PHASE_DUR)..."
        docker compose -f "$COMPOSE_FILE" run --rm --no-deps -T -e WORKLOAD_TYPE=json locust-master \
            -f /mnt/locust/locustfile.py --host http://bench-json:8000 \
            --headless -u 30 -r 5 -t "$PHASE_DUR" \
            --csv="/mnt/locust/tmp_run_steady" > "$RUN_DIR/phase2_steady_locust.log" 2>&1 || true
        for sfx in stats.csv stats_history.csv failures.csv exceptions.csv; do
            mv -f "$GCF_DIR/locustfiles/tmp_run_steady_${sfx}" "$RUN_DIR/phase2_steady_locust_${sfx}" 2>/dev/null || true
        done
        cp -f "$GCF_DIR/metrics.csv" "$RUN_DIR/phase2_steady_server_metrics.csv" 2>/dev/null || true

        # Fase 3: Microburst 25-72% host CPU -> 100 users
        echo "  - Fase 3/4: Microburst Load ($PHASE_DUR)..."
        docker compose -f "$COMPOSE_FILE" run --rm --no-deps -T -e WORKLOAD_TYPE=json locust-master \
            -f /mnt/locust/locustfile.py --host http://bench-json:8000 \
            --headless -u 100 -r 25 -t "$PHASE_DUR" \
            --csv="/mnt/locust/tmp_run_burst" > "$RUN_DIR/phase3_burst_locust.log" 2>&1 || true
        for sfx in stats.csv stats_history.csv failures.csv exceptions.csv; do
            mv -f "$GCF_DIR/locustfiles/tmp_run_burst_${sfx}" "$RUN_DIR/phase3_burst_locust_${sfx}" 2>/dev/null || true
        done
        cp -f "$GCF_DIR/metrics.csv" "$RUN_DIR/phase3_burst_server_metrics.csv" 2>/dev/null || true

        # Fase 4: Overload 85-95% host CPU -> 220 users
        echo "  - Fase 4/4: Overload ($PHASE_DUR)..."
        docker compose -f "$COMPOSE_FILE" run --rm --no-deps -T -e WORKLOAD_TYPE=json locust-master \
            -f /mnt/locust/locustfile.py --host http://bench-json:8000 \
            --headless -u 220 -r 40 -t "$PHASE_DUR" \
            --csv="/mnt/locust/tmp_run_overload" > "$RUN_DIR/phase4_overload_locust.log" 2>&1 || true
        for sfx in stats.csv stats_history.csv failures.csv exceptions.csv; do
            mv -f "$GCF_DIR/locustfiles/tmp_run_overload_${sfx}" "$RUN_DIR/phase4_overload_locust_${sfx}" 2>/dev/null || true
        done

        END_UJ=$(read_rapl)
        END_THROTTLE=$(read_nr_throttled)

        # 3. Simpan artefak lengkap server_metrics.csv di folder run tersebut
        cp -f "$GCF_DIR/metrics.csv" "$RUN_DIR/${RUN_ID}_server_metrics.csv" 2>/dev/null || true
        cp -f "$RUN_DIR/phase4_overload_locust_stats.csv" "$RUN_DIR/${RUN_ID}_locust_stats.csv" 2>/dev/null || true
        echo "Finished At  : $(date "+%Y-%m-%d %H:%M:%S")" >> "$RUN_DIR/run_metadata.txt"

        # 4. Ekstrak ringkasan metrik dengan Python 100% stdlib
        ROW=$(python3 - "$rep" "$block" "$run_counter" "$mode" "$START_UJ" "$END_UJ" "$START_THROTTLE" "$END_THROTTLE" "$RUN_DIR/${RUN_ID}_server_metrics.csv" "$RUN_DIR/phase4_overload_locust_stats.csv" << 'PYEOF'
import sys, csv, os

rep, block, run_idx, mode, s_uj, e_uj, s_th, e_th, m_csv, l_csv = sys.argv[1:]
s_uj, e_uj = int(s_uj), int(e_uj)
delta_uj = e_uj - s_uj
if delta_uj < 0:
    delta_uj += 262143328850
rapl_pkg_kwh = (delta_uj / 1_000_000.0) / 3_600_000.0
th_delta = max(0, int(e_th) - int(s_th))

oh_list, freeze_max, kwh_sum = [], 0.0, 0.0
gr_count, t1_count, mf_count = 0, 0, 0
if os.path.exists(m_csv):
    with open(m_csv) as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                if row.get("time") == "time":
                    continue
                oh_list.append(float(row.get("overhead_cpu", 0)))
                freeze_max = max(freeze_max, float(row.get("freeze_seconds", 0)))
                kwh_sum += float(row.get("energy_kwh", 0))
                act = (row.get("action") or "").strip()
                tier = (row.get("tier") or "").strip()
                if act == "GUARDRAIL":
                    gr_count += 1
                if tier == "AGGRESSIVE" or act == "AGGRESSIVE":
                    t1_count += 1
                if act == "MICRO_FREEZE":
                    mf_count += 1
            except Exception:
                pass

target_kwh = kwh_sum if kwh_sum > 0 else rapl_pkg_kwh
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

print(f"{rep},{block},{run_idx},{mode},{s_uj},{e_uj},{rapl_pkg_kwh:.9f},{target_kwh:.9f},{mean_rt:.2f},{p95_rt:.2f},{max_rt:.2f},{rps:.2f},{fails},{oh_mean:.2f},{freeze_max:.3f},{th_delta},{gr_count},{t1_count},{mf_count}")
PYEOF
)
        echo "$ROW" >> "$SUMMARY_CSV"
        echo "  -> Selesai: $ROW"
        echo "  -> Tersimpan di: $RUN_DIR"
        sleep 10
    done
done
done

echo "============================================================"
echo "EKSPERIMEN $TOTAL_RUNS RUN SELESAI."
echo "Menghasilkan Laporan Statistik, Gate 2 Checklist, & Jupyter Notebook (.ipynb)..."
echo "============================================================"
python3 scripts/analyze_24runs.py "$SUMMARY_CSV"
