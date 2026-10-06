#!/usr/bin/env python3
# experiments/diagnose_host.py
# READ-ONLY host capability check (tidak mengubah apa pun).
# Menentukan tuas optimasi energi mana yang tersedia di host eksperimen.

import os
import glob
import platform


def rd(p):
    try:
        with open(p) as f:
            return f.read().strip()
    except Exception as e:
        return f"<unreadable: {type(e).__name__}>"


def main():
    print("== Host ==")
    print("kernel:", platform.release(), "| euid:", os.geteuid())
    cpus = sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*"))
    print("logical CPUs:", len(cpus))
    print("virtualized (hypervisor flag):", "hypervisor" in rd("/proc/cpuinfo"))

    print("\n== Sensor energi (H1 butuh ini) ==")
    rapl = glob.glob("/sys/class/powercap/*rapl*/energy_uj")
    for p in rapl:
        print(p, "->", rd(p), "| max_range:", rd(os.path.join(os.path.dirname(p), "max_energy_range_uj")))
    if not rapl:
        print("RAPL: TIDAK ADA (VM/AMD lama?)")
    for p in glob.glob("/sys/class/hwmon/hwmon*/energy1_input"):
        print("hwmon energy:", p, rd(p))

    print("\n== DVFS (cpufreq) ==")
    c0 = "/sys/devices/system/cpu/cpu0/cpufreq"
    if os.path.isdir(c0):
        for k in ("scaling_driver", "scaling_governor", "scaling_available_governors",
                  "scaling_min_freq", "scaling_max_freq", "cpuinfo_max_freq"):
            print(k, "=", rd(os.path.join(c0, k)))
        print("writable governor:", os.access(os.path.join(c0, "scaling_governor"), os.W_OK))
    else:
        print("cpufreq: TIDAK ADA")

    print("\n== cgroup v2 ==")
    print("controllers:", rd("/sys/fs/cgroup/cgroup.controllers"))
    print("subtree_control:", rd("/sys/fs/cgroup/cgroup.subtree_control"))
    print("cpuset.cpus.effective:", rd("/sys/fs/cgroup/cpuset.cpus.effective"))

    print("\n== CPU hotplug ==")
    print("cpu1 online writable:", os.access("/sys/devices/system/cpu/cpu1/online", os.W_OK))

    print("\n== C-states ==")
    cs = glob.glob("/sys/devices/system/cpu/cpu0/cpuidle/state*/name")
    print([rd(p) for p in sorted(cs)] or "cpuidle: TIDAK ADA")


if __name__ == "__main__":
    main()
