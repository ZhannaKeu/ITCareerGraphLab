"""Isolated complete-protocol tests; no server or external database."""
import csv
import io
import json
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models import ExperimentRun
from app.api.schemas import Experiment2Request, ExperimentRequest
from app.services.importer import import_dataset
from app.services.experiments import load_snapshot, execute_run
from app.services.experiment2 import execute_experiment2, export_file, TAUS, LAMBDAS
from conftest import DATASETS

@pytest.fixture(scope='module')
def study():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        import_dataset(db, DATASETS)
        snapshot = load_snapshot(db)
        old = execute_run(db, snapshot, ExperimentRequest(source_profile='backend:junior', target_profile='fullstack:middle', version_id=snapshot.version.id), 'batch')
        archived = json.dumps(old, sort_keys=True)
        payload = execute_experiment2(db, snapshot)
        yield db, snapshot, payload, old, archived
    engine.dispose()

def test_fixed_sixty_scenarios_all_pairs_and_invariants(study):
    db, snapshot, run, _, _ = study
    assert run['scenario_count'] == len(run['scenarios']) == 60
    assert {(s['graph'], s['tau'], s['lambda']) for s in run['scenarios']} == {(g,t,l) for g in ('G1','G2','G3') for t in TAUS for l in LAMBDAS}
    baseline = {(r['source_profile'],r['target_profile']):r['M2'] for r in run['scenarios'][0]['results']}
    assert len(baseline) == 182
    for s in run['scenarios']:
        assert len(s['results']) == 182
        assert {(r['source_profile'],r['target_profile']):r['M2'] for r in s['results']} == baseline
        assert all(r['M3'] >= r['M2'] for r in s['results'])
        if s['lambda'] == 0:
            assert all(r['M3'] == r['M2'] for r in s['results'])
            assert s['metrics']['mean_extra'] == 0
            assert s['metrics']['top3_replaced_targets'] == s['metrics']['top5_replaced_targets'] == 0
        stored = db.get(ExperimentRun,s['scenario_run_id']).payload
        params = stored['provenance']['parameters']
        assert params['algorithm'] == 'kahn'
        assert params['weight_source'] == 'skill_weights_by_role_final_v2.csv'
        assert params['verification_scope'] == 'all'
        assert params['included_edges'] == params['excluded_edges'] == []
        assert stored['provenance']['dataset'] == snapshot.version.id
        assert s['configuration_hash'] == run['configurations'][s['graph']]['configuration_hash']
        for name in ('mean_spearman','mean_kendall_tau_b'):
            value = s['metrics'][name]
            assert value is None or -1.00000001 <= value <= 1.00000001
    assert len(run['rankings']) == len(run['graph_rankings']) == 840
    assert len(run['graph_comparisons']) == 60

def test_replay_and_old_experiments_unchanged(study):
    db,snapshot,run,old,archived = study
    assert execute_experiment2(db,snapshot) == run
    assert json.dumps(db.get(ExperimentRun,old['provenance']['run_id']).payload,sort_keys=True) == archived
    # Fresh calculation from the established engine, independent of saved batches.
    second_engine = create_engine('sqlite://')
    Base.metadata.create_all(second_engine)
    with Session(second_engine) as second:
        import_dataset(second,DATASETS)
        replay = execute_experiment2(second,load_snapshot(second))
        assert replay == run
    second_engine.dispose()

@pytest.mark.parametrize('name,count', [('summary',60),('scenarios',10920),('rankings',21840)])
def test_csv_exports_complete_and_provenanced(study,name,count):
    run = study[2]
    text,media = export_file(run,f'experiment2-{name}.csv')
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == count and media.startswith('text/csv')
    assert all(r['experiment_run_id'] == run['provenance']['run_id'] for r in rows)
    assert all(r['dataset_version'] == run['provenance']['dataset'] and len(r['source_data_hash']) == 64 for r in rows)
    assert all(r['algorithm'] == 'kahn_lexicographical' and r['weight_rule'] == 'MAX(weight_0_1)' for r in rows)
    baseline_rows = [r for r in rows if r.get('comparison_type','M2_vs_M3') == 'M2_vs_M3']
    assert len({(r['graph'],r['tau'],r['lambda']) for r in baseline_rows}) == 60
    assert all(len(r['configuration_hash']) == 64 and r['scenario_run_id'] for r in baseline_rows)

def test_json_and_fixed_request(study):
    run = study[2]
    text,media = export_file(run,'experiment2-results.json')
    assert media == 'application/json' and json.loads(text) == run
    assert len(json.loads(text)['scenarios']) == 60
    assert run['provenance']['input_manifest']
    assert run['provenance']['parameters']['taus'] == [1,2,3,4]
    with pytest.raises(ValidationError):
        Experiment2Request(version_id='a'*64, lambda_=1)
    with pytest.raises(ValueError):
        export_file(run,'unknown.csv')

def test_api_functions_restore_and_export_without_running_server(study):
    import asyncio
    from app.main import experiment2, experiment2_export
    from fastapi import HTTPException
    db,snapshot,run,_,_ = study
    assert experiment2(Experiment2Request(version_id=snapshot.version.id),db) == run
    response = experiment2_export(run['provenance']['run_id'],'experiment2-summary.csv',db)
    async def body():
        return ''.join([chunk async for chunk in response.body_iterator])
    assert len(list(csv.DictReader(io.StringIO(asyncio.run(body()))))) == 60
    assert response.headers['x-dataset-version'] == snapshot.version.id
    assert 'experiment2-summary.csv' in response.headers['content-disposition']
    with pytest.raises(HTTPException) as exc:
        experiment2_export(run['provenance']['run_id'],'invalid.csv',db)
    assert exc.value.status_code == 404
