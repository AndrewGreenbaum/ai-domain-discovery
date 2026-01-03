"""Main FastAPI application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from api.routes import router
from services.database import init_db
from utils.logger import logger
from config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("application_starting")

    try:
        # Initialize database
        await init_db()
        logger.info("database_ready")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("application_shutting_down")


# Create FastAPI app
app = FastAPI(
    title="AI Domain Discovery API",
    description="API for discovering and tracking new .ai domains",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware - allow Vercel and local development
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://carya-ai-domain-discovery-a9ni9k5ww.vercel.app",
]

# Also add any origins from settings
if settings.allowed_origins:
    for origin in settings.allowed_origins.split(","):
        origin = origin.strip()
        if origin and origin not in allowed_origins:
            allowed_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Allow all Vercel preview deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Root endpoint - Serve the dashboard"""
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {
        "service": "AI Domain Discovery",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "dashboard": "/static/dashboard.html"
    }


@app.get("/dashboard")
async def dashboard():
    """Dashboard page"""
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {"error": "Dashboard not found"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower()
    )
