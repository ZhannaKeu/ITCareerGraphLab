import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import networkx as nx
import pytest
from pydantic import ValidationError
from sqlalchemy import select,func,create_engine,inspect
from app.models import PrerequisiteClassification,RecordProvenance,ExperimentRun
from app.api.schemas import ExperimentRequest,RelationImpactRequest,RevisionRequest
from app.services.experiments import load_snapshot,execute_run
from app.services.relation_graphs import SPEC,edge_id,graph_configuration,digest,ensure_classification
from app.services.relation_impact import execute_relation_impact,kendall_tau_b,correlations
from app.services.versions import create_revision,key,metadata

REQUIRED={15,16,17,18,19,21,22,24,27,28,29,30,31,45}

def parameters(snapshot,**kw):
    return ExperimentRequest(source_profile='backend:junior',target_profile='fullstack:middle',version_id=snapshot.version.id,**kw)


def test_exact_fifty_one_rows_off_by_one_and_preliminary_trust(session,dataset_dir):
    snapshot=load_snapshot(session)
    rows=list(csv.DictReader((dataset_dir/'prerequisites.csv').open(encoding='utf-8-sig')))
    labels=snapshot.classification['relations']
    assert len(labels)==len(rows)==51
    for i,(source,label) in enumerate(zip(rows,labels),1):
        assert label['source_row']==i
        assert (label['from_skill'],label['to_skill'])==(source['from_skill'],source['to_skill'])
        assert label['relation_type']==('Required' if i in REQUIRED else 'Related' if i==14 else 'Recommended')
        assert label['min_level'] is None
        assert label['verification_status']=='Unverified'
        assert label['classification_source']=='AI-assisted preliminary review'
        assert label['edge_id']==edge_id(source['from_skill'],source['to_skill'])
    assert labels[13]['from_skill']=='html_css' and labels[13]['to_skill']=='javascript' and labels[13]['relation_type']=='Related'
    assert labels[14]['from_skill']=='javascript' and labels[14]['to_skill']=='typescript' and labels[14]['relation_type']=='Required'
    assert all(p.status=='Unverified' for p in session.scalars(select(RecordProvenance)))
    ensure_classification(session,snapshot.version.id)
    assert session.scalar(select(func.count()).select_from(PrerequisiteClassification))==51


def test_g_configs_counts_node_population_hashes_and_acyclicity(session):
    s=load_snapshot(session);configs={g:graph_configuration(s,g) for g in ('G1','G2','G3')}
    assert [configs[g]['edge_count'] for g in configs]==[51,14,50]
    assert all(c['node_count']==71 and c['dataset_version']==s.version.id for c in configs.values())
    assert all(c['node_ids']==configs['G1']['node_ids'] for c in configs.values())
    assert set(configs['G2']['included_edge_ids'])<set(configs['G3']['included_edge_ids'])<set(configs['G1']['included_edge_ids'])
    for name,c in configs.items():
        assert len(c['included_edge_ids'])==len(set(c['included_edge_ids']))
        assert c['configuration_hash']==digest({k:v for k,v in c.items() if k!='configuration_hash'})
        assert graph_configuration(s,name)==c
        graph=nx.DiGraph();graph.add_nodes_from(c['node_ids']);graph.add_edges_from((e['from_skill'],e['to_skill']) for e in c['edges'])
        assert nx.is_directed_acyclic_graph(graph)
    assert len({c['configuration_hash'] for c in configs.values()})==3


def test_legacy_hash_and_g1_scores_exactly_compatible(session):
    s=load_snapshot(session)
    legacy=execute_run(session,s,parameters(s),'batch')
    original=execute_run(session,s,parameters(s,graph_configuration='G1'),'batch')
    assert legacy['results']==original['results']
    assert 'graph_configuration' not in legacy['provenance']['parameters']
    # Compare the archived runtime-independent run hash to a resolved historical request.
    expected=hashlib.sha256(json.dumps({'dataset':s.version.id,'record_hash':s.metadata['record_hash'],
        'parameters':legacy['provenance']['parameters'],'implementation':'1.1.0','experiment_kind':'batch'},sort_keys=True).encode()).hexdigest()
    assert expected==legacy['provenance']['run_id']
    assert original['provenance']['graph_configuration']['edge_count']==51
    assert original['provenance']['run_id']!=legacy['provenance']['run_id']


