import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import BaseCarrier, ShippingFlatRate, ShippingRateEntry, Shipment, User, ShipmentAttachment, Config, Invoice  # noqa: F401 — register models

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
def admin_user(db_session):
    user = User(
        username='admin_test',
        password_hash=hash_password('secret'),
        role='admin',
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def admin_client(client, admin_user):
    """TestClient with admin Authorization header pre-set."""
    token = create_access_token(subject=admin_user.username, role=admin_user.role)
    client.headers.update({'Authorization': f'Bearer {token}'})
    return client


@pytest.fixture
def regular_user(db_session):
    user = User(username='regular_test', role=None)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def regular_client(client, regular_user):
    token = create_access_token(subject=regular_user.username, role=regular_user.role)
    client.headers.update({'Authorization': f'Bearer {token}'})
    return client


@pytest.fixture
def shipment_type(db_session):
    from app.carriers.gls import GLSCarrier
    st = GLSCarrier(code='GLS', name='GLS Parcel', enabled=True)
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
        weight_kg='2.000',
        tracking_code='TRACK123',
    )
    db_session.add(s)
    db_session.flush()
    return s
