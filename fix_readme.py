import re

with open("README.md", "r") as f:
    content = f.read()

# Replace HTML header
html_header = """<div align="center">
  <h1>🌿 Hybrid Green Container Framework (HGCF)</h1>
  <p><b>An Adaptive, Lightweight, and Energy-Aware Docker Management System</b></p>
  
  <p>
    <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python Version" />
    <img src="https://img.shields.io/badge/Docker-Native-2496ED.svg?logo=docker" alt="Docker Native" />
    <img src="https://img.shields.io/badge/Overhead-&lt;5%25-success.svg" alt="Resource Overhead" />
    <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" />
  </p>
</div>

<hr />"""

markdown_header = """# 🌿 Hybrid Green Container Framework (HGCF)

**An Adaptive, Lightweight, and Energy-Aware Docker Management System**

![Python Version](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Docker Native](https://img.shields.io/badge/Docker-Native-2496ED.svg?logo=docker)
![Resource Overhead](https://img.shields.io/badge/Overhead-&lt;5%25-success.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---"""

content = content.replace(html_header, markdown_header)

# Fix trailing spaces
content = re.sub(r' \n', '\n', content)
content = re.sub(r' $', '', content, flags=re.MULTILINE)

# Fix blank lines around headings
# We will match headings and ensure they are surrounded by blank lines.
# But actually, I'll just do simple string replacements for the specific headings.
replacements = [
    ("### 1. Environment Profiler (`profiler.py`)\nAutomatically", "### 1. Environment Profiler (`profiler.py`)\n\nAutomatically"),
    ("### 2. Monitoring Engine (`monitor.py`)\nPulls", "### 2. Monitoring Engine (`monitor.py`)\n\nPulls"),
    ("### 3. Hybrid Control Engine (`engine.py`, `guardrail.py`, `tier_detector.py`, `predictor.py`)\nFeatures", "### 3. Hybrid Control Engine (`engine.py`, `guardrail.py`, `tier_detector.py`, `predictor.py`)\n\nFeatures"),
    ("### 4. Adaptive Resource Shaping (`shaper.py`)\nInterprets", "### 4. Adaptive Resource Shaping (`shaper.py`)\n\nInterprets"),
    ("### Pilar 1: Resource Stability\n1.", "### Pilar 1: Resource Stability\n\n1."),
    ("### Pilar 2: Operational Performance (via Locust)\n5.", "### Pilar 2: Operational Performance (via Locust)\n\n1."),
    ("6. **Latency", "2. **Latency"),
    ("7. **Throughput", "3. **Throughput"),
    ("8. **Error Rate", "4. **Error Rate"),
    ("9. **Container Restart", "5. **Container Restart"),
    ("### Pilar 3: Energy & Efficiency\n10.", "### Pilar 3: Energy & Efficiency\n\n1."),
    ("11. **Energy Consumption", "2. **Energy Consumption"),
    ("12. **Idle Resource Waste", "3. **Idle Resource Waste"),
    ("13. **Performance-per-Watt", "4. **Performance-per-Watt"),
    ("### Pilar 4: Environmental Impact\n14.", "### Pilar 4: Environmental Impact\n\n1."),
    ("15. **Carbon per Task", "2. **Carbon per Task"),
    ("16. **Thermal Stability", "3. **Thermal Stability"),
    ("### Pilar 5: Meta-Metrics\n17.", "### Pilar 5: Meta-Metrics\n\n1."),
    ("### Prerequisites\n-", "### Prerequisites\n\n-"),
    ("## 🧪 Testing Workload\nTo", "## 🧪 Testing Workload\n\nTo"),
    ("## 📜 License\nDistribute", "## 📜 License\n\nDistribute")
]

for old, new in replacements:
    content = content.replace(old, new)

# Fix lists not preceded by blank lines
content = content.replace("AI logic:\n-", "AI logic:\n\n-")
content = content.replace("meters:\n-", "meters:\n\n-")
content = content.replace("Locust:\n-", "Locust:\n\n-")

# Fix code blocks missing blank lines
content = content.replace("1. **Clone the repository**\n   ```bash", "1. **Clone the repository**\n\n   ```bash")
content = content.replace("3. **Deploy HGCF Daemon & UI**\n   ```bash", "3. **Deploy HGCF Daemon & UI**\n\n   ```bash")
content = content.replace("4. **Access the Beszel-style HGCF Analytics Dashboard**\n   Navigate to:\n   ```url", "4. **Access the Beszel-style HGCF Analytics Dashboard**\n   Navigate to:\n\n   ```url")
content = content.replace("using:\n```bash", "using:\n\n```bash")

with open("README.md", "w") as f:
    f.write(content)
