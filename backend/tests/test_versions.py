import copy
from sqlalchemy import select, func
from fastapi.testclient import TestClient
import pytest
from app.db import get_db
from app.main import app
from app import models as m
from app.api.schemas import RevisionRequest, ExperimentRequest
from app.services.experiments import load_snapshot, execute_run
from app.services.versions import create_revision, metadata, catalog, annotations, history, key, record_hash

@pytest.fixture
def client(session):
    app.dependency_overrides[get_db]=lambda:session
    with TestClient(app) as c:yield c
    app.dependency_overrides.clear()


def root(session):
    return load_snapshot(session).version.id


def revision(session, changes, parent=None, label='reviewed revision'):
    request=RevisionRequest(parent_id=parent or root(session), label=label, author='Researcher', reason='Recorded correction for sensitivity analysis', changes=changes)
    return create_revision(session,request)['version_id']


def test_all_imported_records_unverified_despite_expert_csv_claims(session):
    version=root(session);meta=metadata(session,version)
    assert meta['kind']=='original' and meta['parent_id'] is None
    assert meta['verification_counts']['requirement']=={'Unverified':204}
    assert meta['verification_counts']['prerequisite']=={'Unverified':51}
    assert meta['disclosure']['independently_verified'] is False
    records=catalog(session,version);provs=annotations(session,version)
    assert len(records)==len(provs)
    assert meta['record_hash']==record_hash(records,provs)
    assert all(p['status']=='Unverified' and p['reviewer'] is None for p in provs.values())
    assert any(d.get('weight_origin')=='expert' for (e,_),d in records.items() if e=='requirement')
    assert all(p['origin']['rows'] for (e,_),p in provs.items())
    course=next(p for (e,_),p in provs.items() if e=='course_skill')
    assert 'учебного плана' in course['origin']['course_name_origin']


def test_correction_is_copy_on_write_and_keeps_parent_and_raw_rows(session):
    parent=root(session);before=catalog(session,parent);before_prov=annotations(session,parent)
    child=revision(session,[{'entity':'requirement','key':['backend:junior','skill','sql'],'operation':'upsert','required_level':4}])
    after=catalog(session,child)
    assert catalog(session,parent)==before
    assert annotations(session,parent)==before_prov
    assert after['requirement',key(['backend:junior','skill','sql'])]['required_level']==4
    assert {k:d for k,d in before.items() if k[0]=='source_row'}=={k:d for k,d in after.items() if k[0]=='source_row'}
    assert session.get(m.ActiveDataset,1).version_id==parent
    meta=metadata(session,child)
    assert meta['parent_id']==parent and meta['root_id']==parent and meta['kind']=='corrected'
    events=history(session,child)
    assert len(events)==2
    assert events[0]['changes'][0]['before']['data']['required_level']!=4
    assert events[0]['changes'][0]['after']['data']['required_level']==4
    assert events[0]['changes'][0]['author']=='Researcher'


def test_reviews_require_evidence_and_edit_resets_previous_review(session):
    original=root(session);k=['oop','design_patterns']
    reviewed=revision(session,[{'entity':'prerequisite','key':k,'operation':'verify','verification':{'status':'Expert Verified','reviewer':'Domain reviewer','evidence':'Expert review record E-2027-01'}}])
    p=annotations(session,reviewed)['prerequisite',key(k)]
    assert p['status']=='Expert Verified'
    edited=revision(session,[{'entity':'prerequisite','key':k,'operation':'upsert'}],parent=reviewed)
    assert annotations(session,edited)['prerequisite',key(k)]['status']=='Unverified'
    assert annotations(session,reviewed)['prerequisite',key(k)]['status']=='Expert Verified'
    assert annotations(session,original)['prerequisite',key(k)]['status']=='Unverified'
    assert len(history(session,edited))==3
    # Reviewing is a separate claim, not a value edit or automatic scientific validation.
    assert catalog(session,reviewed)==catalog(session,original)
    assert metadata(session,reviewed)['record_hash']!=metadata(session,original)['record_hash']