def test_kendall_tau_b_ties_and_undefined():
    assert kendall_tau_b([1,2,3],[1,2,3])==1
    assert kendall_tau_b([1,2,3],[3,2,1])==-1
    assert kendall_tau_b([1,1,2],[1,2,2])==pytest.approx(.5)
    assert kendall_tau_b([1,1,1],[1,2,3]) is None
    assert kendall_tau_b([1,1],[1,1]) is None
    assert correlations([1,1,2],[1,1,2])==pytest.approx((1,1))
    assert correlations([1,1],[1,2])==(None,None)


def test_controlled_182_pairs_common_baseline_replay_and_sensitivity(session):
    s=load_snapshot(session)
    request=RelationImpactRequest(experiment=parameters(s),taus=[1,2],lambdas=[0,.5])
    run=execute_relation_impact(session,s,request)
    assert len(run['transitions'])==182
    assert len({(r['source_profile'],r['target_profile']) for r in run['transitions']})==182
    assert len(run['sensitivity'])==12
    assert len(run['sensitivity_comparisons'])==12
    assert run['provenance']['dataset']==s.version.id
    assert run['provenance']['parameters']['experiment']['version_id']==s.version.id
    assert set(run['comparisons'])=={'G1_G2','G1_G3','G2_G3'}
    assert set(run['against_M2'])=={'G1','G2','G3'}
    for g,batch in run['runs'].items():
        assert batch['provenance']['dataset']==s.version.id
        assert batch['provenance']['graph_configuration']['configuration_hash']==run['configurations'][g]['configuration_hash']
        assert len(batch['results'])==182
        assert sum(b['count'] for b in run['distributions'][g])==182
    assert [(b['lower'],b['upper']) for b in run['distributions']['G1']]==[(b['lower'],b['upper']) for b in run['distributions']['G2']]
    for r in run['transitions']:
        assert r['source_profile']!=r['target_profile']
        assert r['M3_G1']>=r['M3_G3']>=r['M3_G2']>=r['M2']
    for point in run['sensitivity']:
        saved=session.get(ExperimentRun,point['run_id']).payload
        assert saved['provenance']['parameters']['graph_configuration']==point['graph']
        assert saved['provenance']['parameters']['minimum_prerequisite_level']==point['tau']
        assert saved['provenance']['parameters']['lambda']==point['lambda']
        assert saved['provenance']['dataset']==s.version.id
        assert point['pairs']==182
        if point['lambda']==0:
            assert point['weighted_extra_pairs']==0 and point['mean_extra']==0
            assert all(r['M3']==r['M2'] for r in saved['results'])
    assert any(p['lambda']==0 and p['prerequisite_deficit_pairs']>0 for p in run['sensitivity'])
    assert execute_relation_impact(session,s,request)==run
    assert session.get(ExperimentRun,run['provenance']['run_id']).payload==run
    assert all(len(c['sources'])==14 for c in run['comparisons'].values())


def test_classification_does_not_inherit_expert_verification(session):
    s=load_snapshot(session)
    child=create_revision(session,RevisionRequest(parent_id=s.version.id,label='Reviewed edge',author='Reviewer',reason='Test provenance independence',changes=[{'entity':'prerequisite','key':['oop','design_patterns'],'operation':'verify','verification':{'status':'Expert Verified','reviewer':'Named reviewer','evidence':'Explicit test assessment'}}]))['version_id']
    snapshot=load_snapshot(session,child)
    assert snapshot.record_provenance['prerequisite',key(['oop','design_patterns'])]['status']=='Expert Verified'
    assert all(e['verification_status']=='Unverified' and e['min_level'] is None for e in snapshot.classification['relations'])
    assert graph_configuration(snapshot,'G1')['dataset_version']==child
    assert graph_configuration(snapshot,'G1')['configuration_hash']!=graph_configuration(s,'G1')['configuration_hash']


