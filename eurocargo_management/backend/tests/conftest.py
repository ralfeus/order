import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app
from app.models import ShipmentType, Shipment, User, Payment  # noqa: F401 — register models

DATABASE_URL = 'sqlite://'  # in-memory SQLite for tests


@pytest.fixture(scope='session')
def engine():
    return create_engine(DATABASE_URL, connect_args={'check_same_thread': False})


@pytest.fixture(scope='session')
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(engine, tables):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def shipment_type(db_session):
    st = ShipmentType(code='GLX', name='Galaxus', enabled=True)
    db_session.add(st)
    db_session.flush()
    return st


@pytest.fixture
def shipment(db_session, shipment_type):
    s = Shipment(
        order_id='ORD-2026-04-0001',
        customer_name='Jane Doe',
        email='jane@example.com',
        address='123 Main St',
        city='Prague',
        country='CZ',
        zip='11000',
        phone='+420123456789',
        shipment_type_id=shipment_type.id,
        tracking_code='TRACK123',
        amount_eur='12.50',
    )
    db_session.add(s)
    db_session.flush()
    return s
