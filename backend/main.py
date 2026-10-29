
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Load environment variables before importing database configuration.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from database import engine
from routes.auth import router as auth_router
from routes.protected import router as protected_router

app = FastAPI(
    title="Final Year Project API",
    description=(
        "FastAPI backend with JWT authentication, "
        "user management, PostgreSQL, and database migrations."
    ),
    version="1.0.0",
)

# Configure CORS using environment variables.
# Example: CORS_ORIGINS=http://localhost:3000,http://localhost:5173
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.get("/", tags=["General"])
def root():
    """Return basic API information."""
    return {
        "message": "Final Year Project API is running",
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Check whether the application can reach PostgreSQL."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected",
        }

    except SQLAlchemyError:
        return {
            "status": "unhealthy",
            "database": "unavailable",
        }


# Register authentication and user-management endpoints.
app.include_router(auth_router)
app.include_router(protected_router)
