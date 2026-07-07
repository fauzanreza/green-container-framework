# framework/security/image_signer.py
# Layer 1 Extension: Pre-Runtime Security Gate — Trusted Image Signing
# Architecture §10.2, PRD §12.2
#
# Verifies container image digital signatures/digests against a trusted list
# before Layer 1 allows HECF to manage that container.
# Runs ONCE per container at cold start — deliberately kept out of the
# runtime polling loop to protect the <5% overhead budget.

import logging

logger = logging.getLogger("hecf.security.image_signer")


class ImageSigner:
    """
    Pre-runtime image verification gate.
    
    Checks container images against a trusted digest/signature list.
    Untrusted or unsigned images are flagged and optionally rejected.
    
    Overhead defense (prd.md §12.8): this runs once at cold start per container,
    not in the runtime monitoring loop — zero marginal cost to the steady-state
    <5% overhead budget.
    """

    def __init__(self, trusted_digests: list = None, required: bool = False):
        """
        Args:
            trusted_digests: List of trusted image digest prefixes (sha256:...).
                             If empty, all images are trusted (open gate).
            required: If True, untrusted images cause container rejection.
                      If False, untrusted images are flagged but allowed.
        """
        self._trusted_digests = trusted_digests or []
        self._required = required
        self._verified_cache = {}  # container_id -> bool (verified or not)

        if self._trusted_digests:
            logger.info(
                "Image signing gate ENABLED: %d trusted digests, required=%s",
                len(self._trusted_digests), self._required
            )
        else:
            logger.info("Image signing gate DISABLED (no trusted digests configured)")

    def verify_container(self, container_name: str, container_id: str,
                         image_id: str, image_attrs: dict = None) -> dict:
        """
        Verify a container's image against the trusted list.
        Called once per container at Layer 1 discovery (cold start).

        Args:
            container_name: Human-readable container name.
            container_id: Docker container long ID.
            image_id: Docker image ID or digest.
            image_attrs: Optional image metadata (RepoDigests, etc.)

        Returns:
            {"trusted": bool, "reason": str}
        """
        # Check cache first (already verified this container)
        if container_id in self._verified_cache:
            return self._verified_cache[container_id]

        # No trusted list configured → open gate
        if not self._trusted_digests:
            result = {"trusted": True, "reason": "no_signing_required"}
            self._verified_cache[container_id] = result
            return result

        # Check image digest against trusted list
        digests_to_check = []
        if image_id:
            digests_to_check.append(image_id)
        if image_attrs and "RepoDigests" in image_attrs:
            digests_to_check.extend(image_attrs["RepoDigests"])

        for digest in digests_to_check:
            for trusted in self._trusted_digests:
                if trusted in digest:
                    result = {"trusted": True, "reason": f"matched:{trusted[:16]}..."}
                    self._verified_cache[container_id] = result
                    logger.info(
                        "[TRUSTED] %s image verified against trusted digest",
                        container_name
                    )
                    return result

        # Not matched
        result = {"trusted": False, "reason": "no_matching_digest"}
        self._verified_cache[container_id] = result

        if self._required:
            logger.warning(
                "[REJECTED] %s image NOT in trusted list — container will be excluded",
                container_name
            )
        else:
            logger.warning(
                "[UNTRUSTED] %s image NOT in trusted list — flagged but allowed",
                container_name
            )

        return result

    def is_trusted(self, container_id: str) -> bool:
        """Quick check if a container was previously verified as trusted."""
        cached = self._verified_cache.get(container_id)
        if cached is None:
            return True  # Not yet checked → allow
        return cached["trusted"]

    @property
    def required(self) -> bool:
        return self._required
