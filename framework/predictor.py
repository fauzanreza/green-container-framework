# framework/predictor.py
# Layer 3C: Lightweight Prediction Engine — AFMV
# Ref: Hossain et al. (2022) — Adaptive Filter-based Moving Average (AFMV)
#
# Formula dari paper (Section 3.2.4, Equation 16):
#   Y(k) = (1 - α) × MV_w(k-1) + α × u(k)
#
# Di mana:
#   MV_w(k-1) = moving average dari w sampel terakhir (bukan EMA sederhana!)
#   u(k)      = nilai CPU aktual terbaru
#   α         = ditentukan heuristik dari STDEV window (Section 3.2.4 paper):
#               "with a higher STDEV, more weight is given on recent profiled information"
#
# Ini BERBEDA dari plain EMA: Y_EMA = α×u + (1-α)×Y_prev
# AFMV menggunakan moving average sebagai "past estimated value", bukan nilai prediksi sebelumnya.

import numpy as np
from collections import defaultdict
from .config import AFMV_WINDOW_SIZE, AFMV_ALPHA_MIN, AFMV_ALPHA_MAX, AFMV_STDEV_SCALE


class AFMVPredictor:
    def __init__(self):
        # container_name → list of actual CPU samples
        self._samples: dict = defaultdict(list)
        # container_name → last AFMV prediction
        self._predictions: dict = defaultdict(float)

    def update(self, container_name: str, cpu: float) -> float:
        """
        Update AFMV dengan nilai CPU baru dan kembalikan prediksi berikutnya.

        Implementasi persis Algorithm 3 dari Hossain et al. (2022):
        1. Tambah sampel ke window
        2. Hitung MV_w dari w sampel terakhir
        3. Hitung α dari STDEV window
        4. Y(k) = (1-α) × MV_w + α × u(k)
        """
        samples = self._samples[container_name]
        samples.append(cpu)

        # Pertahankan hanya data yang relevan (2× window agar STDEV stabil)
        max_keep = AFMV_WINDOW_SIZE * 4
        if len(samples) > max_keep:
            samples.pop(0)

        # Hitung Moving Average dari w sampel terakhir (MV_w)
        recent_w = samples[-AFMV_WINDOW_SIZE:]
        mv_w = float(np.mean(recent_w))

        # Hitung alpha dari STDEV window (heuristik Hossain et al.)
        # STDEV tinggi → alpha besar (lebih percaya data terbaru)
        # STDEV rendah → alpha kecil (lebih percaya moving average)
        if len(recent_w) >= 2:
            stdev = float(np.std(recent_w))
            alpha = np.clip(stdev / AFMV_STDEV_SCALE, AFMV_ALPHA_MIN, AFMV_ALPHA_MAX)
        else:
            alpha = AFMV_ALPHA_MIN

        # AFMV Formula: Y(k) = (1-α) × MV_w(k-1) + α × u(k)
        prediction = (1 - alpha) * mv_w + alpha * cpu
        self._predictions[container_name] = prediction

        return round(prediction, 2)

    def get_prediction(self, container_name: str) -> float:
        """Return prediksi terakhir tanpa update."""
        return round(self._predictions[container_name], 2)

    def get_alpha(self, container_name: str) -> float:
        """Return alpha yang sedang digunakan (untuk logging)."""
        samples = self._samples[container_name]
        recent_w = samples[-AFMV_WINDOW_SIZE:]
        if len(recent_w) >= 2:
            stdev = float(np.std(recent_w))
            return round(float(np.clip(stdev / AFMV_STDEV_SCALE, AFMV_ALPHA_MIN, AFMV_ALPHA_MAX)), 4)
        return AFMV_ALPHA_MIN