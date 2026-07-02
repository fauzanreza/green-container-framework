import os

with open("dashboard.py", "r") as f:
    content = f.read()

# 1. Add HTOP and Custom Legend styles
css_patch = """
        /* ---- CHART & LEGEND ---- */
        #resourceChart { min-height: 250px; }
        .custom-legend {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            max-height: 80px;
            overflow-y: auto;
            padding: 8px;
            background: #f8fafc;
            border-radius: 8px;
            margin-bottom: 12px;
            border: 1px solid var(--border);
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 11px;
            cursor: pointer;
            padding: 2px 6px;
            border-radius: 4px;
            transition: background 0.2s;
        }
        .legend-item:hover { background: #e2e8f0; }
        .legend-color { width: 10px; height: 10px; border-radius: 2px; }

        /* ---- HTOP STYLES ---- */
        .htop-panel {
            background: #0f172a;
            color: #e2e8f0;
            font-family: 'Courier New', Courier, monospace;
            font-size: 13px;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 24px;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        @media (min-width: 768px) {
            .htop-panel { flex-direction: row; gap: 24px; }
        }
        .htop-col { flex: 1; display: flex; flex-direction: column; gap: 4px; }
        .htop-row {
            display: flex;
            align-items: center;
            white-space: pre;
        }
        .htop-label { color: #38bdf8; width: 50px; flex-shrink: 0; }
        .htop-bar-bg {
            flex-grow: 1;
            background: #1e293b;
            height: 14px;
            margin: 0 8px;
            position: relative;
        }
        .htop-bar-fill { height: 100%; background: #22c55e; transition: width 1s; }
        .htop-bar-text { position: absolute; top: -1px; right: 4px; font-size: 11px; color: #f8fafc; text-shadow: 1px 1px 1px #000; }
        .htop-sys-label { color: #38bdf8; }
        .htop-sys-val { color: #f8fafc; font-weight: bold; }
    </style>
"""
content = content.replace("    </style>", css_patch)

# 2. Insert HTOP HTML
html_patch = """
    </div>

    <!-- HTOP Panel -->
    <div class="htop-panel" id="htop-panel">
        <div class="htop-col" id="htop-cpus">
            <div class="text-muted" style="font-size: 11px;">Loading htop data...</div>
        </div>
        <div class="htop-col">
            <div class="htop-row">
                <span class="htop-label">Mem[</span>
                <div class="htop-bar-bg"><div class="htop-bar-fill" id="htop-mem-bar" style="width:0%;"></div><span class="htop-bar-text" id="htop-mem-text">0G/0G</span></div>
                <span style="color:#38bdf8;">]</span>
            </div>
            <div class="htop-row">
                <span class="htop-label">Swp[</span>
                <div class="htop-bar-bg"><div class="htop-bar-fill" id="htop-swp-bar" style="width:0%; background:#ef4444;"></div><span class="htop-bar-text" id="htop-swp-text">0G/0G</span></div>
                <span style="color:#38bdf8;">]</span>
            </div>
            <div class="htop-row mt-3">
                <span class="htop-sys-label">Tasks: </span><span class="htop-sys-val" id="htop-tasks">0</span><span class="htop-sys-label"> total</span>
            </div>
            <div class="htop-row">
                <span class="htop-sys-label">Load average: </span><span class="htop-sys-val" id="htop-load">0.00 0.00 0.00</span>
            </div>
            <div class="htop-row">
                <span class="htop-sys-label">Uptime: </span><span class="htop-sys-val" id="htop-uptime">0 days, 00:00:00</span>
            </div>
        </div>
    </div>

    <div class="row g-4 mb-4">
"""
content = content.replace("    </div>\n\n    <div class=\"row g-4 mb-4\">", html_patch)

# 3. Add Custom Legend HTML
legend_patch = """
                <div class="panel-body">
                    <div id="customLegend" class="custom-legend"></div>
                    <canvas id="resourceChart"></canvas>
"""
content = content.replace("""                <div class="panel-body">
                    <canvas id="resourceChart"></canvas>""", legend_patch)

# 4. Modify Chart Options and Add HTOP JS
js_patch = """
        plugins: {
            legend: { display: false },
            tooltip: {
"""
content = content.replace("""        plugins: {
            legend: { labels: { usePointStyle: true, boxWidth: 6, font: { size: 11 } } },
            tooltip: {""", js_patch)

