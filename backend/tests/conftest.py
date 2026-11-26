import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from main import app
from database import Base, SessionLocal, engine
from models.user import User
from models.tax_record import TaxRecord
from models.chat import ChatMessageModel
from models.tax_profile import TaxProfileModel
from models.audit_log import AuditLogModel
from models.itr_filing import ITRFilingModel


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.execute(delete(AuditLogModel))
        db.execute(delete(ChatMessageModel))
        db.execute(delete(ITRFilingModel))
        db.execute(delete(TaxProfileModel))
        db.execute(delete(TaxRecord))
        db.execute(delete(User))
        db.commit()

    with TestClient(app) as test_client:
        yield test_client

    with SessionLocal() as db:
        db.execute(delete(AuditLogModel))
        db.execute(delete(ChatMessageModel))
        db.execute(delete(ITRFilingModel))
        db.execute(delete(TaxProfileModel))
        db.execute(delete(TaxRecord))
        db.execute(delete(User))
        db.commit()