def test_changed_edge_population_rejected_without_restoring_deleted_edge(session):
    s=load_snapshot(session)
    child=create_revision(session,RevisionRequest(parent_id=s.version.id,label='Deleted edge',author='Researcher',reason='Test explicit eligibility',changes=[{'entity':'prerequisite','key':['oop','design_patterns'],'operation':'delete'}]))['version_id']
    changed=load_snapshot(session,child)
    with pytest.raises(ValueError,match='51-edge population'):graph_configuration(changed,'G1')
    assert len(changed.edges)==50
    assert len(execute_run(session,changed,parameters(changed),'batch')['results'])==182


@pytest.mark.parametrize('kwargs',[{'verification_scope':'verified'},{'included_edges':[('sql','oop')]},{'excluded_edges':[('oop','design_patterns')]}])
def test_named_graphs_reject_ambiguous_overrides_and_verified_claims(session,kwargs):
    s=load_snapshot(session)
    with pytest.raises(ValueError):execute_run(session,s,parameters(s,graph_configuration='G2',**kwargs),'batch')
    with pytest.raises(ValidationError):RelationImpactRequest(experiment=parameters(s,**kwargs),taus=[1],lambdas=[1])


def test_sidecar_matches_packaged_protocol_and_inputs_are_unchanged(dataset_dir):
    assert json.loads((dataset_dir/'prerequisite_relations_v2.json').read_text())==SPEC
    assert hashlib.sha256((dataset_dir/'prerequisites.csv').read_bytes()).hexdigest()==SPEC['source_sha256']
    audit=json.loads((dataset_dir.parent/'docs/dataset-audit.json').read_text())
    for name,m in audit['manifest'].items(): assert hashlib.sha256((dataset_dir/name).read_bytes()).hexdigest()==m['sha256']


def test_migrations_on_isolated_sqlite_only(tmp_path):
    backend=Path(__file__).resolve().parents[1]
    url=f'sqlite:///{tmp_path}/migration-test.db'
    env={**os.environ,'DATABASE_URL':url,'RUN_POSTGRES_TESTS':'0'}
    for arguments in [('upgrade','head'),('check',)]:
        result=subprocess.run([sys.executable,'-m','alembic',*arguments],cwd=backend,env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stdout+result.stderr
    engine=create_engine(url)
    assert 'prerequisite_classifications' in inspect(engine).get_table_names()
    with engine.connect() as c:
        from sqlalchemy import text
        assert c.scalar(text('SELECT version_num FROM alembic_version'))=='0004'
    engine.dispose()


def test_actual_pre_v2_archived_run_identity_survives(session):
    old=json.loads((Path(__file__).parent/'fixtures/legacy_batch_run.json').read_text())
    snapshot=load_snapshot(session,old['dataset'])
    assert snapshot.metadata['record_hash']==old['record_hash']
    request=ExperimentRequest.model_validate(old['parameters'])
    result=execute_run(session,snapshot,request,old['experiment_kind'])
    assert result['provenance']['run_id']==old['run_id']
    assert result['provenance']['parameters']==old['parameters']


def test_configurations_on_isolated_asgi_client(session):
    # In-process ASGI calls only: no uvicorn, listening socket, external HTTP or main DB.
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import get_db
    app.dependency_overrides[get_db]=lambda:session
    try:
        with TestClient(app) as client:
            version=load_snapshot(session).version.id
            configs=client.get(f'/api/graph-configurations?version_id={version}').json()
            assert configs['available']
            assert [c['edge_count'] for c in configs['configurations']]==[51,14,50]
            for name,count in [('G1',51),('G2',14),('G3',50)]:
                response=client.get(f'/api/skills/graph?version_id={version}&configuration={name}')
                assert response.status_code==200,response.text
                graph=response.json()
                assert len(graph['nodes'])==71 and len(graph['edges'])==count
                assert graph['configuration']['dataset_version']==version
                assert all(e['min_level'] is None and e['classification_verification_status']=='Unverified' for e in graph['edges'])
            body={'experiment':{'source_profile':'backend:junior','target_profile':'fullstack:middle','version_id':version},'taus':[1],'lambdas':[.5]}
            response=client.post('/api/experiments/relation-impact',json=body)
            assert response.status_code==200,response.text
            result=response.json()
            assert len(result['transitions'])==182
            assert client.get('/api/runs/'+result['provenance']['run_id']).json()==result
    finally:
        app.dependency_overrides.clear()