js_htop_patch = """
function renderCustomLegend() {
    const legendDiv = document.getElementById('customLegend');
    let html = '';
    chart.data.datasets.forEach((ds, i) => {
        const hidden = chart.getDatasetMeta(i).hidden;
        const op = hidden ? 0.4 : 1;
        html += `<div class="legend-item" style="opacity:${op}" onclick="toggleDataset(${i})">
            <div class="legend-color" style="background:${ds.borderColor}"></div>
            <span>${ds.label}</span>
        </div>`;
    });
    legendDiv.innerHTML = html;
}

window.toggleDataset = function(i) {
    const meta = chart.getDatasetMeta(i);
    meta.hidden = meta.hidden === null ? !chart.data.datasets[i].hidden : null;
    chart.update('none');
    renderCustomLegend();
};

async function fetchHtop() {
    try {
        const res = await fetch('/api/htop');
        const data = await res.json();
        
        let cpuHtml = '';
        data.cpus.forEach((cpu, i) => {
            cpuHtml += `<div class="htop-row">
                <span class="htop-label">${i}[</span>
                <div class="htop-bar-bg"><div class="htop-bar-fill" style="width:${cpu}%;"></div><span class="htop-bar-text">${cpu.toFixed(1)}%</span></div>
                <span style="color:#38bdf8;">]</span>
            </div>`;
        });
        document.getElementById('htop-cpus').innerHTML = cpuHtml;
        
        const m = data.memory;
        document.getElementById('htop-mem-bar').style.width = m.mem_percent + '%';
        document.getElementById('htop-mem-text').innerText = `${m.mem_used_gb}G/${m.mem_total_gb}G`;
        document.getElementById('htop-swp-bar').style.width = m.swap_percent + '%';
        document.getElementById('htop-swp-text').innerText = `${m.swap_used_gb}G/${m.swap_total_gb}G`;
        
        const s = data.system;
        document.getElementById('htop-tasks').innerText = s.tasks;
        document.getElementById('htop-load').innerText = s.load.map(x=>x.toFixed(2)).join(' ');
        document.getElementById('htop-uptime').innerText = s.uptime;
    } catch(e) {}
}
setInterval(fetchHtop, 2000);
fetchHtop();

async function fetchLatency() {
    try {
        const res = await fetch('/api/latency');
        const data = await res.json();
        if(data.p95 && data.p95 !== 'N/A') {
            document.getElementById('latency-p95').innerText = data.p95 + ' ms';
        }
    } catch(e) {}
}
setInterval(fetchLatency, 5000);
fetchLatency();

async function fetchMetrics() {
"""
content = content.replace("async function fetchMetrics() {", js_htop_patch)

js_legend_update = """
        chart.update('none');
        renderCustomLegend();
"""
content = content.replace("        chart.update('none');", js_legend_update)

# 5. Add Python Endpoints
python_patch = """
_last_cpu_stat = {}

def get_cpu_percents():
    global _last_cpu_stat
    try:
        with open("/proc/stat") as f:
            lines = f.readlines()
    except Exception:
        return []
    
    current_stat = {}
    percents = []
    
    for line in lines:
        if line.startswith("cpu") and line.strip() != "cpu":
            parts = line.split()
            cpu_name = parts[0]
            try:
                user = float(parts[1])
                nice = float(parts[2])
                system = float(parts[3])
                idle = float(parts[4])
                iowait = float(parts[5])
                irq = float(parts[6])
                softirq = float(parts[7])
                steal = float(parts[8])
                
                idle_total = idle + iowait
                non_idle = user + nice + system + irq + softirq + steal
                total = idle_total + non_idle
                
                current_stat[cpu_name] = (idle_total, total)
                
                if cpu_name in _last_cpu_stat:
                    prev_idle, prev_total = _last_cpu_stat[cpu_name]
                    total_diff = total - prev_total
                    idle_diff = idle_total - prev_idle
                    
                    if total_diff > 0:
                        percent = (total_diff - idle_diff) / total_diff * 100
                    else:
                        percent = 0.0
                    percents.append(round(percent, 1))
                else:
                    percents.append(0.0)
            except:
                pass
                
    _last_cpu_stat.update(current_stat)
    return percents

def get_mem_info():
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].replace(":", "")] = int(parts[1])
    except Exception:
        pass
    
    mem_total = info.get("MemTotal", 0)
    mem_free = info.get("MemFree", 0)
    buffers = info.get("Buffers", 0)
    cached = info.get("Cached", 0)
    swap_total = info.get("SwapTotal", 0)
    swap_free = info.get("SwapFree", 0)
    
    mem_used = mem_total - mem_free - buffers - cached
    swap_used = swap_total - swap_free
    
    return {
        "mem_total_gb": round(mem_total / (1024*1024), 2),
        "mem_used_gb": round(mem_used / (1024*1024), 2),
        "mem_percent": round((mem_used / mem_total * 100), 1) if mem_total > 0 else 0,
        "swap_total_gb": round(swap_total / (1024*1024), 2),
        "swap_used_gb": round(swap_used / (1024*1024), 2),
        "swap_percent": round((swap_used / swap_total * 100), 1) if swap_total > 0 else 0
    }

def get_sys_stats():
    import os
    load = [0.0, 0.0, 0.0]
    uptime = "0 days, 00:00:00"
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            load = [float(parts[0]), float(parts[1]), float(parts[2])]
    except Exception:
        pass
        
    try:
        with open("/proc/uptime") as f:
            up_seconds = float(f.read().split()[0])
            days = int(up_seconds // 86400)
            hours = int((up_seconds % 86400) // 3600)
            mins = int((up_seconds % 3600) // 60)
            secs = int(up_seconds % 60)
            uptime = f"{days} days, {hours:02d}:{mins:02d}:{secs:02d}"
    except Exception:
        pass
        
    tasks = 0
    try:
        tasks = len([d for d in os.listdir("/proc") if d.isdigit()])
    except Exception:
        pass
        
    return {
        "load": load,
        "uptime": uptime,
        "tasks": tasks
    }

@app.route("/api/htop")
def api_htop():
    return jsonify({
        "cpus": get_cpu_percents(),
        "memory": get_mem_info(),
        "system": get_sys_stats()
    })

LOCUST_CSV_PATH = os.path.join(BASE_DIR, "locustfiles", "results_stats.csv")

@app.route("/api/latency")
def api_latency():
    try:
        if os.path.isfile(LOCUST_CSV_PATH):
            with open(LOCUST_CSV_PATH, newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("Type") == "Aggregated" or row.get("Name") == "Aggregated":
                        p95 = row.get("95%") or row.get("95% (ms)")
                        if p95:
                            return jsonify({"p95": p95})
    except Exception:
        pass
    return jsonify({"p95": "N/A"})

@app.route("/api/download-csv")
"""
content = content.replace("@app.route(\"/api/download-csv\")", python_patch)

with open("dashboard.py", "w") as f:
    f.write(content)
