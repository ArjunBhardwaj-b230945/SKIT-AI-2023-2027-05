from dotenv import load_dotenv

# Load configuration before importing modules that read it.
load_dotenv()

from fastapi import FastAPI

from routes.auth import router as auth_router
from routes.protected import router as protected_router


app = FastAPI(
    title="Authentication and User Management API",
    description=(
        "Backend API for registration, authentication, "
        "user management and access control."
    ),
    version="1.1.0"
)


# Register application routers.
app.include_router(auth_router)
app.include_router(protected_router)


@app.get("/")
def home():
    return {
        "success": True,
        "message": "Backend API is running"
    }


@app.get("/health")
def health():
    return {
        "success": True,
        "status": "healthy"
    }