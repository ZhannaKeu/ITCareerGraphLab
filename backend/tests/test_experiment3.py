"""Robustness protocol, isolated SQLite only. No server, Docker or network."""
import csv
import io
import json
import hashlib
from pathlib import Path
import pytest
import networkx as nx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from pydantic import ValidationError
from app.db import Base
from app.models import ExperimentRun
from app.api.schemas import ExperimentRequest, Experiment3Request
from app.services.importer import import_dataset
from app.services.experiments import load_snapshot, run_experiment
from app.services.experiment2 import execute_experiment2
from app.services.experiment3 import (execute_experiment3, calculate_scenario, temporary_snapshot, comparison_metrics, export_file, CONTROLS, FINAL, ALTERNATIVE)
from app.services.relation_impact import compare_rankings, correlations
from app.services.relation_graphs import digest
from conftest import DATASETS

@pytest.fixture(scope='module')
def study():
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        import_dataset(db,DATASETS);s=load_snapshot(db)
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in DATASETS.glob('*.csv')}
        records=[(r.profile_id,r.skill_id,r.group_id,r.required_level) for r in s.requirements]
        weights=[(w.source,w.role,w.skill_id,w.weight) for w in s.weights]
        old=execute_experiment2(db,s);old_json=json.dumps(old,sort_keys=True)
        run=execute_experiment3(db,s)
        yield db,s,run,before,records,weights,old,old_json
    engine.dispose()

def test_full_population_and_independence(study):
    _,s,run,*_=study
    assert run['scenario_count']==len(run['scenarios'])==345
    assert {k:sum(r['study']==k for r in run['scenarios']) for k in 'ABC'}=={'A':45,'B':45,'C':255}
    assert len({r['id'] for r in run['scenarios']})==345
    assert len(run['edge_configurations'])==51
    index={r['id']:r for r in run['scenarios']}
    for row in run['scenarios']:
        assert (row['tau'],row['lambda']) in CONTROLS
        assert len(row['results'])==182
        assert len({(r['source_profile'],r['target_profile']) for r in row['results']})==182
        assert len(row['rankings']['M2'])==len(row['rankings']['M3'])==14
        assert all(r['M3']>=r['M2'] for r in row['results'])
        base=index[row['baseline_id']]
        assert (base['graph'],base['tau'],base['lambda'])==(row['graph'],row['tau'],row['lambda'])
        assert base['variant']==('B0' if row['study']=='B' else 'A0')
        if row['study']=='A': assert row['weight_mode']=='B0' and row['excluded_edge'] is None
        if row['study']=='B': assert row['unknown_source_level']==0 and row['excluded_edge'] is None
        if row['study']=='C':
            assert row['graph']=='G1' and row['unknown_source_level']==0 and row['weight_mode']=='B0'
            assert all(r['M2']==r['baseline_M2'] and r['M3']<=r['baseline_M3'] for r in row['results'])
        if row['variant'] in ('A0','B0'):
            for model in ('M2','M3'):
                assert row['metrics'][model]['max_absolute_difference']==0
                assert row['metrics'][model]['top3_membership_changed_sources']==0
    assert sum(len(r['results']) for r in run['scenarios'])==62790

def test_baseline_exact_existing_engine_and_weight_sources(study):
    _,s,run,*_=study
    for variant in ('A0','B0','B1'):
        scenario=next(r for r in run['scenarios'] if r['variant']==variant and r['graph']=='G2' and r['tau']==4 and r['lambda']==2)
        row=scenario['results'][0]
        request=ExperimentRequest(source_profile=row['source_profile'],target_profile=row['target_profile'],minimum_prerequisite_level=4,lambda_=2,graph_configuration='G2',weight_source=ALTERNATIVE if variant=='B1' else FINAL)
        expected=run_experiment(s,request)
        for key in ('M1','M2','M3','prerequisite_burden'): assert row[key]==expected[key]
    assert len(run['weight_diagnostics'])==21
    assert all(r['normalization']=='none' for r in run['weight_diagnostics'])
    assert all(r['fallback_weight_count']==0 for sc in run['scenarios'] if sc['variant']=='B2' for r in sc['results'])
    assert any(r['fallback_weight_count']>0 for sc in run['scenarios'] if sc['variant']=='B0' for r in sc['results'])

@pytest.mark.parametrize('level',[0,1,2])
def test_transient_unknown_assumptions_preserve_known_values(study,level):
    _,s,run,*_=study
    source=sorted(p.id for p in s.profiles)[0]
    original={r.skill_id:r.required_level for r in s.requirements if r.profile_id==source and r.skill_id is not None}
    transient=temporary_snapshot(s,source,level)
    actual={r.skill_id:r.required_level for r in transient.requirements if r.profile_id==source and r.skill_id is not None}
    for skill,value in original.items():
        if value is not None: assert actual[skill]==value
    if level:
        assert all(actual[x.id]==(original[x.id] if original.get(x.id) is not None else level) for x in s.skills)
    else: assert actual==original
    scenario=next(sc for sc in run['scenarios'] if sc['variant']==f'A{level}' and sc['graph']=='G3' and sc['tau']==4 and sc['lambda']==2)
    independent=calculate_scenario(s,run['configurations']['G3'],4,2,unknown_level=level)
    for computed,saved in zip(independent,scenario['results']):
        assert all(saved[k]==v for k,v in computed.items())
        assert saved['unknown_source_count']==len(saved['unknown_source_skills'])
        assert saved['assumed_source_count']==(saved['unknown_source_count'] if level else 0)

