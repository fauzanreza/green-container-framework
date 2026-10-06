#!/usr/bin/env python3
# experiments/analyze_results.py
# Analisis Statistik Hasil Eksperimen HECF (Design Science Research)
#
# Perbaikan P1/P2 dari laporan eksperimen:
#  - Energi = SUM energy_kwh (per interval) pada jendela steady-state, bukan max().
#  - Hanya container bench (nama dinormalisasi: "bench-json" == "benchjson").
#  - Sumbu waktu memakai kolom `time` asli, warm-up 5 menit dibuang.
#  - Uji statistik dipisah per workload x intensitas, Cohen's d bertanda, 95% CI.
#  - P95 tanpa fallback diam-diam ke Max.
#
# Usage: python analyze_results.py <session_dir> [--warmup-min 5]

import os
import glob
import argparse
import numpy as np
import pandas as pd
from scipy import stats

CONDITIONS = ("default_docker", "hecf_active")
SLA_P95_MS = 500.0

CSV_HEADER = [
    "time", "container_name", "cpu_percent", "mem_percent",
    "tier", "action", "power_watt", "energy_kwh",
    "ema_pred", "alpha", "spike_ratio", "p50", "p95",
    "overhead_cpu", "overhead_mem", "freeze_seconds",
]


def _read_locust(path):
    df = pd.read_csv(path)
    row = df[df["Name"] == "Aggregated"].iloc[0]
    if "95%" not in df.columns:
        raise KeyError(f"Kolom '95%' tidak ada di {path}")
    return {
        "Requests": row["Request Count"],
        "Failures": row["Failure Count"],
        "Avg_ms": row["Average Response Time"],
        "P95_ms": row["95%"],
        "Max_ms": row["Max Response Time"],
        "RPS": row["Requests/s"],
    }


