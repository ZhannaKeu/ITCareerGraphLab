"""Run against migrated, imported PostgreSQL with RUN_POSTGRES_TESTS=1."""
import os
from pathlib import Path
import pytest
from sqlalchemy import text,select,func
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient
from app.db import SessionLocal
from app.main import app,calculate_batch
from app.models import Skill,SourceRecord,Prerequisite
from app.api.schemas import ExperimentRequest
from app.services.importer import import_dataset
from app.services.experiments import load_snapshot

pytestmark=pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS')!='1',reason='Enable with RUN_POSTGRES_TESTS=1 and a migrated/imported PostgreSQL database')


def test_postgres_vector_and_migration_head():
    with SessionLocal() as db:
        assert db.bind.dialect.name=='postgresql'
        assert db.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        assert db.scalar(text('SELECT version_num FROM alembic_version'))=='0004'
        assert db.scalar(select(func.count()).select_from(Skill))>=71


def test_real_postgres_idempotent_import():
    directory=Path(__file__).resolve().parents[2]/'datasets'
    with SessionLocal() as db:
        before=db.scalar(select(func.count()).select_from(SourceRecord))
        import_dataset(db,directory)
        assert db.scalar(select(func.count()).select_from(SourceRecord))==before
        assert len(calculate_batch(load_snapshot(db),ExperimentRequest(source_profile='backend:junior',target_profile='fullstack:middle')))==182


def test_postgres_foreign_keys_reject_bad_edge():
    with SessionLocal() as db:
        s=load_snapshot(db)
        db.add(Prerequisite(version_id=s.version.id,prerequisite_id='missing-node',skill_id='oop'))
        with pytest.raises(IntegrityError):db.flush()
        db.rollback()


def test_postgres_http_api():
    with TestClient(app) as client:
        assert client.get('/health/ready').status_code==200
        r=client.post('/api/experiments/compare',json={'source_profile':'backend:junior','target_profile':'fullstack:middle'})
        assert r.status_code==200,r.text
        assert r.json()['result']['M3']>=r.json()['result']['M2']
        assert not r.json()['provenance']['is_demo']


def test_postgres_revision_and_runs_in_outer_rollback():
    """Service commits stay inside savepoints; no test revision persists in user data."""
    from sqlalchemy.orm import Session
    from app.db import engine
    from app.api.schemas import RevisionRequest
    from app.services.versions import create_revision,metadata,history
    from app.services.experiments import execute_run
    from app.models import DatasetVersion,ExperimentRun
    child=None
    with engine.connect() as connection:
        transaction=connection.begin()
        try:
            with Session(bind=connection,join_transaction_mode='create_savepoint',expire_on_commit=False) as db:
                original=load_snapshot(db)
                child=create_revision(db,RevisionRequest(parent_id=original.version.id,label='Transactional test, rolled back',author='Automated isolated test',reason='Test copy-on-write and composite FKs without leaving user-data edits',changes=[{'entity':'requirement','key':['fullstack:middle','skill','sql'],'operation':'upsert','required_level':4}]))['version_id']
                assert metadata(db,child)['parent_id']==original.version.id
                assert len(history(db,child))==2
                request=ExperimentRequest(source_profile='backend:junior',target_profile='fullstack:middle')
                left=execute_run(db,load_snapshot(db,original.version.id),request)
                right=execute_run(db,load_snapshot(db,child),request)
                assert right['result']['M2']!=left['result']['M2']
                assert db.get(ExperimentRun,right['provenance']['run_id']).payload==right
        finally:
            transaction.rollback()
    with SessionLocal() as db:
        assert db.get(DatasetVersion,child) is None
