#!/usr/bin/env python3
"""
scripts/analyze_24runs.py
Evaluasi Statistik Eksperimen RCBD (Stage B 24 Run / Stage B+ 72 Run) — 100% Python Standard Library!
Selain mencetak hasil ke terminal, script ini otomatis menghasilkan di dalam folder sesi:
1. statistical_report.md  (Tabel statistik lengkap, ELP, evaluasi Gate 2, dan perbandingan BrownoutCon)
2. analysis_summary.ipynb (Jupyter Notebook interaktif untuk eksplorasi & grafik tesis Bab IV)
"""

import os
import sys
import csv
import json
import math
from collections import defaultdict


def mean(arr: list[float]) -> float:
    return sum(arr) / len(arr) if arr else 0.0


def std_sample(arr: list[float]) -> float:
    n = len(arr)
    if n < 2:
        return 0.0
    m = mean(arr)
    var = sum((x - m) ** 2 for x in arr) / (n - 1)
    return math.sqrt(var)


def wilcoxon_signed_rank_exact(x: list[float], y: list[float]) -> tuple[float, float]:
    """Exact two-sided Paired Wilcoxon Signed-Rank Test using 100% Python stdlib."""
    d = [float(xi) - float(yi) for xi, yi in zip(x, y) if (float(xi) - float(yi)) != 0.0]
    n = len(d)
    if n == 0:
        return 0.0, 1.0

    abs_d = [abs(val) for val in d]
    order = sorted(range(n), key=lambda idx: abs_d[idx])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs_d[order[j + 1]] == abs_d[order[i]]:
            j += 1
        avg_rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1

    w_pos = sum(ranks[idx] for idx in range(n) if d[idx] > 0)
    w_neg = sum(ranks[idx] for idx in range(n) if d[idx] < 0)
    w_stat = min(w_pos, w_neg)
    total_rank_sum = sum(ranks)

    total_configs = 1 << n
    extreme_count = 0
    for mask in range(total_configs):
        s = 0.0
        for bit in range(n):
            if (mask >> bit) & 1:
                s += ranks[bit]
        s_min = min(s, total_rank_sum - s)
        if s_min <= w_stat + 1e-9:
            extreme_count += 1

    p_val = min(1.0, extreme_count / float(total_configs))
    return w_stat, p_val


def cohens_d_paired(x: list[float], y: list[float]) -> float:
    """Paired Cohen's d_z = mean(diff) / sd(diff)."""
    diff = [float(xi) - float(yi) for xi, yi in zip(x, y)]
    if len(diff) < 2:
        return 0.0
    sd = std_sample(diff)
    if sd <= 1e-12:
        return 0.0
    return mean(diff) / sd


