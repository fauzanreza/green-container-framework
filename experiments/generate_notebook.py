import os
import json

def create_analysis_notebook(session_dir):
    notebook_content = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# 📊 HECF Experiment Analysis\n",
                    "Notebook ini digenerate secara otomatis untuk merangkum hasil eksperimen (72 cases) dari sesi ini.\n",
                    "Jalankan cell di bawah untuk melihat rekapitulasi data dan grafik perbandingan."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "import os\n",
                    "import glob\n",
                    "import pandas as pd\n",
                    "import matplotlib.pyplot as plt\n",
                    "import seaborn as sns\n",
                    "\n",
                    "# Konfigurasi visualisasi\n",
                    "sns.set_theme(style=\"whitegrid\")\n",
                    "plt.rcParams['figure.figsize'] = (10, 6)"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 1. Load Data\n",
                    "Mengumpulkan semua file `_locust_stats.csv` dan merata-ratakan hasil dari 3 replikasi (rep_1, rep_2, rep_3)."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "data_list = []\n",
                    "base_dir = '.'\n",
                    "\n",
                    "for condition in ['default_docker', 'hecf_active']:\n",
                    "    for workload in ['json', 'static', 'db']:\n",
                    "        for intensity in ['low', 'medium', 'high', 'spike']:\n",
                    "            for rep in [1, 2, 3]:\n",
                    "                # Cari file locust stats\n",
                    "                search_path = os.path.join(base_dir, condition, workload, intensity, f\"rep_{rep}\", \"*locust_stats.csv\")\n",
                    "                files = glob.glob(search_path)\n",
                    "                if not files:\n",
                    "                    continue\n",
                    "                \n",
                    "                # Baca row Aggregated (baris terakhir)\n",
                    "                try:\n",
                    "                    df = pd.read_csv(files[0])\n",
                    "                    agg_row = df[df['Name'] == 'Aggregated'].iloc[0]\n",
                    "                    \n",
                    "                    data_list.append({\n",
                    "                        'Condition': condition,\n",
                    "                        'Workload': workload,\n",
                    "                        'Intensity': intensity.capitalize(),\n",
                    "                        'Rep': rep,\n",
                    "                        'Requests': agg_row['Request Count'],\n",
                    "                        'Failures': agg_row['Failure Count'],\n",
                    "                        'Median Response Time': agg_row['Median Response Time'],\n",
                    "                        'Average Response Time': agg_row['Average Response Time'],\n",
                    "                        'Max Response Time': agg_row['Max Response Time'],\n",
                    "                        'Requests/s': agg_row['Requests/s']\n",
                    "                    })\n",
                    "                except Exception as e:\n",
                    "                    print(f\"Error reading {files[0]}: {e}\")\n",
                    "\n",
                    "df_all = pd.DataFrame(data_list)\n",
                    "print(f\"Berhasil meload {len(df_all)} file CSV.\")"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 2. Summary Table (Rata-rata 3 Replikasi)"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Kelompokkan berdasarkan Condition, Workload, dan Intensity, lalu hitung mean\n",
                    "summary_df = df_all.groupby(['Condition', 'Workload', 'Intensity']).mean(numeric_only=True).reset_index()\n",
                    "summary_df.drop(columns=['Rep'], inplace=True)\n",
                    "\n",
                    "# Tampilkan tabel (bisa dicopy ke Excel)\n",
                    "display(summary_df)"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 3. Visualisasi: Average Response Time"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "sns.catplot(\n",
                    "    data=summary_df, kind=\"bar\",\n",
                    "    x=\"Intensity\", y=\"Average Response Time\", hue=\"Condition\", col=\"Workload\",\n",
                    "    order=['Low', 'Medium', 'High', 'Spike'],\n",
                    "    palette=\"muted\", height=5, aspect=0.8\n",
                    ")\n",
                    "plt.suptitle('Average Response Time Comparison', y=1.05)\n",
                    "plt.show()"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 4. Visualisasi: Requests per Second (Throughput)"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "sns.catplot(\n",
                    "    data=summary_df, kind=\"bar\",\n",
                    "    x=\"Intensity\", y=\"Requests/s\", hue=\"Condition\", col=\"Workload\",\n",
                    "    order=['Low', 'Medium', 'High', 'Spike'],\n",
                    "    palette=\"viridis\", height=5, aspect=0.8\n",
                    ")\n",
                    "plt.suptitle('Requests per Second (Throughput) Comparison', y=1.05)\n",
                    "plt.show()"
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.10.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }

    file_path = os.path.join(session_dir, "analysis_summary.ipynb")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(notebook_content, f, indent=2)
    
    print(f"✅ Notebook berhasil dibuat di: {file_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        create_analysis_notebook(sys.argv[1])
    else:
        print("Usage: python generate_notebook.py <session_dir>")