def test_all_single_edge_configs_and_influence_order(study):
    run=study[2];g1=run['configurations']['G1']
    for edge,c in run['edge_configurations'].items():
        assert c['configuration_hash']==digest({k:v for k,v in c.items() if k!='configuration_hash'})
        assert c['excluded_edge_ids']==[edge]
        assert set(c['included_edge_ids'])==set(g1['included_edge_ids'])-{edge}
        assert len(c['edges'])==50 and c['node_ids']==g1['node_ids']
        graph=nx.DiGraph();graph.add_nodes_from(c['node_ids']);graph.add_edges_from((r['from_skill'],r['to_skill']) for r in c['edges'])
        assert nx.is_directed_acyclic_graph(graph)
    assert len(run['edge_influence'])==255
    for t,l in CONTROLS:
        cells=sorted((r for r in run['edge_influence'] if r['tau']==t and r['lambda']==l),key=lambda r:r['score_rank'])
        assert [r['score_rank'] for r in cells]==list(range(1,52))
        assert [r['mean_absolute_difference'] for r in cells]==sorted((r['mean_absolute_difference'] for r in cells),reverse=True)

def test_differences_rank_ties_and_undefined():
    def row(target,m2,m3):
        return dict(source_profile='s',target_profile=target,M2=m2,M3=m3,unknown_source_count=1,assumed_source_count=1,fallback_weight_count=0)
    base=[row('a',1,2),row('b',1,2),row('c',2,3)]
    other=[row('a',2,1),row('b',2,1),row('c',3,2)]
    metrics,ranks=comparison_metrics(base,other)
    assert metrics['M2']['mean_difference']==1 and metrics['M3']['mean_difference']==-1
    assert metrics['M3']['mean_absolute_difference']==metrics['M3']['max_absolute_difference']==1
    assert metrics['M3']['mean_spearman']==pytest.approx(1)
    assert metrics['M3']['mean_kendall_tau_b']==1
    assert ranks['M3']==compare_rankings(base,other,'M3','M3')['sources']
    assert correlations([1,1,1],[1,2,3])==(None,None)
    constant=[row('a',1,1),row('b',1,1)]
    metrics,_=comparison_metrics(constant,constant)
    assert metrics['M3']['mean_spearman'] is None and metrics['M3']['undefined_spearman_sources']==1
    assert metrics['M3']['mean_kendall_tau_b'] is None

@pytest.mark.parametrize('name,count',[('summary',345),('results',62790),('rankings',9660),('edges',255)])
def test_csv_exports(study,name,count):
    run=study[2];body,media=export_file(run,f'experiment3-{name}.csv')
    rows=list(csv.DictReader(io.StringIO(body)))
    assert media.startswith('text/csv') and len(rows)==count
    assert all(r['run_id']==run['provenance']['run_id'] and r['dataset']==run['provenance']['dataset'] and len(r['source_data_hash'])==64 for r in rows)
    assert all(r['analysis_version']=='experiment3-robustness-1.0.0' and len(r['configuration_hash'])==64 for r in rows)
    if name!='edges': assert len({r['id'] for r in rows})==345
    if name=='rankings': assert all(len(json.loads(r['target_ranks']))==13 for r in rows)

def test_replay_immutability_and_json(study):
    db,s,run,before,records,weights,old,old_json=study
    assert execute_experiment3(db,s)==run
    body,_=export_file(run,'experiment3-results.json')
    assert json.loads(body)==run
    assert json.dumps(db.get(ExperimentRun,old['provenance']['run_id']).payload,sort_keys=True)==old_json
    assert [(r.profile_id,r.skill_id,r.group_id,r.required_level) for r in s.requirements]==records
    assert [(w.source,w.role,w.skill_id,w.weight) for w in s.weights]==weights
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in before.items())
    with pytest.raises(ValidationError): Experiment3Request(version_id=s.version.id,lambda_=2)
    with pytest.raises(ValueError): export_file(run,'unknown.json')

def test_explicit_null_and_known_zero_are_distinct(study):
    from dataclasses import replace
    from types import SimpleNamespace
    s=study[1];source=sorted(p.id for p in s.profiles)[0]
    a,b=sorted(x.id for x in s.skills)[:2]
    reqs=[r for r in s.requirements if not(r.profile_id==source and r.skill_id in (a,b))]
    reqs.extend([SimpleNamespace(profile_id=source,skill_id=a,group_id=None,required_level=0.),SimpleNamespace(profile_id=source,skill_id=b,group_id=None,required_level=None)])
    synthetic=replace(s,requirements=reqs)
    for level in (1,2):
        temp=temporary_snapshot(synthetic,source,level)
        values={r.skill_id:r.required_level for r in temp.requirements if r.profile_id==source and r.skill_id is not None}
        assert values[a]==0 and values[b]==level
        assert all(r in temp.requirements for r in reqs if r.profile_id!=source)

def test_endpoint_functions_without_server(study):
    import asyncio
    from fastapi import HTTPException
    from app.main import experiment3,experiment3_export
    db,s,run,*_=study
    assert experiment3(Experiment3Request(version_id=s.version.id),db)==run
    response=experiment3_export(run['provenance']['run_id'],'experiment3-summary.csv',db)
    async def consume(): return ''.join([chunk async for chunk in response.body_iterator])
    assert len(list(csv.DictReader(io.StringIO(asyncio.run(consume())))))==345
    assert response.headers['x-dataset-version']==s.version.id
    with pytest.raises(HTTPException): experiment3_export(run['provenance']['run_id'],'unknown.csv',db)
