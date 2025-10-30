"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title="Spatial Intelligence Platform API",
    description="Mall visitor journey tracking and analytics platform",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "status": "online",
        "service": "Spatial Intelligence Platform API",
        "version": "0.1.0",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Import and include API routers
from app.api import api_router

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
