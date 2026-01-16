"""
Ship service - compatibility module.

This module re-exports the ShipService from the new modular structure
for backward compatibility.
"""

from app.services.ship import ShipService, ship_service

__all__ = ["ShipService", "ship_service"]
