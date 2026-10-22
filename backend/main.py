
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from database import Base, engine
from models.user import User  # Registers the User model with SQLAlchemy
from routes.auth import router as auth_router
from routes.protected import router as protected_router

app = FastAPI(
    title="User Authentication and Management API",
    description="FastAPI backend with JWT authentication and PostgreSQL.",
    version="1.1.0",
)


@app.on_event("startup")
def create_database_tables():
    Base.metadata.create_all(bind=engine)


app.include_router(auth_router)
app.include_router(protected_router)


@app.get("/")
def health_check():
    return {"message": "API is running"}
