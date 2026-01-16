from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from app.config import settings
from app.database import db_service
from app.drivers import initialize_driver, close_driver
from app.services.status import status_checker
from app.routes import health, ships, stat

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Bay API service...")

    try:
        # Initialize database
        await db_service.initialize()
        await db_service.create_tables()
        logger.info("Database initialized")

        # Initialize container driver
        await initialize_driver(settings.container_driver)
        logger.info(f"Container driver initialized: {settings.container_driver}")

        # Start status checker
        await status_checker.start()
        logger.info("Status checker started")

        logger.info("Bay API service started successfully")

    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Bay API service...")

    # Stop status checker
    try:
        await status_checker.stop()
        logger.info("Status checker stopped")
    except Exception as e:
        logger.error(f"Error stopping status checker: {e}")

    # Close container driver
    try:
        await close_driver()
        logger.info("Container driver closed")
    except Exception as e:
        logger.error(f"Error closing container driver: {e}")


def create_app() -> FastAPI:
    """Create FastAPI application"""
    app = FastAPI(
        title="Bay API",
        description="Agent Sandbox Bay API Service",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router, tags=["health"])
    app.include_router(ships.router, tags=["ships"])
    app.include_router(stat.router, tags=["stat"])

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )
