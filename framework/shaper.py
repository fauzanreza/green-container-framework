# framework/shaper.py
# Layer 4: Adaptive Resource Shaping
# Ref: Xu & Buyya (2019) — container-based resource control; Singh et al. (2021)
#
# Menerjemahkan keputusan Layer 3 menjadi perubahan cgroup parameter Docker.
# Menggunakan docker container.update() yang memodifikasi /sys/fs/cgroup/ secara langsung.
#
# PENTING: Memerlukan Docker socket mount dan privilege untuk docker update.

import docker
import logging
from .config import CPU_PERIOD, DRY_RUN

logger = logging.getLogger("hgcf.shaper")


def shape_container(
    container_name: str,
    cpu_quota: int,
    cpu_period: int = CPU_PERIOD,
    mem_limit: str = None,
    dry_run: bool = DRY_RUN,
) -> bool:
    """
    Terapkan limit CPU (dan opsional memori) ke container.

    Args:
        container_name: nama container Docker
        cpu_quota: microseconds per period. -1 = hapus limit (unlimited)
        cpu_period: period dalam microseconds (default 100ms)
        mem_limit: string misal "512m", "1g", atau None
        dry_run: jika True, hanya log — tidak benar-benar mengubah resource

    Returns:
        True jika berhasil (atau dry_run), False jika gagal
    """
    if dry_run:
        if cpu_quota == -1:
            logger.info("[DRY-RUN] %s: hapus CPU limit", container_name)
        else:
            cores = cpu_quota / cpu_period
            logger.info("[DRY-RUN] %s: set CPU=%.2f core (quota=%d)", container_name, cores, cpu_quota)
        return True

    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
    except docker.errors.NotFound:
        logger.warning("Container '%s' tidak ditemukan, skip shaping", container_name)
        return False

    kwargs = {}

    if cpu_quota == -1:
        # Hapus limit: set cpu_quota=0 untuk Rocky Linux/RHEL Docker
        # (beberapa versi Docker: -1 tidak valid, 0 = unlimited)
        kwargs["cpu_quota"] = 0
        kwargs["cpu_period"] = cpu_period
    else:
        kwargs["cpu_quota"] = int(cpu_quota)
        kwargs["cpu_period"] = int(cpu_period)

    if mem_limit is not None:
        kwargs["mem_limit"] = mem_limit

    try:
        container.update(**kwargs)
        if cpu_quota == -1 or cpu_quota == 0:
            logger.info("Shaped %s: CPU limit REMOVED", container_name)
        else:
            cores = cpu_quota / cpu_period
            logger.info("Shaped %s: CPU=%.2f core (quota=%d, period=%d)",
                        container_name, cores, cpu_quota, cpu_period)
        return True
    except docker.errors.APIError as e:
        logger.error("Gagal shape container '%s': %s", container_name, str(e))
        return False