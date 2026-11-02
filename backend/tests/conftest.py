from pathlib import Path
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.services.importer import import_dataset

DATASETS=Path(__file__).resolve().parents[2]/'datasets'

@pytest.fixture
def dataset_dir():
    return DATASETS

@pytest.fixture
def session(dataset_dir):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    @event.listens_for(engine,'connect')
    def fk(conn,_):
        conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as session:
        import_dataset(session,dataset_dir)
        yield session
    engine.dispose()
