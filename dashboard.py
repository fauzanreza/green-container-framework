import os
import csv
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# Basic in-memory template for the dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HGCF | 17 Metrics Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }
        .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24); }
        .card-header { background-color: #0d1117; border-bottom: 1px solid #30363d; font-weight: 600; color: #8b949e; }
        .metric-value { font-size: 1.8rem; font-weight: 700; color: #58a6ff; }
        .metric-label { font-size: 0.8rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; }
        .nav-brand { font-weight: 700; color: #3fb950; font-size: 1.2rem; }
        .text-success { color: #3fb950 !important; }
        .text-danger { color: #f85149 !important; }
        .text-warning { color: #d29922 !important; }
        .text-info { color: #58a6ff !important; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark border-bottom border-secondary mb-4" style="background-color: #161b22 !important;">
        <div class="container-fluid">
            <span class="navbar-brand nav-brand">🌿 HGCF | Hybrid Green Container Framework</span>
        </div>
    </nav>
    <div class="container-fluid px-4">
        
        <div class="row mb-3">
            <h5 class="mb-3 text-info">Pilar 1: Resource Stability & Pilar 3: Energy Efficiency</h5>
            <div class="col-md-3 mb-3">
                <div class="card p-3">
                    <div class="metric-label">Avg CPU Utilization</div>
                    <div class="metric-value" id="cpu-mean">-- %</div>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="card p-3">
                    <div class="metric-label">Memory Usage (Mean)</div>
                    <div class="metric-value" id="ram-mean">-- %</div>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="card p-3">
                    <div class="metric-label">Power Consumption (Mean)</div>
                    <div class="metric-value text-warning" id="power-mean">-- W</div>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="card p-3">
                    <div class="metric-label">Estimated CO₂e</div>
                    <div class="metric-value text-success" id="carbon-total">-- gCO₂</div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-8 mb-4">
                <div class="card h-100">
                    <div class="card-header">Target Containers Resource Real-time</div>
                    <div class="card-body">
                        <canvas id="resourceChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-md-4 mb-4">
                <div class="card h-100">
                    <div class="card-header">17 Metrics Status</div>
                    <div class="card-body" style="font-size: 0.85rem;">
                        <ul class="list-group list-group-flush bg-transparent">
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>1. CPU Utilization (mean) (%)</span> <span class="badge bg-success">Active</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>2. CPU Variance (%²)</span> <span class="badge bg-success">Active</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>3. Memory Usage (mean) (GB)</span> <span class="badge bg-warning text-dark">Partial (%)</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>4. Memory Variance (%²)</span> <span class="badge bg-success">Active</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>5. Latency Average (ms)</span> <span class="badge bg-secondary">Awaiting Merge</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>6. Latency p95 (ms)</span> <span class="badge bg-secondary">Awaiting Merge</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>7. Throughput (req/s)</span> <span class="badge bg-secondary">Awaiting Merge</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>8. Error Rate (%)</span> <span class="badge bg-secondary">Awaiting Merge</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>9. Container Restart (count)</span> <span class="badge bg-secondary">Awaiting Merge</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>10. Power Consumption (mean) (Watt)</span> <span class="badge bg-success">Active</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>11. Energy Consumption (total) (kWh)</span> <span class="badge bg-success">Active</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>12. Idle Resource Waste (%)</span> <span class="badge bg-secondary">Awaiting Merge</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>13. Performance-per-Watt (req/J)</span> <span class="badge bg-secondary">Awaiting Merge</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>14. Estimated CO₂e (gCO₂)</span> <span class="badge bg-success">Active</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>15. Carbon per Task (g/req)</span> <span class="badge bg-secondary">Awaiting Merge</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>16. Thermal Stability (°C var)</span> <span class="badge bg-secondary">Pending Dev</span></li>
                            <li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between"><span>17. Framework Overhead (% CPU & RAM)</span> <span class="badge bg-warning text-dark">Partial</span></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('resourceChart').getContext('2d');
        const resourceChart = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets: [] },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
                    y: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' }, suggestedMax: 100, title: { display: true, text: 'Utilization %', color: '#8b949e' } }
                },
                plugins: {
                    legend: { labels: { color: '#c9d1d9' } }
                }
            }
        });

        async function fetchMetrics() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();
                
                if (data.status === 'success' && data.data.length > 0) {
                    const metrics = data.data;
                    
                    // Simple aggregation
                    let cpuSum = 0; let memSum = 0; let powerSum = 0; let maxCarbon = 0;
                    
                    // Chart grouping
                    const timeLabels = [];
                    const datasets = {};

                    metrics.forEach((row, i) => {
                        let c_cpu = parseFloat(row.cpu_percent) || 0;
                        let c_mem = parseFloat(row.mem_percent) || 0;
                        let c_power = parseFloat(row.power_watt) || 0;
                        let c_carbon = parseFloat(row.carbon_co2) || 0;
                        
                        cpuSum += c_cpu; memSum += c_mem; powerSum += c_power;
                        if(c_carbon > maxCarbon) maxCarbon = c_carbon;
                        
                        // For chart
                        if (!timeLabels.includes(row.time)) timeLabels.push(row.time);
                        if (!datasets[row.container_name]) {
                            datasets[row.container_name] = { label: `CPU % (${row.container_name})`, data: [], borderColor: '#' + Math.floor(Math.random()*16777215).toString(16), tension: 0.3 };
                        }
                        datasets[row.container_name].data.push(c_cpu);
                    });

                    // Limit points to last 20 easily
                    if(timeLabels.length > 20) {
                        timeLabels.splice(0, timeLabels.length - 20);
                        Object.keys(datasets).forEach(k => {
                           datasets[k].data.splice(0, datasets[k].data.length - 20); 
                        });
                    }

                    document.getElementById('cpu-mean').innerText = (cpuSum / metrics.length).toFixed(1) + ' %';
                    document.getElementById('ram-mean').innerText = (memSum / metrics.length).toFixed(1) + ' %';
                    // Power per record is avg W at that moment, averaging further is fine
                    document.getElementById('power-mean').innerText = (powerSum / metrics.length).toFixed(1) + ' W';
                    document.getElementById('carbon-total').innerText = (maxCarbon * 1000).toFixed(2) + ' gCO₂';

                    resourceChart.data.labels = timeLabels;
                    resourceChart.data.datasets = Object.values(datasets);
                    resourceChart.update();
                }
            } catch (err) {
                console.error("Error fetching data:", err);
            }
        }

        setInterval(fetchMetrics, 5000);
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
    
    # Return last 100 rows to avoid blowing up payload on browser
    return jsonify({"status": "success", "data": data[-100:]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8092, debug=False)