def test_source_verification_is_record_specific_and_traceable(session):
    k=['demo-missing']
    record=next((e,jsonkey) for e,jsonkey in catalog(session,root(session)) if e=='course_skill')
    import json
    k=json.loads(record[1])
    child=revision(session,[{'entity':'course_skill','key':k,'operation':'verify','verification':{'status':'Source Verified','reviewer':'Curriculum reviewer','evidence':'Local curriculum document, section 2, explicitly checked mapping','note':'Manual attestation'}}])
    assert annotations(session,child)[record]['status']=='Source Verified'
    assert metadata(session,child)['verification_counts']['course_skill']['Source Verified']==1
    assert all(p['status']=='Unverified' for (e,_),p in annotations(session,child).items() if e=='source_row')


@pytest.mark.parametrize('change',[
 {'entity':'prerequisite','key':['oop','oop'],'operation':'upsert'},
 {'entity':'prerequisite','key':['architecture','oop'],'operation':'upsert'},
 {'entity':'prerequisite','key':['missing','oop'],'operation':'upsert'},
 {'entity':'prerequisite','key':['oop','missing'],'operation':'delete'},
 {'entity':'requirement','key':['backend:junior','skill','missing'],'operation':'upsert','required_level':2},
 {'entity':'requirement','key':['backend:junior','skill','sql'],'operation':'upsert'},
 {'entity':'requirement','key':['backend:junior','skill','sql'],'operation':'upsert','required_level':1.5},
 {'entity':'prerequisite','key':['oop','design_patterns'],'operation':'verify','verification':{'status':'Expert Verified'}},
 {'entity':'prerequisite','key':['oop','design_patterns'],'operation':'verify','verification':{'status':'Source Verified','reviewer':' ','evidence':' '}},
 {'entity':'weight','key':['role_skill_weights.csv','backend','sql'],'operation':'upsert'},
])
def test_invalid_revision_is_atomic(session,change):
    version=root(session);before=catalog(session,version)
    count=session.scalar(select(func.count()).select_from(m.DatasetVersion))
    with pytest.raises(ValueError): revision(session,[change])
    assert session.scalar(select(func.count()).select_from(m.DatasetVersion))==count
    assert catalog(session,version)==before


def test_revisions_idempotent_and_diamond_counts_recomputed(session):
    change={'entity':'prerequisite','key':['oop','design_patterns'],'operation':'delete'}
    first=revision(session,[change]);second=revision(session,[change])
    assert first==second
    assert session.scalar(select(func.count()).select_from(m.DatasetVersion))==2
    assert ('prerequisite',key(change['key'])) not in catalog(session,first)
    assert metadata(session,first)['verification_counts']['prerequisite']=={'Unverified':50}
    assert any(e['operation']=='recalculate' for e in history(session,first)[0]['changes'])
    g=load_snapshot(session,first)
    assert len(g.edges)==50
    assert g.version.quality['stats']['edges']==50


def test_experiments_persist_exact_results_and_pin_resolved_versions(session):
    s=load_snapshot(session)
    request=ExperimentRequest(source_profile='backend:junior',target_profile='fullstack:middle')
    pair=execute_run(session,s,request)
    assert pair['provenance']['parameters']['version_id']==s.version.id
    assert pair['provenance']['record_hash']==metadata(session,s.version.id)['record_hash']
    assert execute_run(session,s,request)==pair
    stored=session.get(m.ExperimentRun,pair['provenance']['run_id'])
    assert stored.payload==pair
    batch=execute_run(session,s,request,'batch')
    assert batch['provenance']['run_id']!=pair['provenance']['run_id']
    assert len(batch['results'])==182


def test_verified_scope_without_coverage_is_not_a_zero_gap(client):
    response=client.post('/api/experiments/compare',json={'source_profile':'backend:junior','target_profile':'fullstack:middle','verification_scope':'verified'})
    assert response.status_code==422
    assert 'no verified coverage' in response.json()['detail']