def ci95(arr: list[float]) -> tuple[float, float, float]:
    """Return (mean, sd, half_width_95ci) using t-critical for df=len-1."""
    a = [float(v) for v in arr]
    n = len(a)
    if n == 0:
        return 0.0, 0.0, 0.0
    m = mean(a)
    if n < 2:
        return m, 0.0, 0.0
    sd = std_sample(a)
    t_table = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
               6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}
    t_crit = t_table.get(n - 1, 1.96)
    hw = t_crit * (sd / math.sqrt(n))
    return m, sd, hw


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni step-down multiple testing correction."""
    m = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        adj = min(1.0, p * (m - rank))
        running_max = max(running_max, adj)
        adjusted[orig_idx] = running_max
    return adjusted


def generate_rcbd_notebook(session_dir: str):
    """Generate analysis_summary.ipynb inside session_dir for Jupyter/Colab visualization."""
    nb = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# 📊 HECF Experiment Analysis (RCBD: Stage B / Stage B+)\n",
                    "Notebook ini di-generate otomatis dari hasil eksperimen di folder sesi ini.\n",
                    "Struktur direktori sesi: `<mode>/json/block_<1..6>/rep_<1..R>/` beserta `summary_all_runs.csv`."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "import os, glob\n",
                    "import pandas as pd\n",
                    "import matplotlib.pyplot as plt\n",
                    "import seaborn as sns\n\n",
                    "sns.set_theme(style='whitegrid')\n",
                    "plt.rcParams['figure.figsize'] = (11, 6)\n",
                    "df = pd.read_csv('summary_all_runs.csv')\n",
                    "df['elp'] = df['target_kwh'] * df['p95_rt_ms']\n",
                    "display(df.head(10))"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 1. Ringkasan Metrik per Mode (Mean ± SD)"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "summary = df.groupby('mode')[['target_kwh', 'rapl_pkg_kwh', 'mean_rt_ms', 'p95_rt_ms', 'rps', 'fail_count', 'overhead_cpu_pct', 'freeze_sec', 'elp']].agg(['mean', 'std'])\n",
                    "display(summary)"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 2. Grafik Perbandingan Konsumsi Energi (kWh) & Latensi P95 (ms)"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "fig, axes = plt.subplots(1, 3, figsize=(16, 5))\n",
                    "order = ['default_docker', 'static_cap', 'reactive_only', 'full_hecf']\n",
                    "sns.barplot(data=df, x='mode', y='target_kwh', order=order, ax=axes[0], palette='viridis')\n",
                    "axes[0].set_title('Container Energy Consumption (kWh - RAPL)')\n",
                    "axes[0].tick_params(axis='x', rotation=20)\n\n",
                    "sns.barplot(data=df, x='mode', y='p95_rt_ms', order=order, ax=axes[1], palette='magma')\n",
                    "axes[1].axhline(500, color='red', linestyle='--', label='SLA 500ms')\n",
                    "axes[1].set_title('Web Latency P95 (ms)')\n",
                    "axes[1].tick_params(axis='x', rotation=20)\n",
                    "axes[1].legend()\n\n",
                    "sns.barplot(data=df, x='mode', y='elp', order=order, ax=axes[2], palette='crest')\n",
                    "axes[2].set_title('Energy-Latency Product (ELP = kWh × P95 ms)')\n",
                    "axes[2].tick_params(axis='x', rotation=20)\n",
                    "plt.tight_layout()\n",
                    "plt.show()"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 3. Time-Series Trajectory per Mode (dari Subfolder `<mode>/json/block_1/rep_1/`)"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=False)\n",
                    "for mode in ['default_docker', 'static_cap', 'reactive_only', 'full_hecf']:\n",
                    "    files = glob.glob(os.path.join(mode, 'json', 'block_1', 'rep_1', '*_server_metrics.csv'))\n",
                    "    if files:\n",
                    "        mdf = pd.read_csv(files[0])\n",
                    "        mdf['sample_idx'] = range(len(mdf))\n",
                    "        axes[0].plot(mdf['sample_idx'], mdf['cpu_percent'], label=mode)\n",
                    "        axes[1].plot(mdf['sample_idx'], mdf['power_watt'], label=mode)\n",
                    "axes[0].set_title('Container CPU Utilization (%) over 16-Minute Multi-Phase Run (Block 1)')\n",
                    "axes[0].set_ylabel('CPU %')\n",
                    "axes[0].legend()\n",
                    "axes[1].set_title('Container Attributed RAPL Power (Watts) over 16-Minute Run (Block 1)')\n",
                    "axes[1].set_ylabel('Power (W)')\n",
                    "axes[1].set_xlabel('Sample Index')\n",
                    "axes[1].legend()\n",
                    "plt.tight_layout()\n",
                    "plt.show()"
                ]
            }
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10.0"}
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }
    nb_path = os.path.join(session_dir, "analysis_summary.ipynb")
    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=2)
    return nb_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/analyze_24runs.py <summary_all_runs.csv>")
        sys.exit(1)

    csv_path = os.path.abspath(sys.argv[1])
    session_dir = os.path.dirname(csv_path)

    raw_data = defaultdict(lambda: defaultdict(list))
    total_gr, total_t1, total_mf, total_fails = 0, 0, 0, 0

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            b = int(row["block"])
            m = row["mode"]
            kwh_val = float(row.get("target_kwh") or row.get("rapl_kwh") or 0.0)
            pkg_kwh_val = float(row.get("rapl_pkg_kwh") or row.get("rapl_kwh") or 0.0)
            p95_val = float(row["p95_rt_ms"])
            fails_val = int(row["fail_count"])
            gr_val = int(row.get("guardrail_triggers", 0))
            t1_val = int(row.get("tier1_triggers", 0))
            mf_val = int(row.get("microfreeze_triggers", 0))

            total_gr += gr_val
            total_t1 += t1_val
            total_mf += mf_val
            total_fails += fails_val

            raw_data[m][b].append({
                "kwh": kwh_val,
                "pkg_kwh": pkg_kwh_val,
                "mean_rt": float(row["mean_rt_ms"]),
                "p95_rt": p95_val,
                "elp": kwh_val * p95_val,
                "fails": fails_val,
                "oh": float(row["overhead_cpu_pct"]),
                "freeze_s": float(row.get("freeze_sec", 0.0)),
            })

    # Average across replications within each (mode, block) pair
    data = defaultdict(dict)
    for m, blocks_dict in raw_data.items():
        for b, rep_list in blocks_dict.items():
            data[m][b] = {
                "kwh": mean([r["kwh"] for r in rep_list]),
                "pkg_kwh": mean([r["pkg_kwh"] for r in rep_list]),
                "mean_rt": mean([r["mean_rt"] for r in rep_list]),
                "p95_rt": mean([r["p95_rt"] for r in rep_list]),
                "elp": mean([r["elp"] for r in rep_list]),
                "fails": sum(r["fails"] for r in rep_list),
                "oh": mean([r["oh"] for r in rep_list]),
                "freeze_s": mean([r["freeze_s"] for r in rep_list]),
            }

    modes = ["default_docker", "static_cap", "reactive_only", "full_hecf"]
    lines_out = []

    def log(s=""):
        print(s)
        lines_out.append(s)

    log("\n=== 1. DESCRIPTIVE STATISTICS (MEAN ± SD [95% CI]) ===")
    log(f"{'Mode':<16} | {'Energy (kWh)':<28} | {'Mean RT (ms)':<16} | {'P95 RT (ms)':<16} | {'ELP (kWh*ms)':<16} | {'Overhead (%)':<12}")
    log("-" * 116)
    for m in modes:
        blocks = sorted(data[m].keys())
        if not blocks:
            continue
        kwh_m, kwh_s, kwh_ci = ci95([data[m][b]["kwh"] for b in blocks])
        rt_m, rt_s, _ = ci95([data[m][b]["mean_rt"] for b in blocks])
        p95_m, p95_s, _ = ci95([data[m][b]["p95_rt"] for b in blocks])
        elp_m, elp_s, _ = ci95([data[m][b]["elp"] for b in blocks])
        oh_m, oh_s, _ = ci95([data[m][b]["oh"] for b in blocks])
        log(f"{m:<16} | {kwh_m:.6f} ± {kwh_s:.6f} (±{kwh_ci:.6f}) | {rt_m:6.1f} ± {rt_s:5.1f} | {p95_m:6.1f} ± {p95_s:5.1f} | {elp_m:8.5f} ± {elp_s:6.5f} | {oh_m:5.2f} ± {oh_s:4.2f}%")

    baselines = ["default_docker", "static_cap", "reactive_only"]
    common_blocks = sorted(set.intersection(*(set(data[m].keys()) for m in modes))) if all(data[m] for m in modes) else []

    if len(common_blocks) >= 2:
        log("\n=== 2. PAIRED WILCOXON + COHEN'S D + HOLM ADJUSTMENT (Container Energy kWh) ===")
        raw_ps, results = [], []
        hecf_kwh = [data["full_hecf"][b]["kwh"] for b in common_blocks]
        for base in baselines:
            base_kwh = [data[base][b]["kwh"] for b in common_blocks]
            w, p = wilcoxon_signed_rank_exact(hecf_kwh, base_kwh)
            d = cohens_d_paired(hecf_kwh, base_kwh)
            mean_base = mean(base_kwh)
            pct_diff = ((mean(hecf_kwh) - mean_base) / mean_base * 100.0) if mean_base > 0 else 0.0
            raw_ps.append(p)
            results.append((base, pct_diff, w, p, d))

        adj_ps = holm_adjust(raw_ps)
        for (base, pct_diff, w, p, d), p_holm in zip(results, adj_ps):
            log(f"full_hecf vs {base:<14}: ΔEnergy={pct_diff:+6.2f}% | W={w:4.1f} | p_raw={p:.4f} | p_Holm={p_holm:.4f} | Cohen's d={d:+.3f}")

        log("\n=== 3. GATE 2 VERIFICATION CHECKLIST (TAHAP B -> TAHAP B+) ===")
        hecf_oh = mean([data["full_hecf"][b]["oh"] for b in common_blocks])
        hecf_p95 = mean([data["full_hecf"][b]["p95_rt"] for b in common_blocks])
        hecf_rt = mean([data["full_hecf"][b]["mean_rt"] for b in common_blocks])
        reac_rt = mean([data["reactive_only"][b]["mean_rt"] for b in common_blocks])
        log(f"- Guardrail triggers across session : {total_gr} (Target >= 1)")
        log(f"- Tier 1 (Aggressive) triggers      : {total_t1} (Target >= 1)")
        log(f"- Micro-Freeze triggers             : {total_mf} (Target >= 1)")
        log(f"- HECF Overhead Mean                : {hecf_oh:.2f}% (Target < 5.0%)")
        log(f"- Total HTTP Failures               : {total_fails} (Target == 0)")
        log(f"- HECF P95 Latency                  : {hecf_p95:.1f} ms (Target < 500 ms)")
        log(f"- HECF vs Reactive Mean RT Ratio    : {(hecf_rt / reac_rt if reac_rt > 0 else 1.0):.3f}x (Target <= 1.05x)")

    # Write Markdown Report & Jupyter Notebook in session_dir
    report_path = os.path.join(session_dir, "statistical_report.md")
    with open(report_path, "w", encoding="utf-8") as rf:
        rf.write("# HECF Statistical & Gate Verification Report\n\n```text\n")
        rf.write("\n".join(lines_out))
        rf.write("\n```\n")

    nb_path = generate_rcbd_notebook(session_dir)
    print(f"\n[OK] Laporan Markdown tersimpan di : {report_path}")
    print(f"[OK] Jupyter Notebook tersimpan di : {nb_path}")


if __name__ == "__main__":
    main()
