"""
Kubernetes container driver package.

This package provides a Kubernetes-based container driver for running
Ship containers as Kubernetes Pods with PVC storage.
"""

from app.drivers.kubernetes.driver import KubernetesDriver

__all__ = ["KubernetesDriver"]
