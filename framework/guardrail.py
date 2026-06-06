# framework/guardrail.py
# Layer 3A: Real-time Guardrail
# Ref: Ahmad et al. (2025) — threshold-based rules; Xu & Buyya (2019) — brownout approach
# Ref: Lorido-Botran et al. (2014) — klasifikasi threshold-based sebagai teknik auto-scaling valid
#
# Mekanisme: evaluasi 5 sampel terakhir per container.
# Jika >= 3 dari 5 sampel melebihi threshold CPU>80% atau MEM>90%,
# guardrail aktif → hard CPU cap (brownout: throttle non-priority container).

from collections import defaultdict
from .config import (
    GUARDRAIL_CPU_THRESHOLD,
    GUARDRAIL_MEM_THRESHOLD,
    GUARDRAIL_WINDOW,
    GUARDRAIL_CONSECUTIVE,
)


class Guardrail:
    def __init__(self):
        # container_name → list of (cpu_percent, mem_percent)
        self._history: dict = defaultdict(list)

    def update(self, container_name: str, cpu: float, mem: float) -> bool:
        """
        Update riwayat dan periksa apakah guardrail perlu diaktifkan.

        Returns:
            True jika kondisi overload terpenuhi (guardrail aktif).
        """
        history = self._history[container_name]
        history.append((cpu, mem))

        # Pertahankan hanya GUARDRAIL_WINDOW sampel terakhir
        if len(history) > GUARDRAIL_WINDOW:
            history.pop(0)

        # Evaluasi dari sampel yang tersedia (minimal 1)
        recent = history[-GUARDRAIL_WINDOW:]
        cpu_over = sum(1 for c, _ in recent if c > GUARDRAIL_CPU_THRESHOLD)
        mem_over = sum(1 for _, m in recent if m > GUARDRAIL_MEM_THRESHOLD)

        # Aktif jika >= GUARDRAIL_CONSECUTIVE dari sampel melebihi threshold
        return cpu_over >= GUARDRAIL_CONSECUTIVE or mem_over >= GUARDRAIL_CONSECUTIVE

    def reset(self, container_name: str):
        """Reset riwayat container tertentu (misal setelah restart)."""
        self._history.pop(container_name, None)