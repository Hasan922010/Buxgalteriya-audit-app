from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine, Base
from app.services.user_service import bootstrap_admin_if_needed
from app.api.v1.api import api_router
from app.db.seed import seed_database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuse to start with a missing / publicly known JWT signing key
    settings.assert_secure()

    # Startup: ensure tables & initial seed
    logger.info("Initializing database schema and seed data...")
    try:
        await seed_database()
        async with AsyncSessionLocal() as session:
            await bootstrap_admin_if_needed(session)
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error during startup database seed: {e}")
    yield
    # Shutdown
    logger.info("Shutting down database connection engine...")
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Uzbekistan Financial Accounting and Reporting Engine (BHMS / NAS, Didox EHF, Soliq.uz)",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Lets the SPA read download file names (exports are fetched with a bearer token)
    expose_headers=["Content-Disposition"],
)

# Mount API v1
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "db_port": settings.POSTGRES_PORT
    }

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Yordamchi Buxgalter AI backend tizimi muvaffaqiyatli ishga tushirildi.",
        "docs_url": "/docs",
        "version": "1.0.0"
    }
