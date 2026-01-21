"""
Kubernetes manifest generation utilities.

This module provides functions to generate Kubernetes Pod and PVC manifests
for Ship containers.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from kubernetes_asyncio.client import (
    V1Container,
    V1ContainerPort,
    V1EnvVar,
    V1ObjectMeta,
    V1PersistentVolumeClaim,
    V1PersistentVolumeClaimSpec,
    V1Pod,
    V1PodSpec,
    V1ResourceRequirements,
    V1Volume,
    V1VolumeMount,
    V1PersistentVolumeClaimVolumeSource,
)

from app.config import settings


def build_pvc_manifest(
    ship_id: str,
    storage_size: Optional[str] = None,
    storage_class: Optional[str] = None,
) -> V1PersistentVolumeClaim:
    """
    Build a PVC manifest for a Ship container.

    Args:
        ship_id: The unique identifier for the ship
        storage_size: Size of the PVC (default: from settings.default_ship_disk)
        storage_class: Storage class to use (default: from settings)

    Returns:
        V1PersistentVolumeClaim: The PVC manifest
    """
    pvc_name = f"ship-{ship_id}"
    # Use provided storage_size, or fall back to default_ship_disk from settings
    raw_size = storage_size or settings.default_ship_disk
    # Normalize the disk size for Kubernetes (convert Docker-style to K8s-style units)
    size = normalize_disk_for_k8s(raw_size)
    sc = storage_class or settings.kube_storage_class

    return V1PersistentVolumeClaim(
        api_version="v1",
        kind="PersistentVolumeClaim",
        metadata=V1ObjectMeta(
            name=pvc_name,
            labels={
                "app": "ship",
                "ship_id": ship_id,
            },
        ),
        spec=V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=V1ResourceRequirements(
                requests={"storage": size},
            ),
            storage_class_name=sc if sc else None,
        ),
    )


from app.drivers.core.utils import (
    parse_memory_string,
    parse_disk_string,
    MIN_MEMORY_BYTES,
    MIN_DISK_BYTES,
)


# Mapping of Docker-style suffixes to K8s-style suffixes (lowercase keys)
_DOCKER_TO_K8S_SUFFIX = {
    "kb": "Ki",
    "k": "Ki",
    "mb": "Mi",
    "m": "Mi",  # Critical: Docker 'm' means MiB, K8s 'm' means milli-bytes!
    "gb": "Gi",
    "g": "Gi",
}


def _enforce_minimum_memory(memory: str) -> tuple[int, bool]:
    """
    Enforce minimum memory limit and return (bytes, was_clamped).

    Args:
        memory: Memory string to check

    Returns:
        Tuple of (safe_bytes, was_clamped) where was_clamped indicates
        if the value was increased to meet the minimum.
    """
    from app.drivers.core.utils import logger

    original_bytes = parse_memory_string(memory)
    if original_bytes < MIN_MEMORY_BYTES:
        logger.warning(
            "Requested memory '%s' (%d bytes) is below minimum 128 MiB. "
            "Automatically increased to 128 MiB.",
            memory,
            original_bytes,
        )
        return MIN_MEMORY_BYTES, True
    return original_bytes, False


def _normalize_unit_for_k8s(memory: str) -> str:
    """
    Normalize Docker-style units to K8s-style units without min enforcement.

    Args:
        memory: Memory string to normalize

    Returns:
        Normalized memory string with K8s-compatible units
    """
    mem = memory.strip()
    lower = mem.lower()

    # Already using K8s binary units (case-insensitive)
    if lower.endswith(("ki", "mi", "gi")):
        return mem

    # Convert Docker-style units to K8s binary units
    for suffix, k8s_suffix in _DOCKER_TO_K8S_SUFFIX.items():
        if lower.endswith(suffix):
            return mem[: -len(suffix)] + k8s_suffix

    # No recognized unit suffix, assume bytes - return as-is
    return mem


def normalize_memory_for_k8s(memory: str) -> str:
    """
    Normalize memory unit for Kubernetes.

    Converts Docker-style memory units (like '512m', '1g') to Kubernetes-style
    binary units (like '512Mi', '1Gi') to prevent the dangerous 'm' suffix
    issue in Kubernetes (where 'm' means milli-bytes, not megabytes).

    Also enforces a minimum memory limit of 128 MiB.

    Args:
        memory: Memory string to normalize

    Returns:
        Normalized memory string safe for Kubernetes

    Examples:
        >>> normalize_memory_for_k8s("512m")
        "512Mi"
        >>> normalize_memory_for_k8s("64Mi")  # Too small
        "134217728"  # 128 MiB in bytes
    """
    if not memory:
        return memory

    # Enforce minimum memory limit
    safe_bytes, was_clamped = _enforce_minimum_memory(memory)

    # If memory was increased to meet minimum, return the safe byte value
    if was_clamped:
        return str(safe_bytes)

    # Otherwise, normalize the unit for K8s
    return _normalize_unit_for_k8s(memory)


def _enforce_minimum_disk(disk: str) -> tuple[int, bool]:
    """
    Enforce minimum disk limit and return (bytes, was_clamped).

    Args:
        disk: Disk string to check

    Returns:
        Tuple of (safe_bytes, was_clamped) where was_clamped indicates
        if the value was increased to meet the minimum.
    """
    from app.drivers.core.utils import logger

    original_bytes = parse_disk_string(disk)
    if original_bytes < MIN_DISK_BYTES:
        logger.warning(
            "Requested disk '%s' (%d bytes) is below minimum 100 MiB. "
            "Automatically increased to 100 MiB.",
            disk,
            original_bytes,
        )
        return MIN_DISK_BYTES, True
    return original_bytes, False


def normalize_disk_for_k8s(disk: str) -> str:
    """
    Normalize disk/storage unit for Kubernetes.

    Converts Docker-style disk units (like '1g', '10G') to Kubernetes-style
    binary units (like '1Gi', '10Gi') to prevent the dangerous 'm' suffix
    issue in Kubernetes (where 'm' means milli-bytes, not megabytes).

    Also enforces a minimum disk limit of 100 MiB.

    Args:
        disk: Disk string to normalize

    Returns:
        Normalized disk string safe for Kubernetes

    Examples:
        >>> normalize_disk_for_k8s("1g")
        "1Gi"
        >>> normalize_disk_for_k8s("50Mi")  # Too small
        "104857600"  # 100 MiB in bytes
    """
    if not disk:
        return disk

    # Enforce minimum disk limit
    safe_bytes, was_clamped = _enforce_minimum_disk(disk)

    # If disk was increased to meet minimum, return the safe byte value
    if was_clamped:
        return str(safe_bytes)

    # Otherwise, normalize the unit for K8s
    return _normalize_unit_for_k8s(disk)


def build_pod_manifest(
    ship_id: str,
    image: str,
    cpus: Optional[float] = None,
    memory: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> V1Pod:
    """
    Build a Pod manifest for a Ship container.

    Args:
        ship_id: The unique identifier for the ship
        image: Container image to use
        cpus: CPU allocation (optional)
        memory: Memory allocation (optional, will be normalized for K8s)
        env: Additional environment variables (optional)

    Returns:
        V1Pod: The Pod manifest
    """
    # Normalize memory for Kubernetes
    normalized_memory = normalize_memory_for_k8s(memory) if memory else None

    pod_name = f"ship-{ship_id}"
    pvc_name = f"ship-{ship_id}"

    # Build resource requirements
    resources: Dict[str, Any] = {}
    if cpus is not None or normalized_memory is not None:
        requests: Dict[str, str] = {}
        limits: Dict[str, str] = {}

        if cpus is not None:
            cpu_str = str(cpus)
            requests["cpu"] = cpu_str
            limits["cpu"] = cpu_str

        if normalized_memory is not None:
            requests["memory"] = normalized_memory
            limits["memory"] = normalized_memory

        resources = V1ResourceRequirements(
            requests=requests,
            limits=limits,
        )

    # Build environment variables
    env_vars = [
        V1EnvVar(name="PORT", value=str(settings.ship_container_port)),
    ]
    if env:
        for key, value in env.items():
            env_vars.append(V1EnvVar(name=key, value=value))

    # Build container with volume mounts for persistence
    # /home - user workspaces (each user has /home/ship_xxx/workspace/)
    # /app/metadata - session/user mapping for restoration
    container = V1Container(
        name="ship",
        image=image,
        image_pull_policy=settings.kube_image_pull_policy,
        ports=[
            V1ContainerPort(container_port=settings.ship_container_port),
        ],
        env=env_vars,
        resources=resources if resources else None,
        volume_mounts=[
            V1VolumeMount(
                name="data",
                mount_path="/home",
                sub_path="home",  # PVC/home -> container /home
            ),
            V1VolumeMount(
                name="data",
                mount_path="/app/metadata",
                sub_path="metadata",  # PVC/metadata -> container /app/metadata
            ),
        ],
    )

    # Build pod
    return V1Pod(
        api_version="v1",
        kind="Pod",
        metadata=V1ObjectMeta(
            name=pod_name,
            labels={
                "app": "ship",
                "ship_id": ship_id,
            },
        ),
        spec=V1PodSpec(
            containers=[container],
            volumes=[
                V1Volume(
                    name="data",
                    persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(
                        claim_name=pvc_name,
                    ),
                ),
            ],
            restart_policy="Never",
        ),
    )


def get_pod_name(ship_id: str) -> str:
    """Get the Pod name for a ship ID."""
    return f"ship-{ship_id}"


def get_pvc_name(ship_id: str) -> str:
    """Get the PVC name for a ship ID."""
    return f"ship-{ship_id}"
