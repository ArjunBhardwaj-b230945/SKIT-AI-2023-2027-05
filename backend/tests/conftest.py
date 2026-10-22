
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from main import app
from database import Base, SessionLocal, engine
from models.user import User


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.execute(delete(User))
        db.commit()

    with TestClient(app) as test_client:
        yield test_client

    with SessionLocal() as db:
        db.execute(delete(User))
        db.commit()
