# framework/hardware_sensor.py
# Layer 1 Extension: Hybrid Hardware Power Sensor
# Attempts to read real motherboard power (Intel RAPL / AMD hwmon).
# If blocked (e.g., inside a cloud VPS), it fails gracefully.

import os
import time
import logging

logger = logging.getLogger("hecf.hardware")

class PowerSensor:
    def __init__(self):
        self.sensor_path = self._detect_sensor()
        self.last_joules = None
        self.last_time = None
        self.available = self.sensor_path is not None

        if self.available:
            logger.info("[Hardware Sensor] DETECTED real power sensor at %s", self.sensor_path)
            # Initialize baseline reading
            self._read_joules()
        else:
            logger.warning("[Hardware Sensor] Blocked by virtualization or unavailable. Falling back to Software Estimation.")

    def _detect_sensor(self) -> str:
        """Detects if a hardware power sensor is readable."""
        # 1. Intel RAPL
        rapl_path = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
        if os.path.exists(rapl_path) and os.access(rapl_path, os.R_OK):
            return rapl_path
        
        # 2. AMD Energy (often in hwmon)
        # Search for energy1_input in hwmon directories
        try:
            hwmon_base = "/sys/class/hwmon/"
            if os.path.exists(hwmon_base):
                for hwmon in os.listdir(hwmon_base):
                    path = os.path.join(hwmon_base, hwmon, "energy1_input")
                    if os.path.exists(path) and os.access(path, os.R_OK):
                        return path
        except Exception:
            pass
            
        return None

    def _read_joules(self) -> float:
        """Reads the raw energy counter in Joules."""
        if not self.sensor_path:
            return 0.0
            
        try:
            with open(self.sensor_path, "r") as f:
                # Raw value is in microjoules (uj)
                microjoules = int(f.read().strip())
                joules = microjoules / 1_000_000.0
                
                now = time.time()
                
                # First read or counter wrap-around protection
                if self.last_joules is None or joules < self.last_joules:
                    self.last_joules = joules
                    self.last_time = now
                    return 0.0
                    
                delta_j = joules - self.last_joules
                delta_t = now - self.last_time
                
                self.last_joules = joules
                self.last_time = now
                
                if delta_t > 0:
                    return delta_j / delta_t
                return 0.0
        except Exception as e:
            logger.error("Failed to read hardware sensor: %s", str(e))
            self.available = False
            return 0.0

    def get_power_watts(self) -> float:
        """Returns the average Watts consumed since the last call."""
        if not self.available:
            return None
            
        watts = self._read_joules()
        return round(watts, 3)
