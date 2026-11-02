import itertools
import random
import networkx as nx
import pytest
from app.research.models import compare, Parameters
from app.research.graph import build_graph, InvalidGraph, topological_order, prerequisite_closure


def test_m1_counts_skill_not_level_units():
    result=compare(['a','b'],[],{'a':1,'b':3},{'a':4,'b':4},{'a':2,'b':1})
    assert result['M1']==2
    assert result['M2']==pytest.approx(1.75)
    assert result['M3']==result['M2']


def test_satisfied_profile_zero_gap():
    r=compare(['a','b'],[('a','b')],{'a':4,'b':4},{'b':2},{'b':1})
    assert [r[k] for k in ['M1','M2','M3']]==[0,0,0]
    assert not r['learning_order']


def test_diamond_shared_prerequisite_counted_once():
    r=compare(['a','b','c','d'],[('a','b'),('a','c'),('b','d'),('c','d')],{}, {'d':4},dict.fromkeys('abcd',1),Parameters(2,0.5))
    assert r['M1']==1
    assert r['M2']==1
    assert r['prerequisite_burden']==1.5
    assert r['M3']==1.75
    assert r['learning_order']==['a','b','c','d']
    assert r['unknown_source_skills']==['a','b','c','d']


def test_direct_prerequisite_overlap_charges_only_extra_units():
    r=compare(['a','b'],[('a','b')],{'a':0,'b':0},{'a':1,'b':4},{'a':2,'b':1},Parameters(3,1))
    assert r['M2']==1.5
    assert r['prerequisite_burden']==1 # (3 - 1) * 2 / 4
    assert r['M3']==2.5
    assert r['details'][0]['additional_deficit']==2


def test_already_known_prerequisite_no_burden():
    r=compare(['a','b'],[('a','b')],{'a':3}, {'b':4},{'b':1},Parameters(2,1))
    assert r['prerequisite_burden']==0
    assert 'a' not in r['unknown_source_skills']


def test_zero_lambda_is_m2_and_unknown_target_is_reported():
    r=compare(['a','b'],[('a','b')],{}, {'b':None},{},Parameters(1,0))
    assert r['M3']==r['M2']==1
    assert r['unknown_target_skills']==['b']
    assert r['fallback_weight_skills']==['a','b']
    assert 'conservative' in r['scenario']


def test_cycle_and_dangling_edges_rejected():
    with pytest.raises(InvalidGraph,match='cycle'):
        build_graph(['a','b'],[('a','b'),('b','a')])
    with pytest.raises(InvalidGraph,match='Unknown'):
        build_graph(['a'],[('a','z')])
    with pytest.raises(InvalidGraph):
        build_graph(['a'],[('a','a')])


@pytest.mark.parametrize('algorithm',['kahn','dfs'])
def test_topological_order_is_valid_for_cross_edges(algorithm):
    edges=[('a','b'),('a','c'),('c','b'),('b','d')]
    g=build_graph('abcd',edges)
    ordered=topological_order(g,algorithm)
    assert len(ordered)==len(set(ordered))==4
    assert all(ordered.index(a)<ordered.index(b) for a,b in edges)
    assert ordered==topological_order(g,algorithm)


def test_deep_dependency_expansion_not_limited_by_recursion():
    skills=[str(i) for i in range(2000)]
    g=build_graph(skills,list(zip(skills,skills[1:])))
    assert len(prerequisite_closure(g,[skills[-1]]))==1999
    assert len(topological_order(g,'dfs'))==2000


def test_random_dags_algorithms_and_permutation_invariance():
    rng=random.Random(2027)
    for _ in range(20):
        skills=[f's{i:02}' for i in range(15)]
        edges=[(a,b) for a,b in itertools.combinations(skills,2) if rng.random()<.15]
        source={s:rng.randint(0,4) for s in skills[:5]}
        target={s:rng.randint(1,4) for s in skills[5:]}
        weights={s:rng.random() for s in skills}
        a=compare(skills,edges,source,target,weights,Parameters(2,.8,'kahn'))
        b=compare(skills[::-1],edges[::-1],source,target,weights,Parameters(2,.8,'dfs'))
        for key in ['M1','M2','M3','prerequisite_burden']:
            assert a[key]==b[key]
        assert a['M3']>=a['M2']>=0
        g=build_graph(skills,edges)
        order=topological_order(g,'dfs')
        assert all(order.index(u)<order.index(v) for u,v in g.edges)
        expected=set().union(*(nx.ancestors(g,n) for n in a['missing_skills']))
        assert set(a['prerequisite_skills'])==expected


def test_independent_m1_m2_m3_functions():
    from app.research.models import m1_unweighted_gap, m2_weighted_gap, m3_prerequisite_aware_gap
    deficits={'a':2,'b':0,'c':1}
    weights={'a':.5,'b':1,'c':1}
    assert m1_unweighted_gap(deficits)==2
    assert m2_weighted_gap(deficits,weights)==.5
    score,burden=m3_prerequisite_aware_gap(.5,{'d':2},{'d':.4},.5)
    assert burden==.2
    assert score==.6
