import os
import csv
import json
import platform
from flask import Flask, render_template_string, jsonify, request, send_file

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HECF | Enterprise Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --primary: #1a56db;
            --primary-light: #ebf0ff;
            --accent: #0d9488;
            --accent-light: #e6fffa;
            --warning: #d97706;
            --warning-light: #fef3c7;
            --danger: #dc2626;
            --danger-light: #fee2e2;
            --purple: #7c3aed;
            --purple-light: #f5f3ff;
            --bg: #f1f5f9;
            --surface: #ffffff;
            --border: #e2e8f0;
            --text: #0f172a;
            --text-muted: #64748b;
            --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.05);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -1px rgba(0,0,0,0.05);
        }
        *, *::before, *::after { box-sizing: border-box; }
        body {
            background: var(--bg);
            color: var(--text);
            font-family: 'Inter', sans-serif;
            font-size: 14px;
            min-height: 100vh;
        }
        /* ---- NAVBAR ---- */
        .topbar {
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 0 24px;
            height: 56px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: var(--shadow);
        }
        .brand { font-weight: 700; font-size: 1.1rem; color: var(--primary); letter-spacing: -0.3px; }
        .brand span { color: var(--text); }
        .host-chips { display: flex; gap: 8px; align-items: center; }
        .chip {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 3px 10px;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
        }
        .btn-export {
            background: var(--primary-light);
            color: var(--primary);
            border: 1px solid #c7d7fb;
            border-radius: 8px;
            padding: 5px 14px;
            font-size: 12px;
            font-weight: 600;
            text-decoration: none;
            transition: all .15s;
        }
        .btn-export:hover { background: var(--primary); color: #fff; }
        .status-badge {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 600;
            color: var(--accent);
        }
        .status-dot {
            width: 8px; height: 8px;
            border-radius: 50%;
            background: var(--accent);
            animation: pulse-dot 2s infinite;
        }
        @keyframes pulse-dot {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        .status-dot.inactive { background: #94a3b8; animation: none; }
        /* ---- TOGGLE ---- */
        .switch { position: relative; display: inline-block; width: 42px; height: 24px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider {
            position: absolute; cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background: #cbd5e1; border-radius: 24px; transition: .3s;
        }
        .slider:before {
            position: absolute; content: "";
            height: 18px; width: 18px;
            left: 3px; bottom: 3px;
            background: white; border-radius: 50%; transition: .3s;
        }
        input:checked + .slider { background: var(--accent); }
        input:checked + .slider:before { transform: translateX(18px); }
        /* ---- LAYOUT ---- */
        .page { padding: 24px; max-width: 1400px; margin: 0 auto; }
        /* ---- METRIC CARDS ---- */
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }
        .metric-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            box-shadow: var(--shadow);
        }
        .metric-card .label {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-muted);
            margin-bottom: 8px;
        }
        .metric-card .value {
            font-size: 1.8rem;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 4px;
        }
        .metric-card .sub { font-size: 11px; color: var(--text-muted); }
        .metric-card .badge-layer {
            float: right;
            background: var(--primary-light);
            color: var(--primary);
            border-radius: 6px;
            padding: 2px 7px;
            font-size: 10px;
            font-weight: 600;
        }
        .v-cpu { color: var(--primary); }
        .v-ram { color: var(--purple); }
        .v-energy { color: var(--warning); }
        .v-latency { color: var(--accent); }
        .v-overhead { color: var(--danger); }
        /* ---- PANELS ---- */
        .panel {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            box-shadow: var(--shadow);
        }
        .panel-header {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .panel-header h6 {
            margin: 0;
            font-weight: 600;
            font-size: 14px;
            color: var(--text);
        }
        .panel-body { padding: 20px; }
        .panel-tag {
            background: var(--accent-light);
            color: var(--accent);
            border-radius: 6px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 600;
        }
        /* ---- INSIGHTS ---- */
        .insight-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }
        .insight-label { font-size: 12px; color: var(--text-muted); }
        .insight-val { font-size: 13px; font-weight: 700; }
        .progress-thin {
            height: 5px;
            background: var(--border);
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 16px;
        }
        .progress-fill { height: 100%; border-radius: 4px; transition: width .4s; }
        .status-box {
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-radius: 10px;
            padding: 14px;
            display: flex;
            align-items: center;
            gap: 12px;
            margin-top: auto;
        }
        .status-box .icon { font-size: 1.6rem; }
        .status-box .title { font-weight: 600; font-size: 13px; color: #15803d; }
        .status-box .desc { font-size: 11px; color: #4ade80; }
        /* ---- TABLE ---- */
        .table { font-size: 13px; }
        .table th {
            background: #f8fafc;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border);
            padding: 10px 14px;
        }
        .table td { padding: 10px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
        .table tr:last-child td { border-bottom: none; }
        .table tr:hover td { background: #f8fafc; }
        .badge-tier {
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: 700;
        }
        .tier-agg { background: #fee2e2; color: #dc2626; }
        .tier-bal { background: #fef3c7; color: #d97706; }
        .tier-soft { background: #dcfce7; color: #16a34a; }
        .tier-na { background: #f1f5f9; color: #94a3b8; }
        .badge-action {
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: 600;
        }
        .act-guardrail { background: #fee2e2; color: #dc2626; }
        .act-agg { background: #fef9c3; color: #92400e; }
        .act-bal { background: #dbeafe; color: #1d4ed8; }
        .act-soft { background: #dcfce7; color: #15803d; }
        .act-other { background: #f1f5f9; color: #64748b; }
        /* ---- CHART ---- */
        #resourceChart { max-height: 300px; }
    </style>
</head>
<body>

<nav class="topbar">
    <div class="d-flex align-items-center gap-3">
        <div class="brand">🌿 HECF <span>Enterprise</span></div>
        <div class="host-chips">
            <span class="chip" id="host-name">…</span>
            <span class="chip" id="host-cpu">… vCPU</span>
            <span class="chip" id="host-ram">… GB RAM</span>
        </div>
    </div>
    <div class="d-flex align-items-center gap-3">
        <a href="/api/download-csv" class="btn-export" target="_blank">⬇ Export CSV</a>
        <div class="status-badge">
            <div class="status-dot" id="status-dot"></div>
            <span id="status-text">FRAMEWORK ACTIVE</span>
        </div>
        <label class="switch mb-0">
            <input type="checkbox" id="frameworkToggle" checked onchange="toggleFramework()">
            <span class="slider"></span>
        </label>
    </div>
</nav>

<div class="page">
    <!-- 5 Core Metrics -->
    <div class="metric-grid mb-4">
        <div class="metric-card">
            <div class="label">1. CPU Utilization <span class="badge-layer">Metric 1</span></div>
            <div class="value v-cpu" id="cpu-mean">-- %</div>
            <div class="sub">Avg across targets</div>
        </div>
        <div class="metric-card">
            <div class="label">2. RAM Usage <span class="badge-layer">Metric 2</span></div>
            <div class="value v-ram" id="mem-mean">-- %</div>
            <div class="sub">Avg across targets</div>
        </div>
        <div class="metric-card">
            <div class="label">3. Energy Cons. <span class="badge-layer">Metric 3</span></div>
            <div class="value v-energy" id="energy-total">-- kWh</div>
            <div class="sub">Total accumulated</div>
        </div>
        <div class="metric-card">
            <div class="label">4. Web Latency <span class="badge-layer">Metric 4</span></div>
            <div class="value v-latency" id="latency-p95">N/A</div>
            <div class="sub">Tracked via Locust</div>
        </div>
        <div class="metric-card">
            <div class="label">5. FW Overhead <span class="badge-layer">Metric 5</span></div>
            <div class="value v-overhead" id="overhead-mean">-- %</div>
            <div class="sub">HECF CPU (target &lt;5%)</div>
        </div>
    </div>

    <div class="row g-4 mb-4">
        <!-- Chart -->
        <div class="col-md-8">
            <div class="panel h-100">
                <div class="panel-header">
                    <h6>Live Resource Trend</h6>
                    <span class="panel-tag">HECF Monitoring</span>
                </div>
                <div class="panel-body">
                    <canvas id="resourceChart"></canvas>
                </div>
            </div>
        </div>
        <!-- Insights -->
        <div class="col-md-4">
            <div class="panel h-100">
                <div class="panel-header"><h6>Control Plane Insights</h6></div>
                <div class="panel-body d-flex flex-column" style="min-height:320px;">
                    <div>
                        <div class="insight-row">
                            <span class="insight-label">Spike Ratio (P95/P50)</span>
                            <span class="insight-val text-primary" id="avg-spike">--</span>
                        </div>
                        <div class="progress-thin">
                            <div class="progress-fill bg-primary" id="spike-bar" style="width:0%"></div>
                        </div>
                        <p style="font-size:11px;color:var(--text-muted);">Dictates Tier classification (Layer 3B)</p>

                        <div class="insight-row">
                            <span class="insight-label">Guardrail Interventions</span>
                            <span class="insight-val text-danger" id="guardrail-count">0</span>
                        </div>
                        <p style="font-size:11px;color:var(--text-muted);">Emergency caps applied (Layer 3A)</p>
                    </div>
                    <div class="status-box mt-auto">
                        <div class="icon">🚀</div>
                        <div>
                            <div class="title">Framework Active</div>
                            <div class="desc">Adaptive Shaping via cgroups v2</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Container Table -->
    <div class="panel">
        <div class="panel-header">
            <h6>Active Container Tracking — HECF 4-Layer Anatomy</h6>
            <span style="font-size:12px;color:var(--text-muted);" id="container-count"></span>
        </div>
        <div class="table-responsive">
            <table class="table mb-0">
                <thead>
                    <tr>
                        <th>Container (Target)</th>
                        <th>L2: CPU %</th>
                        <th>L2: MEM %</th>
                        <th>L3B: Tier Class</th>
                        <th>L3C: EMA Pred.</th>
                        <th>L4: Shaper Action</th>
                        <th>Power (W)</th>
                    </tr>
                </thead>
                <tbody id="container-table-body">
                    <tr><td colspan="7" class="text-center text-muted py-4">Waiting for HECF engine data…</td></tr>
                </tbody>
            </table>
        </div>
    </div>
</div>

<script>
// Host info
fetch('/api/system-info').then(r=>r.json()).then(d=>{
    document.getElementById('host-name').innerText = d.hostname || 'Node';
    document.getElementById('host-cpu').innerText = (d.vcpus||'?') + ' vCPU';
    document.getElementById('host-ram').innerText = d.ram_mb ? (d.ram_mb/1024).toFixed(1)+' GB RAM' : '? GB RAM';
});

// Framework toggle state
fetch('/api/status').then(r=>r.json()).then(d=>{
    const t = document.getElementById('frameworkToggle');
    t.checked = d.active;
    updateStatusUI(d.active);
});

function updateStatusUI(active) {
    const dot = document.getElementById('status-dot');
    const txt = document.getElementById('status-text');
    if (active) {
        dot.classList.remove('inactive');
        txt.innerText = 'FRAMEWORK ACTIVE';
        txt.style.color = 'var(--accent)';
    } else {
        dot.classList.add('inactive');
        txt.innerText = 'FRAMEWORK INACTIVE';
        txt.style.color = 'var(--text-muted)';
    }
}

function toggleFramework() {
    const active = document.getElementById('frameworkToggle').checked;
    fetch('/api/toggle', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({active}) });
    updateStatusUI(active);
}

// Chart
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.color = '#64748b';
const ctx = document.getElementById('resourceChart').getContext('2d');
const chart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [] },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
            x: {
                grid: { color: '#f1f5f9' },
                ticks: { maxTicksLimit: 8, font: { size: 10 } }
            },
            y: {
                grid: { color: '#f1f5f9' },
                suggestedMax: 100,
                title: { display: true, text: 'CPU Utilization %', font: { size: 11 } }
            }
        },
        plugins: {
            legend: { labels: { usePointStyle: true, boxWidth: 6, font: { size: 11 } } },
            tooltip: {
                backgroundColor: '#1e293b',
                titleColor: '#f1f5f9',
                bodyColor: '#cbd5e1',
                borderColor: '#334155',
                borderWidth: 1,
                padding: 10,
                cornerRadius: 6
            }
        }
    }
});

const COLORS = ['#1a56db','#0d9488','#7c3aed','#d97706','#dc2626',
                '#0891b2','#16a34a','#c026d3','#ea580c','#65a30d'];

async function fetchMetrics() {
    try {
        const res = await fetch('/api/metrics');
        const data = await res.json();
        if (data.status !== 'success' || !data.data.length) return;

        const rows = data.data;
        let cpuSum=0, memSum=0, energyTotal=0, overheadSum=0, spikeSum=0, spikeCount=0, guardrailCount=0;
        const timeSet=[], dsMap={}, latest={};

        rows.forEach(row => {
            const cpu = parseFloat(row.cpu_percent)||0;
            const mem = parseFloat(row.mem_percent)||0;
            const energy = parseFloat(row.energy_kwh)||0;
            const overhead = parseFloat(row.overhead_cpu)||0;
            const spike = parseFloat(row.spike_ratio)||0;

            cpuSum += cpu; memSum += mem; energyTotal += energy; overheadSum += overhead;
            if(spike > 0){ spikeSum += spike; spikeCount++; }
            if(row.action === 'GUARDRAIL') guardrailCount++;

            latest[row.container_name] = row;
            if(!timeSet.includes(row.time)) timeSet.push(row.time);
            if(!dsMap[row.container_name]) {
                const clr = COLORS[Object.keys(dsMap).length % COLORS.length];
                dsMap[row.container_name] = { label: row.container_name, data:[], borderColor: clr, backgroundColor: clr+'20', fill:true, tension:0.4, pointRadius:0, pointHoverRadius:4, borderWidth:1.5 };
            }
            dsMap[row.container_name].data.push(cpu);
        });

        const n = rows.length;
        document.getElementById('cpu-mean').innerText = (cpuSum/n).toFixed(1)+' %';
        document.getElementById('mem-mean').innerText = (memSum/n).toFixed(1)+' %';
        document.getElementById('energy-total').innerText = energyTotal.toFixed(6)+' kWh';
        document.getElementById('overhead-mean').innerText = (overheadSum/n).toFixed(2)+' %';

        const avgSpike = spikeCount > 0 ? spikeSum/spikeCount : 0;
        document.getElementById('avg-spike').innerText = avgSpike.toFixed(2);
        document.getElementById('spike-bar').style.width = Math.min((avgSpike/3)*100,100)+'%';
        document.getElementById('guardrail-count').innerText = guardrailCount;

        const trimmedLabels = timeSet.slice(-30).map(t => t.substring(11,16));
        chart.data.labels = trimmedLabels;
        chart.data.datasets = Object.values(dsMap).map(ds => ({ ...ds, data: ds.data.slice(-30) }));
        chart.update('none');

        const tbody = document.getElementById('container-table-body');
        const containers = Object.values(latest);
        document.getElementById('container-count').innerText = containers.length + ' containers';
        tbody.innerHTML = '';
        containers.forEach(c => {
            const tier = (c.tier||'N/A').toUpperCase();
            const action = (c.action||'').toUpperCase();
            const tierClass = tier==='AGGRESSIVE'?'tier-agg':tier==='BALANCED'?'tier-bal':tier==='SOFT'?'tier-soft':'tier-na';
            const actClass = action==='GUARDRAIL'?'act-guardrail':action==='AGGRESSIVE'?'act-agg':action==='BALANCED'?'act-bal':action==='SOFT'?'act-soft':'act-other';
            const cpu = parseFloat(c.cpu_percent||0).toFixed(1);
            const mem = parseFloat(c.mem_percent||0).toFixed(1);
            const ema = parseFloat(c.ema_pred||0).toFixed(1);
            const alpha = parseFloat(c.alpha||0).toFixed(2);
            const pw = parseFloat(c.power_watt||0).toFixed(1);
            tbody.innerHTML += `<tr>
                <td><strong>${c.container_name}</strong></td>
                <td>${cpu}%</td>
                <td>${mem}%</td>
                <td><span class="badge-tier ${tierClass}">${tier}</span></td>
                <td>${ema}% <small class="text-muted">(α=${alpha})</small></td>
                <td><span class="badge-action ${actClass}">${action}</span></td>
                <td class="fw-600">${pw} W</td>
            </tr>`;
        });
    } catch(e) { console.error('fetch error:', e); }
}

setInterval(fetchMetrics, 3000);
fetchMetrics();
</script>
</body>
</html>
"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "metrics.csv")
STATUS_PATH = os.path.join(BASE_DIR, "framework_status.json")
FIELDNAMES = ["time","container_name","cpu_percent","mem_percent","tier","action",
              "power_watt","energy_kwh","ema_pred","alpha","spike_ratio","p50","p95",
              "overhead_cpu","overhead_mem"]

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/metrics")
def api_metrics():
    if not os.path.isfile(CSV_PATH) or os.path.getsize(CSV_PATH) == 0:
        return jsonify({"status": "empty", "data": []})
    data = []
    try:
        with open(CSV_PATH, newline="") as f:
            reader = csv.DictReader(f, fieldnames=FIELDNAMES)
            for i, row in enumerate(reader):
                if i == 0 and row["time"] == "time":
                    continue
                data.append(row)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "data": []})
    return jsonify({"status": "success", "data": data[-200:]})

@app.route("/api/status")
def get_status():
    if os.path.isfile(STATUS_PATH):
        try:
            with open(STATUS_PATH) as f:
                return jsonify(json.load(f))
        except:
            pass
    return jsonify({"active": True})

@app.route("/api/toggle", methods=["POST"])
def toggle_status():
    req = request.json
    with open(STATUS_PATH, "w") as f:
        json.dump({"active": req.get("active", True)}, f)
    return jsonify({"status": "ok"})

@app.route("/api/download-csv")
def download_csv():
    if os.path.isfile(CSV_PATH):
        return send_file(CSV_PATH, mimetype='text/csv', as_attachment=True, download_name='hecf_metrics.csv')
    return "metrics.csv not ready yet", 404

@app.route("/api/system-info")
def system_info():
    cpu_count, mem_mb = 1, 0
    try:
        with open("/proc/cpuinfo") as f:
            cpu_count = sum(1 for l in f if l.strip().startswith("processor"))
    except: pass
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_mb = int(line.split()[1]) // 1024
                    break
    except: pass
    return jsonify({"vcpus": cpu_count, "ram_mb": mem_mb, "hostname": platform.node()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8092, debug=False)
