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
    <title>HGCF | Enterprise Green Framework Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --glass-bg: rgba(20, 25, 35, 0.65);
            --glass-border: rgba(255, 255, 255, 0.08);
            --glow: 0 0 20px rgba(63, 185, 80, 0.4);
            --accent: #3fb950;
            --accent-glow: #2ea043;
            --bg-color: #0b0f19;
            --text-main: #e6edf3;
            --text-muted: #8b949e;
        }
        body {
            background-color: var(--bg-color);
            background-image: 
                radial-gradient(circle at 15% 50%, rgba(63, 185, 80, 0.08), transparent 25%),
                radial-gradient(circle at 85% 30%, rgba(88, 166, 255, 0.08), transparent 25%);
            color: var(--text-main);
            font-family: 'Outfit', sans-serif;
            min-height: 100vh;
        }
        .glass-card {
            background: var(--glass-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .glass-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.4), var(--glow);
        }
        .navbar-glass {
            background: rgba(11, 15, 25, 0.8) !important;
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--glass-border);
        }
        .nav-brand {
            font-weight: 700;
            color: var(--accent);
            font-size: 1.5rem;
            letter-spacing: -0.5px;
            text-shadow: 0 0 10px rgba(63, 185, 80, 0.5);
        }
        .metric-value {
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(180deg, #ffffff, #a5b4fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.2rem;
        }
        .metric-label {
            font-size: 0.85rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }
        .badge-layer {
            background: rgba(88, 166, 255, 0.15);
            color: #58a6ff;
            border: 1px solid rgba(88, 166, 255, 0.3);
            font-size: 0.75rem;
            padding: 4px 8px;
            border-radius: 12px;
            letter-spacing: 0.5px;
        }
        .table {
            color: var(--text-main);
            vertical-align: middle;
        }
        .table th {
            background-color: rgba(255, 255, 255, 0.03);
            border-bottom: 1px solid var(--glass-border);
            color: var(--text-muted);
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        .table td {
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            background: transparent;
        }
        .switch {
            position: relative;
            display: inline-block;
            width: 60px;
            height: 34px;
        }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: rgba(255,255,255,0.1);
            transition: .4s;
            border-radius: 34px;
            border: 1px solid var(--glass-border);
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 26px; width: 26px;
            left: 3px; bottom: 3px;
            background-color: var(--text-muted);
            transition: .4s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background-color: rgba(63, 185, 80, 0.3);
            border-color: var(--accent);
            box-shadow: var(--glow);
        }
        input:checked + .slider:before {
            transform: translateX(26px);
            background-color: var(--accent);
        }
        .pulse { animation: pulse-animation 2s infinite; }
        @keyframes pulse-animation {
            0% { box-shadow: 0 0 0 0 rgba(63, 185, 80, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(63, 185, 80, 0); }
            100% { box-shadow: 0 0 0 0 rgba(63, 185, 80, 0); }
        }
        .btn-glass {
            background: rgba(88, 166, 255, 0.1);
            border: 1px solid rgba(88, 166, 255, 0.3);
            color: #58a6ff;
            border-radius: 20px;
            padding: 5px 15px;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        .btn-glass:hover {
            background: rgba(88, 166, 255, 0.3);
            color: #fff;
        }
        .host-info {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 0.85rem;
            color: #c9d1d9;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark navbar-glass mb-4 sticky-top">
        <div class="container-fluid px-4">
            <div class="d-flex align-items-center">
                <span class="navbar-brand nav-brand mb-0">🌿 HGCF Enterprise</span>
                <div class="ms-4 host-info d-none d-md-flex align-items-center" id="host-info-badge">
                    <span class="me-3">📡 <span id="host-name">Node</span></span>
                    <span class="me-3">⚙️ <span id="host-cpu">0</span> vCPU</span>
                    <span>🧠 <span id="host-ram">0</span> GB RAM</span>
                </div>
            </div>
            
            <div class="d-flex align-items-center">
                <a href="/api/download-csv" target="_blank" class="btn btn-glass me-4 text-decoration-none d-flex align-items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="me-2" viewBox="0 0 16 16">
                        <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"/>
                        <path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"/>
                    </svg>
                    Export Metrics.csv
                </a>
                <span class="me-3 fw-bold" id="status-text" style="color: var(--accent)">FRAMEWORK ACTIVE</span>
                <label class="switch pulse" id="switch-pulse">
                    <input type="checkbox" id="frameworkToggle" checked onchange="toggleFramework()">
                    <span class="slider"></span>
                </label>
            </div>
        </div>
    </nav>
    <div class="container-fluid px-4 pb-5">
        
        <!-- Key Metrics -->
        <div class="row mb-4">
            <div class="col-md-3 mb-3">
                <div class="glass-card p-4 h-100">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div class="metric-label">Mean CPU Util</div>
                        <span class="badge-layer">Layer 2 (Monitor)</span>
                    </div>
                    <div class="metric-value" id="cpu-mean" style="background: linear-gradient(180deg, #7dd3fc, #0284c7); -webkit-background-clip: text;">-- %</div>
                    <small class="text-muted">Avg across all containers</small>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="glass-card p-4 h-100">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div class="metric-label">Mean AFMV Pred</div>
                        <span class="badge-layer">Layer 3C (Predictor)</span>
                    </div>
                    <div class="metric-value" id="pred-mean" style="background: linear-gradient(180deg, #c084fc, #7e22ce); -webkit-background-clip: text;">-- %</div>
                    <small class="text-muted">Next-tick CPU Prediction</small>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="glass-card p-4 h-100">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div class="metric-label">Avg Power Cons.</div>
                        <span class="badge-layer">Energy Module</span>
                    </div>
                    <div class="metric-value" id="power-mean" style="background: linear-gradient(180deg, #fde047, #ca8a04); -webkit-background-clip: text;">-- W</div>
                    <small class="text-muted">Linear Model Estimation</small>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="glass-card p-4 h-100">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div class="metric-label">Carbon Footprint</div>
                        <span class="badge-layer">Carbon Tracking</span>
                    </div>
                    <div class="metric-value" id="carbon-total" style="background: linear-gradient(180deg, #86efac, #16a34a); -webkit-background-clip: text;">-- kgCO₂</div>
                    <small class="text-muted">Total Accumulated</small>
                </div>
            </div>
        </div>

        <div class="row mb-4">
            <!-- Main Chart -->
            <div class="col-md-8 mb-4">
                <div class="glass-card h-100 p-4">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h5 class="m-0 fw-bold">Live Resource & Prediction Trend</h5>
                        <span class="badge-layer">Layer 2 & Layer 3 Integration</span>
                    </div>
                    <div style="height: 350px;">
                        <canvas id="resourceChart"></canvas>
                    </div>
                </div>
            </div>
            
            <!-- Efficiency Highlights -->
            <div class="col-md-4 mb-4">
                <div class="glass-card h-100 p-4 d-flex flex-column">
                    <h5 class="fw-bold mb-4">Efficiency Highlights</h5>
                    
                    <div class="mb-4">
                        <div class="d-flex justify-content-between mb-1">
                            <span class="text-muted">Spike Ratio (p95/p50)</span>
                            <span class="fw-bold text-info" id="avg-spike">--</span>
                        </div>
                        <div class="progress" style="height: 6px; background: rgba(255,255,255,0.1)">
                            <div class="progress-bar bg-info" id="spike-bar" style="width: 0%"></div>
                        </div>
                        <small class="text-muted d-block mt-1">Dictates Tier classification (Layer 3B)</small>
                    </div>

                    <div class="mb-4">
                        <div class="d-flex justify-content-between mb-1">
                            <span class="text-muted">Guardrail Interventions</span>
                            <span class="fw-bold text-danger" id="guardrail-count">0</span>
                        </div>
                        <small class="text-muted d-block mt-1">Emergency caps applied (Layer 3A)</small>
                    </div>
                    
                    <div class="mb-4 mt-auto p-3 rounded" style="background: rgba(63, 185, 80, 0.1); border: 1px solid rgba(63, 185, 80, 0.2)">
                        <div class="d-flex align-items-center">
                            <div style="font-size: 2rem; margin-right: 15px;">🚀</div>
                            <div>
                                <div class="fw-bold text-success mb-1">Framework Status</div>
                                <div class="text-muted small">Adaptive Shaping (Layer 4) is controlling cgroups effectively.</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Containers Table -->
        <div class="row">
            <div class="col-12">
                <div class="glass-card p-4">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h5 class="m-0 fw-bold">Active Container Tracking (4-Layer Anatomy)</h5>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover table-borderless">
                            <thead>
                                <tr>
                                    <th>Container (Target)</th>
                                    <th>L2: CPU %</th>
                                    <th>L2: MEM %</th>
                                    <th>L3B: Tier Class</th>
                                    <th>L3C: AFMV Pred.</th>
                                    <th>L4: Shaper Action</th>
                                    <th>Power (W)</th>
                                </tr>
                            </thead>
                            <tbody id="container-table-body">
                                <tr>
                                    <td colspan="7" class="text-center text-muted py-4">Waiting for HGCF Engine data...</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // System Info Fetch
        fetch('/api/system-info').then(r => r.json()).then(data => {
            document.getElementById('host-name').innerText = data.hostname || "Node";
            document.getElementById('host-cpu').innerText = data.vcpus || "0";
            document.getElementById('host-ram').innerText = data.ram_mb ? (data.ram_mb / 1024).toFixed(1) : "0";
        });

        // Chart configuration (Glassmorphism style)
        Chart.defaults.color = '#8b949e';
        Chart.defaults.font.family = "'Outfit', sans-serif";
        const ctx = document.getElementById('resourceChart').getContext('2d');
        const resourceChart = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets: [] },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: { 
                        grid: { color: 'rgba(255,255,255,0.05)' }, 
                        suggestedMax: 100, 
                        title: { display: true, text: 'CPU Utilization %' } 
                    }
                },
                plugins: {
                    legend: { labels: { usePointStyle: true, boxWidth: 8 } },
                    tooltip: {
                        backgroundColor: 'rgba(22, 27, 34, 0.9)',
                        titleColor: '#fff', bodyColor: '#c9d1d9',
                        borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1,
                        padding: 12, cornerRadius: 8
                    }
                }
            }
        });

        const colorPalette = ['#3fb950', '#58a6ff', '#f85149', '#d29922', '#a371f7'];

        // Initial Toggle State fetch
        fetch('/api/status').then(r => r.json()).then(data => {
            const t = document.getElementById('frameworkToggle');
            const p = document.getElementById('switch-pulse');
            const st = document.getElementById('status-text');
            t.checked = data.active;
            if(!data.active) {
                p.classList.remove('pulse');
                st.innerText = "FRAMEWORK INACTIVE";
                st.style.color = "#8b949e";
            }
        });

        function toggleFramework() {
            const isChecked = document.getElementById('frameworkToggle').checked;
            const p = document.getElementById('switch-pulse');
            const st = document.getElementById('status-text');
            
            fetch('/api/toggle', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({active: isChecked})
            });

            if(isChecked) {
                p.classList.add('pulse');
                st.innerText = "FRAMEWORK ACTIVE";
                st.style.color = "var(--accent)";
            } else {
                p.classList.remove('pulse');
                st.innerText = "FRAMEWORK INACTIVE";
                st.style.color = "var(--text-muted)";
            }
        }

        async function fetchMetrics() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();
                
                if (data.status === 'success' && data.data.length > 0) {
                    const metrics = data.data;
                    
                    let cpuSum = 0; let memSum = 0; let powerSum = 0; let predSum = 0;
                    let maxCarbon = 0; let spikeSum = 0; let guardrailCount = 0;
                    
                    const timeLabels = [];
                    const datasets = {};
                    const latestContainers = {}; // For table

                    metrics.forEach((row, i) => {
                        let c_cpu = parseFloat(row.cpu_percent) || 0;
                        let c_mem = parseFloat(row.mem_percent) || 0;
                        let c_power = parseFloat(row.power_watt) || 0;
                        let c_carbon = parseFloat(row.carbon_co2) || 0;
                        let c_pred = parseFloat(row.afmv_pred) || 0;
                        let c_spike = parseFloat(row.spike_ratio) || 0;
                        
                        cpuSum += c_cpu; powerSum += c_power; predSum += c_pred;
                        if(c_carbon > maxCarbon) maxCarbon = c_carbon;
                        if(c_spike > 0) spikeSum += c_spike;
                        if(row.action === 'GUARDRAIL') guardrailCount++;
                        
                        // Capture latest state for table
                        latestContainers[row.container_name] = row;

                        // Charting
                        if (!timeLabels.includes(row.time)) timeLabels.push(row.time);
                        if (!datasets[row.container_name]) {
                            let clr = colorPalette[Object.keys(datasets).length % colorPalette.length];
                            datasets[row.container_name] = { 
                                label: row.container_name, 
                                data: [], 
                                borderColor: clr,
                                backgroundColor: clr + '20',
                                fill: true,
                                tension: 0.4,
                                pointRadius: 0,
                                pointHoverRadius: 6
                            };
                        }
                        datasets[row.container_name].data.push(c_cpu);
                    });

                    // Keep last 30 points
                    if(timeLabels.length > 30) {
                        timeLabels.splice(0, timeLabels.length - 30);
                        Object.keys(datasets).forEach(k => {
                           datasets[k].data.splice(0, datasets[k].data.length - 30); 
                        });
                    }

                    // Update Top Metrics
                    document.getElementById('cpu-mean').innerText = (cpuSum / metrics.length).toFixed(1) + ' %';
                    document.getElementById('pred-mean').innerText = (predSum / metrics.length).toFixed(1) + ' %';
                    document.getElementById('power-mean').innerText = (powerSum / metrics.length).toFixed(1) + ' W';
                    document.getElementById('carbon-total').innerText = maxCarbon.toFixed(4) + ' kgCO₂';

                    // Update Highlights
                    let avgSpike = spikeSum / metrics.length;
                    document.getElementById('avg-spike').innerText = avgSpike.toFixed(2);
                    document.getElementById('spike-bar').style.width = Math.min((avgSpike / 3) * 100, 100) + '%';
                    document.getElementById('guardrail-count').innerText = guardrailCount;

                    // Update Chart
                    resourceChart.data.labels = timeLabels;
                    resourceChart.data.datasets = Object.values(datasets);
                    resourceChart.update();

                    // Update Table
                    const tbody = document.getElementById('container-table-body');
                    tbody.innerHTML = '';
                    Object.values(latestContainers).forEach(c => {
                        let tierColor = c.tier === 'aggressive' ? 'text-danger' : (c.tier === 'balanced' ? 'text-warning' : 'text-success');
                        let actionColor = c.action === 'GUARDRAIL' ? 'bg-danger text-white' : 'bg-secondary text-white';
                        if(c.action === 'AGGRESSIVE') actionColor = 'bg-warning text-dark';
                        if(c.action === 'SOFT') actionColor = 'bg-success text-white';
                        if(c.action === 'INACTIVE') actionColor = 'bg-dark text-muted border border-secondary';

                        tbody.innerHTML += `
                            <tr>
                                <td class="fw-bold">${c.container_name}</td>
                                <td>${c.cpu_percent}%</td>
                                <td>${c.mem_percent}%</td>
                                <td class="fw-bold ${tierColor}">${c.tier.toUpperCase()}</td>
                                <td><span class="badge bg-dark border border-secondary">${parseFloat(c.afmv_pred).toFixed(1)}%</span> (α=${parseFloat(c.alpha||0).toFixed(2)})</td>
                                <td><span class="badge ${actionColor}">${c.action}</span></td>
                                <td class="text-warning">${c.power_watt} W</td>
                            </tr>
                        `;
                    });
                }
            } catch (err) {
                console.error("Error fetching data:", err);
            }
        }

        setInterval(fetchMetrics, 3000);
        fetchMetrics();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/metrics")
