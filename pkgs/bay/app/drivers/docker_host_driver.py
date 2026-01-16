"""
Docker Host container driver implementation.

This module implements the ContainerDriver interface for running Bay on the host
machine (not inside a Docker container). It uses port mapping to communicate
with Ship containers instead of Docker network internal IPs.
"""

import os
import aiodocker
from aiodocker.exceptions import DockerError
from typing import Optional, Dict, Any
import logging

from app.config import settings
from app.models import Ship, ShipSpec
from app.drivers.base import ContainerDriver, ContainerInfo

logger = logging.getLogger(__name__)


class DockerHostDriver(ContainerDriver):
    """
    Docker driver for host-mode Bay deployment.
    
    This driver is designed for when Bay runs directly on the host machine
    (not inside a Docker container). It uses localhost and mapped ports
    to communicate with Ship containers instead of Docker network IPs.
    
    Use this driver when:
    - Bay is running directly on the host (e.g., `python run.py`)
    - Bay cannot access Docker's internal network IPs
    
    Configuration:
    - Set CONTAINER_DRIVER=docker-host
    """
    
    def __init__(self):
        self.client: Optional[aiodocker.Docker] = None
    
    async def initialize(self) -> None:
        """Initialize Docker client."""
        try:
            self.client = aiodocker.Docker()
            # Test connection
            await self.client.version()
            logger.info("Docker Host driver initialized successfully")
        except DockerError as e:
            logger.error(f"Failed to initialize Docker Host driver: {e}")
            raise
    
    async def close(self) -> None:
        """Close Docker client."""
        if self.client:
            await self.client.close()
    
    async def create_ship_container(
        self, ship: Ship, spec: Optional[ShipSpec] = None
    ) -> ContainerInfo:
        """
        Create and start a ship container using Docker.
        
        Unlike DockerDriver, this returns localhost:mapped_port as the IP address
        so that Bay running on the host can communicate with the container.
        """
        if not self.client:
            await self.initialize()
        
        assert self.client is not None  # For type checker
        
        container_config = self._build_container_config(ship, spec)
        
        try:
            # Create container
            container = await self.client.containers.create_or_replace(
                name=container_config["name"], config=container_config["config"]
            )
            
            # Start container
            await container.start()
            
            # Get container info (need to refresh after start to get port mappings)
            container_info = await container.show()
            
            # Get the mapped host port for 8123
            # In host mode, we use localhost:mapped_port instead of container IP
            ip_address = None
            network_settings = container_info.get("NetworkSettings", {})
            ports = network_settings.get("Ports", {})
            
            if "8123/tcp" in ports and ports["8123/tcp"]:
                host_port = ports["8123/tcp"][0].get("HostPort")
                if host_port:
                    # Use localhost with the mapped port
                    ip_address = f"127.0.0.1:{host_port}"
                    logger.info(f"Ship {ship.id} accessible at {ip_address}")
            
            if not ip_address:
                logger.warning(
                    f"Could not get port mapping for ship {ship.id}, "
                    "falling back to container IP"
                )
                # Fallback to container IP (might not work on host)
                if (
                    settings.docker_network
                    and settings.docker_network in network_settings.get("Networks", {})
                ):
                    ip_address = network_settings["Networks"][settings.docker_network].get(
                        "IPAddress"
                    )
                else:
                    ip_address = network_settings.get("IPAddress")
            
            return ContainerInfo(
                container_id=container.id,
                ip_address=ip_address,
                status=container_info.get("State", {}).get("Status", "unknown"),
            )
        
        except DockerError as e:
            logger.error(f"Failed to create container for ship {ship.id}: {e}")
            raise
    
    async def stop_ship_container(self, container_id: str) -> bool:
        """Stop and remove ship container."""
        if not self.client:
            await self.initialize()
        
        assert self.client is not None  # For type checker
        
        try:
            # Get container
            container = await self.client.containers.get(container_id)
            
            # Stop container
            await container.stop()
            
            # Remove container
            await container.delete()
            
            return True
        
        except DockerError as e:
            if "No such container" in str(e):
                logger.warning(f"Container {container_id} not found")
                return True  # Already removed
            logger.error(f"Failed to stop container {container_id}: {e}")
            return False
    
    def ship_data_exists(self, ship_id: str) -> bool:
        """Check if ship data directory exists."""
        ship_data_dir = os.path.expanduser(f"{settings.ship_data_dir}/{ship_id}")
        home_dir = f"{ship_data_dir}/home"
        metadata_dir = f"{ship_data_dir}/metadata"
        
        # Check if both directories exist
        return os.path.exists(home_dir) and os.path.exists(metadata_dir)
    
    async def get_container_logs(self, container_id: str) -> str:
        """Get container logs."""
        if not self.client:
            await self.initialize()
        
        assert self.client is not None  # For type checker
        
        try:
            # Get container
            container = await self.client.containers.get(container_id)
            
            # Get logs
            logs_stream = await container.log(stdout=True, stderr=True)
            logs = "".join([line for line in logs_stream])
            
            return logs
        
        except DockerError as e:
            if "No such container" in str(e):
                logger.warning(f"Container {container_id} not found")
                return ""
            logger.error(f"Failed to get logs for container {container_id}: {e}")
            return ""
    
    async def is_container_running(self, container_id: str) -> bool:
        """Check if container is running."""
        if not self.client:
            await self.initialize()
        
        assert self.client is not None  # For type checker
        
        try:
            # Get container
            container = await self.client.containers.get(container_id)
            
            # Get container info
            container_info = await container.show()
            return container_info.get("State", {}).get("Status") == "running"
        
        except DockerError as e:
            if "No such container" in str(e):
                return False
            logger.error(f"Failed to check container {container_id} status: {e}")
            return False
    
    def _build_container_config(
        self, ship: Ship, spec: Optional[ShipSpec] = None
    ) -> Dict[str, Any]:
        """Build container configuration for aiodocker."""
        # Prepare host paths for volume mounts
        ship_data_dir = os.path.expanduser(f"{settings.ship_data_dir}/{ship.id}")
        home_dir = f"{ship_data_dir}/home"
        metadata_dir = f"{ship_data_dir}/metadata"
        
        # Create directories if they don't exist
        os.makedirs(home_dir, exist_ok=True)
        os.makedirs(metadata_dir, exist_ok=True)
        
        # Set permissions to allow container to manage users and directories
        try:
            os.chmod(home_dir, 0o777)
            os.chmod(metadata_dir, 0o777)
        except Exception as e:
            logger.error(
                f"Failed to set permissions for ship {ship.id} directories: {e}"
            )
            raise
        
        # Host configuration for resource limits
        # For host mode, we MUST have port binding to access the container
        host_config: Dict[str, Any] = {
            "RestartPolicy": {"Name": "no"},
            "PortBindings": {
                "8123/tcp": [{"HostPort": ""}]  # Let Docker assign random port
            },
            "Binds": [
                f"{home_dir}:/home",
                f"{metadata_dir}:/app/metadata",
            ],
        }
        
        # Apply spec if provided
        if spec:
            if spec.cpus:
                host_config["CpuQuota"] = int(spec.cpus * 100000)
                host_config["CpuPeriod"] = 100000
            
            if spec.memory:
                host_config["Memory"] = self._parse_memory_string(spec.memory)
        
        # Container configuration
        config: Dict[str, Any] = {
            "Image": settings.docker_image,
            "Env": [f"SHIP_ID={ship.id}", f"TTL={ship.ttl}"],
            "Labels": {"ship_id": ship.id, "created_by": "bay"},
            "ExposedPorts": {"8123/tcp": {}},
            "HostConfig": host_config,
        }
        
        # Add network if configured (still useful for container-to-container communication)
        if settings.docker_network:
            config["NetworkingConfig"] = {
                "EndpointsConfig": {settings.docker_network: {}}
            }
        
        return {"name": f"ship-{ship.id}", "config": config}
    
    def _parse_memory_string(self, memory_str: str) -> int:
        """Parse memory string (e.g., '512m', '1g') to bytes."""
        memory_str = memory_str.lower().strip()
        
        if memory_str.endswith("k") or memory_str.endswith("kb"):
            return (
                int(memory_str[:-1] if memory_str.endswith("k") else memory_str[:-2])
                * 1024
            )
        elif memory_str.endswith("m") or memory_str.endswith("mb"):
            return (
                int(memory_str[:-1] if memory_str.endswith("m") else memory_str[:-2])
                * 1024
                * 1024
            )
        elif memory_str.endswith("g") or memory_str.endswith("gb"):
            return (
                int(memory_str[:-1] if memory_str.endswith("g") else memory_str[:-2])
                * 1024
                * 1024
                * 1024
            )
        else:
            # Assume bytes if no suffix
            return int(memory_str)
