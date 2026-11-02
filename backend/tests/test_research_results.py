import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from app.models import ExperimentRun
from app.api.schemas import ExperimentRequest, ResearchRequest
from app.services.experiments import load_snapshot, execute_run
from app.services.research_results import average_ranks, ranking_comparison, deficit_distribution, execute_research


def test_tied_ranks_and_undefined_correlations():
    assert average_ranks([4,1,1,3])==[4,1.5,1.5,3]
    rows=[{'source_profile':'s','target_profile':t,'M2':1,'M3':1} for t in ['z','a','b']]
    result=ranking_comparison(rows,3)[0]
    assert result['spearman'] is None
    assert result['top_m2']==['a','b','z']
    assert result['overlap']==1
    rows[0]['M2']=rows[0]['M3']=2
    assert ranking_comparison(rows)[0]['spearman']==pytest.approx(1)


def test_histogram_conserves_population_and_separates_zero():
    rows=[{'M2':1.,'M3':1.+x} for x in [0,0,.1,.4,1.]]
    bins=deficit_distribution(rows)
    assert bins[0]['label']=='= 0' and bins[0]['count']==2
    assert sum(b['count'] for b in bins)==5
    assert bins[-1]['count']==1
    assert deficit_distribution([{'M2':2,'M3':2}])==[{'label':'= 0','lower':0.,'upper':0.,'count':1}]


@pytest.mark.parametrize('kwargs',[
 {'taus':[1,1]}, {'taus':[float('nan')]}, {'taus':[-1]}, {'taus':[5]},
 {'lambdas':[float('inf')]}, {'lambdas':[-1]}, {'lambdas':[11]},
 {'taus':[0,1,2,3,4], 'lambdas':[0,.1,.2,.3,.4,.5]}, {'top_k':4},
])
def test_bad_sensitivity_grids_rejected(kwargs):
    with pytest.raises(ValidationError):
        ResearchRequest(experiment=ExperimentRequest(source_profile='backend:junior',target_profile='fullstack:middle'),**kwargs)


def test_sensitivity_persisted_replay_and_unchanged_models(session):
    snapshot=load_snapshot(session)
    base=ExperimentRequest(source_profile='backend:junior',target_profile='fullstack:middle',version_id=snapshot.version.id)
    request=ResearchRequest(experiment=base,taus=[2,1],lambdas=[1,0],top_k=3)
    assert request.taus==[1,2] and request.lambdas==[0,1]
    before=execute_run(session,snapshot,base,'batch')
    research=execute_research(session,snapshot,request)
    assert research['baseline']==before
    assert len(research['max_extra'])==182
    assert research['max_extra']==sorted(research['max_extra'],key=lambda r:(-r['extra'],r['source_profile'],r['target_profile']))
    assert sum(p['count'] for p in research['distribution'])==182
    assert len(research['ranking'])==14
    assert len(research['sensitivity'])==4
    for point in research['sensitivity']:
        stored=session.get(ExperimentRun,point['run_id'])
        assert stored.version_id==snapshot.version.id
        assert stored.parameters['minimum_prerequisite_level']==point['tau']
        assert stored.parameters['lambda']==point['lambda']
        assert all(r['M3']==r['M2'] for r in stored.payload['results']) if point['lambda']==0 else True
        assert point['mean_M2']==pytest.approx(research['summary']['mean_M2'])
    assert execute_research(session,snapshot,request)==research
    assert session.get(ExperimentRun,research['provenance']['run_id']).payload==research
    assert research['provenance']['parameters']['experiment']['version_id']==snapshot.version.id
    assert research['provenance']['record_hash']==snapshot.metadata['record_hash']
    # Research adds analyses only; original calculations remain byte-for-byte equivalent JSON values.
    assert execute_run(session,snapshot,base,'batch')==before


def test_research_http_and_replay(session):
    app.dependency_overrides[get_db]=lambda:session
    try:
        with TestClient(app) as client:
            version=load_snapshot(session).version.id
            payload={'experiment':{'source_profile':'backend:junior','target_profile':'fullstack:middle','version_id':version},'taus':[1],'lambdas':[0,.5]}
            response=client.post('/api/experiments/research',json=payload)
            assert response.status_code==200,response.text
            result=response.json()
            assert result['provenance']['dataset']==version
            assert client.get('/api/runs/'+result['provenance']['run_id']).json()==result
            assert client.post('/api/experiments/research',json=payload).json()==result
    finally:
        app.dependency_overrides.clear()