def test_version_api_filters_history_comparison_and_replay(client,session):
    original=root(session)
    response=client.post('/api/versions',json={'parent_id':original,'label':'Updated target SQL','author':'Reviewer','reason':'Explicit test correction','changes':[{'entity':'requirement','key':['fullstack:middle','skill','sql'],'operation':'upsert','required_level':4,'verification':{'status':'Source Verified','reviewer':'Reviewer','evidence':'Assessment record R1'}}]})
    assert response.status_code==201,response.text
    child=response.json()['version_id']
    records=client.get(f'/api/versions/{child}/records?entity=requirement&status=Source%20Verified').json()
    assert records['total']==1
    assert records['records'][0]['data']['required_level']==4
    assert len(client.get(f'/api/versions/{child}/history').json())==2
    assert client.get(f'/api/data/role_requirements.csv?version_id={child}').json()['source_version']==original
    assert len(client.get('/api/datasets').json())==2
    comparison=client.post('/api/experiments/versions',json={'original_version':original,'corrected_version':child,'experiment':{'source_profile':'backend:junior','target_profile':'fullstack:middle'},'batch':True})
    assert comparison.status_code==200,comparison.text
    result=comparison.json()
    assert len(result['rows'])==182
    assert result['changed_pairs']>0
    assert result['original']['provenance']['dataset']==original
    assert result['corrected']['provenance']['dataset']==child
    run=result['original']['provenance']['run_id']
    assert client.get(f'/api/runs/{run}').json()==result['original']
    assert len(client.get('/api/runs').json())==2
    again=client.post('/api/experiments/versions',json={'original_version':original,'corrected_version':child,'experiment':{'source_profile':'backend:junior','target_profile':'fullstack:middle'},'batch':True})
    assert again.json()==result


def test_verified_scope_uses_only_explicitly_reviewed_requirements_and_weights(session):
    review={'status':'Expert Verified','reviewer':'Reviewer','evidence':'Explicit assessment test record'}
    child=revision(session,[
        {'entity':'requirement','key':['backend:junior','skill','sql'],'operation':'verify','verification':review},
        {'entity':'requirement','key':['fullstack:middle','skill','sql'],'operation':'verify','verification':review},
        {'entity':'weight','key':['skill_weights_by_role_final_v2.csv','fullstack','sql'],'operation':'verify','verification':review},
    ])
    s=load_snapshot(session,child)
    verified=execute_run(session,s,ExperimentRequest(source_profile='backend:junior',target_profile='fullstack:middle',verification_scope='verified'))
    assert verified['result']['M1']==1
    assert verified['result']['missing_skills']==['sql']
    assert not verified['result']['fallback_weight_skills']
    assert verified['provenance']['parameters']['verification_scope']=='verified'
    all_records=execute_run(session,s,ExperimentRequest(source_profile='backend:junior',target_profile='fullstack:middle'))
    assert all_records['result']['M1']>verified['result']['M1']
    assert all_records['provenance']['run_id']!=verified['provenance']['run_id']


def test_deleting_requirement_and_unknown_requirement_preserve_audit(session):
    parent=root(session)
    child=revision(session,[{'entity':'requirement','key':['backend:junior','skill','sql'],'operation':'delete'},
        {'entity':'requirement','key':['fullstack:middle','skill','sql'],'operation':'upsert','required_level':None}])
    assert ('requirement',key(['backend:junior','skill','sql'])) not in catalog(session,child)
    assert ('requirement',key(['backend:junior','skill','sql'])) in catalog(session,parent)
    result=execute_run(session,load_snapshot(session,child),ExperimentRequest(source_profile='backend:junior',target_profile='fullstack:middle'))
    assert 'sql' in result['result']['unknown_target_skills']
    assert 'sql' in result['result']['unknown_source_skills']
    assert history(session,child)[0]['changes'][0]['after'] is None