def api_metrics():
    csv_file = "metrics.csv"
    if not os.path.exists(csv_file):
        return jsonify({"status": "empty", "data": []})
    
    data = []
    with open(csv_file, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    
    return jsonify({"status": "success", "data": data[-150:]})

@app.route("/api/status", methods=["GET"])
def get_status():
    status_file = "framework_status.json"
    if os.path.exists(status_file):
        try:
            with open(status_file, "r") as f:
                return jsonify(json.load(f))
        except:
            pass
    return jsonify({"active": True})

@app.route("/api/toggle", methods=["POST"])
def toggle_status():
    status_file = "framework_status.json"
    req = request.json
    with open(status_file, "w") as f:
        json.dump({"active": req.get("active", True)}, f)
    return jsonify({"status": "ok"})

@app.route("/api/download-csv")
def download_csv():
    csv_file = "metrics.csv"
    if os.path.exists(csv_file):
        return send_file(csv_file, mimetype='text/csv', as_attachment=True, download_name='hgcf_metrics.csv')
    return "File metrics.csv not found", 404

@app.route("/api/system-info")
def system_info():
    cpu_count = 1
    mem_mb = 0
    try:
        with open("/proc/cpuinfo") as f:
            cpu_count = sum(1 for line in f if line.strip().startswith("processor"))
    except:
        pass
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_mb = int(line.split()[1]) // 1024
                    break
    except:
        pass
    return jsonify({
        "vcpus": cpu_count, 
        "ram_mb": mem_mb, 
        "hostname": platform.node()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8092, debug=False)
