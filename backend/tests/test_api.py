import csv
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from app.api.schemas import ExperimentRequest
from app.services.experiments import load_snapshot,run_experiment

@pytest.fixture
def client(session):
    app.dependency_overrides[get_db]=lambda:session
    with TestClient(app) as client:yield client
    app.dependency_overrides.clear()

PAYLOAD={'source_profile':'backend:junior','target_profile':'fullstack:middle','lambda':.5}

def test_health_graph_dashboard_and_rows(client):
    assert client.get('/health/live').status_code==200
    assert client.get('/health/ready').status_code==200
    d=client.get('/api/dashboard').json()
    assert not d['is_demo']
    assert d['counts']['transitions']==182
    assert len(client.get('/api/skills/graph').json()['nodes'])==71
    assert len(client.get('/api/profiles').json())==14
    assert client.get('/api/data/role_requirements.csv').json()['rows'][0]['data']['item_type']=='group'
    assert client.get('/api/data/nonexistent').status_code==404
    assert client.get('/api/data/skills.csv?limit=9999').status_code==422


def test_compare_and_batch_and_csv_are_consistent(client):
    one=client.post('/api/experiments/compare',json=PAYLOAD)
    assert one.status_code==200,one.text
    assert one.json()==client.post('/api/experiments/compare',json=PAYLOAD).json()
    batch=client.post('/api/experiments/batch',json=PAYLOAD)
    assert batch.status_code==200,batch.text
    results=batch.json()['results']
    assert len(results)==182
    assert len({(r['source_profile'],r['target_profile']) for r in results})==182
    assert all(r['source_profile']!=r['target_profile'] for r in results)
    same=next(r for r in results if r['source_profile']==PAYLOAD['source_profile'] and r['target_profile']==PAYLOAD['target_profile'])
    assert same==one.json()['result']
    csv_response=client.post('/api/experiments/export',json=PAYLOAD)
    assert csv_response.status_code==200
    rows=list(csv.DictReader(io.StringIO(csv_response.text)))
    assert len(rows)==182
    assert rows[0]['dataset_version']==one.json()['provenance']['dataset']
    assert rows[0]['run_id']==batch.json()['provenance']['run_id']


@pytest.mark.parametrize('patch',[{'target_profile':'absent'},{'target_profile':'backend:junior'},{'lambda':-1},{'algorithm':'bad'},{'included_edges':[['oop','oop']]},{'included_edges':[['architecture','oop']]},{'excluded_edges':[['oop','oop']]},{'included_edges':[['unknown','oop']]}])
def test_invalid_parameters_and_graphs_rejected(client,patch):
    response=client.post('/api/experiments/compare',json={**PAYLOAD,**patch})
    assert response.status_code==422,response.text


def test_edge_ablation_is_recorded_and_does_not_modify_dataset(client):
    payload={**PAYLOAD,'excluded_edges':[['oop','design_patterns']]}
    response=client.post('/api/experiments/compare',json=payload)
    assert response.status_code==200
    assert response.json()['provenance']['parameters']['excluded_edges']==[['oop','design_patterns']]
    assert len(client.get('/api/skills/graph').json()['edges'])==51


def test_group_requirements_excluded_and_weight_sources_independent(session):
    s=load_snapshot(session)
    r=run_experiment(s,ExperimentRequest(**PAYLOAD))
    assert all(x['skill_id']!='backend_language' for x in r['details'])
    assert all('group' not in x for x in r['missing_skills'])
    alternative=run_experiment(s,ExperimentRequest(**PAYLOAD,weight_source='role_skill_weights.csv'))
    assert r['M1']==alternative['M1']
    assert r['M2']!=alternative['M2']
