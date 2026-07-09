import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.direction import Direction
from app.models.user import UserRole
from app.schemas.user import UserCreate
from app.services import user_service

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_credentials():
    credentials = {"username": "admin", "password": "adminpass123"}
    db = TestingSessionLocal()
    try:
        user_service.create_user(
            db,
            UserCreate(full_name="Admin Adminovich", role=UserRole.ADMIN, **credentials),
        )
    finally:
        db.close()
    return credentials


@pytest.fixture
def manager_credentials():
    credentials = {"username": "manager", "password": "managerpass1"}
    db = TestingSessionLocal()
    try:
        user_service.create_user(
            db,
            UserCreate(full_name="Маша Менеджер", role=UserRole.MANAGER, **credentials),
        )
    finally:
        db.close()
    return credentials


@pytest.fixture
def employee_credentials():
    credentials = {"username": "employee", "password": "employeepass1"}
    db = TestingSessionLocal()
    try:
        user_service.create_user(
            db,
            UserCreate(full_name="Олег Сотрудник", role=UserRole.EMPLOYEE, **credentials),
        )
    finally:
        db.close()
    return credentials


def _make_direction(name, short_code, color, sort_order):
    db = TestingSessionLocal()
    try:
        d = Direction(name=name, short_code=short_code, color=color, sort_order=sort_order)
        db.add(d)
        db.commit()
        db.refresh(d)
        db.expunge(d)
    finally:
        db.close()
    return d


@pytest.fixture
def direction():
    return _make_direction("Дизайн", "Дизайн", "pink", 0)


@pytest.fixture
def smi_direction():
    return _make_direction("СМИ", "СМИ", "orange", 1)
