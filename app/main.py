"""Main FastAPI application for Project Hermes."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app import __version__
from app.api.routes import admin, areas, health, routes
from app.config import settings
from app.exceptions import (
    GraphNotFoundError,
    HermesException,
    InvalidAreaError,
    NoValidPathError,
    RouteNotFoundError
)
from app.utils.logger import setup_logging

# Setup logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Intelligent hiking route planning system with multi-day planning and equipment recommendations",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(RouteNotFoundError)
async def route_not_found_handler(request: Request, exc: RouteNotFoundError):
    """Handle RouteNotFoundError exceptions."""
    return JSONResponse(
        status_code=404,
        content={"error": "Route not found", "detail": str(exc)}
    )


@app.exception_handler(InvalidAreaError)
async def invalid_area_handler(request: Request, exc: InvalidAreaError):
    """Handle InvalidAreaError exceptions."""
    return JSONResponse(
        status_code=404,
        content={"error": "Invalid area", "detail": str(exc)}
    )


@app.exception_handler(GraphNotFoundError)
async def graph_not_found_handler(request: Request, exc: GraphNotFoundError):
    """Handle GraphNotFoundError exceptions."""
    return JSONResponse(
        status_code=404,
        content={"error": "Graph not found", "detail": str(exc)}
    )


@app.exception_handler(NoValidPathError)
async def no_valid_path_handler(request: Request, exc: NoValidPathError):
    """Handle NoValidPathError exceptions."""
    return JSONResponse(
        status_code=400,
        content={"error": "No valid path found", "detail": str(exc)}
    )


@app.exception_handler(HermesException)
async def hermes_exception_handler(request: Request, exc: HermesException):
    """Handle general Hermes exceptions."""
    return JSONResponse(
        status_code=400,
        content={"error": "Request error", "detail": str(exc)}
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info(f"Starting {settings.app_name} v{__version__}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Data directory: {settings.data_dir}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info(f"Shutting down {settings.app_name}")


# Include routers
app.include_router(health.router, prefix="")
app.include_router(areas.router, prefix="/api/v1")
app.include_router(routes.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": __version__,
        "description": "Intelligent hiking route planning system",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
