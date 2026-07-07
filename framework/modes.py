# framework/modes.py
# Mode Selector — Runtime-configurable operation modes
# Required by architecture.md §4 and prd.md §4.5
#
# Modes:
#   default_docker  — Observe only, no shaping (absolute baseline)
#   static_cap      — Fixed hard CPU cap (default 80%), no adaptive logic
#   reactive_only   — Only Layer 3A (Guardrail) active
#   full_hecf       — All 4 layers active (the proposed system)


class OperationMode:
    """
    Enum-style class for HECF operation modes.
    Used for baseline comparison in the thesis's experimental design.
    """
    DEFAULT_DOCKER = "default_docker"
    STATIC_CAP     = "static_cap"
    REACTIVE_ONLY  = "reactive_only"
    FULL_HECF      = "full_hecf"

    ALL_MODES = [DEFAULT_DOCKER, STATIC_CAP, REACTIVE_ONLY, FULL_HECF]

    @staticmethod
    def is_valid(mode: str) -> bool:
        """Check if a mode string is recognized."""
        return mode in OperationMode.ALL_MODES

    @staticmethod
    def is_shaping_enabled(mode: str) -> bool:
        """Returns True if the mode applies any resource shaping."""
        return mode != OperationMode.DEFAULT_DOCKER

    @staticmethod
    def is_tier_enabled(mode: str) -> bool:
        """Returns True if Tier Detection (Layer 3B) is active."""
        return mode == OperationMode.FULL_HECF

    @staticmethod
    def is_predictor_enabled(mode: str) -> bool:
        """Returns True if EMA Predictor (Layer 3C) is active."""
        return mode == OperationMode.FULL_HECF

    @staticmethod
    def is_guardrail_enabled(mode: str) -> bool:
        """Returns True if Guardrail (Layer 3A) is active."""
        return mode in [OperationMode.REACTIVE_ONLY, OperationMode.FULL_HECF]