def _read_server(path, warmup_min):
    """Return steady-state metrics of bench container only."""
    df = pd.read_csv(path)
    if "time" not in df.columns:  # file tanpa header
        df = pd.read_csv(path, names=CSV_HEADER, index_col=False)
    df["ts"] = pd.to_datetime(df["time"], errors="coerce")
    name = df["container_name"].astype(str).str.replace("-", "", regex=False).str.lower()
    df = df[name.str.startswith("bench") & df["ts"].notna()].copy()
    if df.empty:
        return None
    t0 = df["ts"].min() + pd.Timedelta(minutes=warmup_min)
    df = df[df["ts"] >= t0]
    if df.empty:
        return None
    for c in ("cpu_percent", "mem_percent", "power_watt", "energy_kwh",
              "overhead_cpu", "overhead_mem"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # Energi total per run: jumlahkan per-interval, lintas container bench.
    energy_kwh = df["energy_kwh"].sum()
    duration_s = max((df["ts"].max() - df["ts"].min()).total_seconds(), 1.0)
    return {
        "Energy_J": energy_kwh * 3.6e6,
        "Avg_power_W": df.groupby("ts")["power_watt"].sum().mean(),
        "CPU_mean": df["cpu_percent"].mean(),
        "CPU_peak": df["cpu_percent"].max(),
        "CPU_std": df["cpu_percent"].std(),
        "MEM_mean": df["mem_percent"].mean(),
        "Overhead_CPU": df["overhead_cpu"].mean(),
        "Overhead_MEM": df["overhead_mem"].mean(),
        "Steady_s": duration_s,
    }


def load(session_dir, warmup_min):
    rows = []
    for cond in CONDITIONS:
        for wl in ("json", "static", "db"):
            for it in ("low", "medium", "high", "spike"):
                for rep in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
                    d = os.path.join(session_dir, cond, wl, it, f"rep_{rep}")
                    loc = glob.glob(os.path.join(d, "*locust_stats.csv"))
                    if not loc:
                        continue
                    rec = dict(Condition=cond, Workload=wl, Intensity=it, Rep=rep)
                    rec.update(_read_locust(loc[0]))
                    srv = glob.glob(os.path.join(d, "*server_metrics.csv"))
                    if srv:
                        m = _read_server(srv[0], warmup_min)
                        if m:
                            rec.update(m)
                    rec["J_per_req"] = rec.get("Energy_J", np.nan) / max(rec["Requests"], 1)
                    rec["ELP"] = rec.get("Energy_J", np.nan) * rec["P95_ms"]
                    rows.append(rec)
    return pd.DataFrame(rows)


def cohens_d_paired(a, b):
    diff = np.asarray(a) - np.asarray(b)
    sd = np.std(diff, ddof=1)
    return float(np.mean(diff) / sd) if sd > 0 else 0.0


def paired_test(base, hecf, metric):
    base, hecf = np.asarray(base, float), np.asarray(hecf, float)
    n = len(base)
    if n < 3:
        return {"Metric": metric, "n": n, "error": "n<3"}
    diff = base - hecf
    if np.allclose(diff, diff[0]):
        p_norm, p_val, test = 1.0, 1.0, "identical"
    else:
        p_norm = stats.shapiro(diff).pvalue
        if p_norm > 0.05:
            p_val, test = stats.ttest_rel(base, hecf).pvalue, "paired t"
        else:
            p_val, test = stats.wilcoxon(base, hecf).pvalue, "Wilcoxon"
    se = stats.sem(diff) if n > 1 else np.nan
    ci = stats.t.interval(0.95, n - 1, loc=np.mean(diff), scale=se) if se > 0 else (np.nan, np.nan)
    return {
        "Metric": metric, "n": n, "Test": test, "p": p_val,
        "d (base-hecf, signed)": cohens_d_paired(base, hecf),
        "Mean base": base.mean(), "Mean HECF": hecf.mean(),
        "Diff 95% CI": f"[{ci[0]:.3g}, {ci[1]:.3g}]",
    }


def per_cell_stats(df, metrics):
    out = []
    for (wl, it), g in df.groupby(["Workload", "Intensity"]):
        b = g[g.Condition == "default_docker"].sort_values("Rep")
        h = g[g.Condition == "hecf_active"].sort_values("Rep")
        reps = sorted(set(b.Rep) & set(h.Rep))
        b, h = b[b.Rep.isin(reps)], h[h.Rep.isin(reps)]
        for m in metrics:
            if m in g and b[m].notna().all() and h[m].notna().all():
                r = paired_test(b[m], h[m], m)
                r.update(Workload=wl, Intensity=it)
                out.append(r)
    return pd.DataFrame(out)


def analyze(session_dir, warmup_min=5):
    df = load(session_dir, warmup_min)
    if df.empty:
        print("Tidak ada data.")
        return
    print(f"Loaded {len(df)} runs")
    summ = df.groupby(["Condition", "Workload", "Intensity"]).mean(numeric_only=True).drop(columns="Rep")
    print(summ[["RPS", "Avg_ms", "P95_ms", "Energy_J", "J_per_req", "CPU_peak"]].round(3).to_string())

    # Rasio HECF / default (pengganti 'Response Time Reduction %' yang menyesatkan)
    piv = summ.reset_index().pivot_table(index=["Workload", "Intensity"], columns="Condition")
    ratio = pd.DataFrame({
        "RPS ratio": piv["RPS"]["hecf_active"] / piv["RPS"]["default_docker"],
        "P95 ratio": piv["P95_ms"]["hecf_active"] / piv["P95_ms"]["default_docker"],
        "Energy ratio": piv["Energy_J"]["hecf_active"] / piv["Energy_J"]["default_docker"],
        "J/req ratio": piv["J_per_req"]["hecf_active"] / piv["J_per_req"]["default_docker"],
    })
    print("\nRasio HECF/Default (<1 energi/latensi = HECF lebih baik; RPS>=0.9 = OK):")
    print(ratio.round(3).to_string())

    print("\nUji per workload x intensitas (n = replikasi):")
    st = per_cell_stats(df, ["P95_ms", "Avg_ms", "RPS", "Energy_J", "J_per_req", "CPU_peak"])
    print(st.round(4).to_string(index=False))

    spike = summ.reset_index()
    spike = spike[(spike.Intensity == "spike") & (spike.Condition == "hecf_active")]
    ok = (spike["P95_ms"] < SLA_P95_MS).all()
    print(f"\nSLA P95<{SLA_P95_MS:.0f}ms pada Spike (HECF): {'LOLOS' if ok else 'GAGAL'}")

    out = os.path.join(session_dir, "analysis_runs.csv")
    df.to_csv(out, index=False)
    print(f"Saved: {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("session_dir")
    ap.add_argument("--warmup-min", type=float, default=5)
    a = ap.parse_args()
    analyze(a.session_dir, a.warmup_min)
