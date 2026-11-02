"""Independent uncertainty interventions through temporary snapshots, unchanged model engine."""
import csv
import io
import json
import math
import platform
from collections import Counter
from dataclasses import replace
from types import SimpleNamespace
from sqlalchemy.exc import IntegrityError
from ..api.schemas import ExperimentRequest
from ..models import ExperimentRun
from .experiments import run_experiment
from .relation_graphs import digest, graph_configuration
from .relation_impact import compare_rankings
from .research_results import average_ranks

PROTOCOL = 'experiment3-robustness-1.0.0'
CONTROLS = ((1.,1.),(2.,1.),(3.,1.),(4.,1.),(4.,2.))
FINAL = 'skill_weights_by_role_final_v2.csv'
ALTERNATIVE = 'role_skill_weights.csv'
EXPORTS = tuple(f'experiment3-{name}.csv' for name in ('summary','results','rankings','edges')) + ('experiment3-results.json',)
RULES = {
    'independence': 'A changes only missing source proficiency; B only target-role weights; C only one G1 edge. Never combined.',
    'source_unknown': 'Absent individual skill requirements and explicit null source levels are unknown. A0=0, A1=1, A2=2 are assumptions, never observations. Known zeros stay zero. Unknown target=4 unchanged; groups excluded.',
    'weights': 'B0 Final v2 MAX after skill_mapping; B1 role_skill_weights as imported; B2 unit weight=1 for every skill/role, no fallback. No rescaling or cross-file mixing. Existing missing-weight fallback=1 reported separately.',
    'weight_scale': 'B absolute score changes include differences in overall weight mass, not solely relative importance. Unit weights and file weights are different assumptions, not empirically calibrated common scales.',
    'rankings': 'Per source, 13 targets, ascending distance; average ties for Spearman, Kendall tau-b; null for undefined correlations, excluded from means with counts; lexical target ID for Top-K.',
    'differences': 'scenario minus matched baseline at identical graph/tau/lambda. Signed mean and mean/max absolute differences are separate. Rankings compared for BOTH M2 and M3.',
    'edge_influence': '51 leave-one-edge-out scenarios per control, all 71 nodes retained. Edge influence ranks separately by M3 mean absolute change, Spearman loss, Top-3 and Top-5 membership change; lexical edge ID breaks ties.',
}


def temporary_snapshot(snapshot, source_id, unknown_level=0, weight_mode='B0'):
    """Only transient Python records; never alter ORM objects or dataset annotations."""
    reqs = list(snapshot.requirements)
    if unknown_level:
        source = {r.skill_id:r.required_level for r in reqs if r.profile_id==source_id and r.skill_id is not None}
        reqs = [r for r in reqs if not (r.profile_id==source_id and r.skill_id is not None and r.required_level is None)]
        reqs += [SimpleNamespace(profile_id=source_id,skill_id=s.id,group_id=None,required_level=unknown_level)
                 for s in snapshot.skills if source.get(s.id) is None]
    weights = snapshot.weights
    if weight_mode == 'B2':
        weights = [SimpleNamespace(source=FINAL,role=role,skill_id=s.id,weight=1.)
                   for role in sorted({p.role for p in snapshot.profiles}) for s in snapshot.skills]
    return replace(snapshot, requirements=reqs, weights=weights)


def calculate_scenario(snapshot, config, tau, lambda_, unknown_level=0, weight_mode='B0', excluded_edge=None):
    """Delegate every transition to run_experiment -> existing compare/M1/M2/M3."""
    profiles = sorted(p.id for p in snapshot.profiles)
    request = ExperimentRequest(source_profile=profiles[0],target_profile=profiles[1],version_id=snapshot.version.id,
        minimum_prerequisite_level=tau,lambda_=lambda_,algorithm='kahn',verification_scope='all',
        weight_source=ALTERNATIVE if weight_mode=='B1' else FINAL,
        graph_configuration=None if excluded_edge else config['name'],
        excluded_edges=[excluded_edge] if excluded_edge else [])
    original = {p:{r.skill_id:r.required_level for r in snapshot.requirements if r.profile_id==p and r.skill_id is not None} for p in profiles}
    skills = {s.id for s in snapshot.skills}
    output = []
    for source in profiles:
        transient = temporary_snapshot(snapshot,source,unknown_level,weight_mode)
        unknown = {s for s in skills if original[source].get(s) is None}
        for target in profiles:
            if source == target: continue
            result = run_experiment(transient,request,source,target)
            consulted = set(original[target]) | set(result['prerequisite_skills'])
            unknown_used = sorted(unknown & consulted)
            output.append({k:result[k] for k in ('source_profile','target_profile','M1','M2','M3','prerequisite_burden','weighted_prerequisite_burden')}
                | {'unknown_source_count':len(unknown_used), 'unknown_source_skills':unknown_used,
                   'unknown_source_population_count':len(unknown), 'assumed_source_count':len(unknown_used) if unknown_level else 0,
                   'unknown_target_count':len(result['unknown_target_skills']),
                   'fallback_weight_count':len(result['fallback_weight_skills']), 'fallback_weight_skills':result['fallback_weight_skills']})
    return output


def comparison_metrics(baseline, results):
    index = {(r['source_profile'],r['target_profile']):r for r in baseline}
    metrics = {'pairs':len(results),
        'unknown_source_occurrences':sum(r['unknown_source_count'] for r in results),
        'assumed_source_occurrences':sum(r['assumed_source_count'] for r in results),
        'fallback_weight_occurrences':sum(r['fallback_weight_count'] for r in results),
        'pairs_with_unknown_source':sum(r['unknown_source_count']>0 for r in results),
        'pairs_with_fallback_weights':sum(r['fallback_weight_count']>0 for r in results)}
    comparisons = {}
    for model in ('M2','M3'):
        cmp = compare_rankings(baseline,results,model,model)
        differences = [r[model]-index[r['source_profile'],r['target_profile']][model] for r in results]
        metrics[model] = {**cmp['summary'], 'mean':math.fsum(r[model] for r in results)/len(results),
            'baseline_mean':math.fsum(r[model] for r in baseline)/len(baseline),
            'mean_difference':math.fsum(differences)/len(differences),
            'mean_absolute_difference':math.fsum(map(abs,differences))/len(differences),
            'max_absolute_difference':max(map(abs,differences)),
            'top3_replaced_targets':sum(len(set(s['top3_left'])-set(s['top3_right'])) for s in cmp['sources']),
            'top5_replaced_targets':sum(len(set(s['top5_left'])-set(s['top5_right'])) for s in cmp['sources'])}
        comparisons[model] = cmp['sources']
    return metrics, comparisons


def weight_diagnostics(snapshot):
    rows=[]
    for mode,source in (('B0',FINAL),('B1',ALTERNATIVE),('B2','unit')):
        for role in sorted({p.role for p in snapshot.profiles}):
            values = [1. for _ in snapshot.skills] if mode=='B2' else [w.weight for w in snapshot.weights if w.source==source and w.role==role]
            if not values: raise ValueError(f'No {source} weights for role {role}')
            rows.append({'variant':mode,'source':source,'role':role,'count':len(values),'minimum':min(values),'maximum':max(values),
                         'sum':math.fsum(values),'mean':math.fsum(values)/len(values),'normalization':'none'})
    return rows


def edge_influence(scenarios):
    rows=[]
    for tau,lambda_ in CONTROLS:
        cells=[s for s in scenarios if s['study']=='C' and s['tau']==tau and s['lambda']==lambda_]
        criteria={'score':'mean_absolute_difference','ranking':'mean_spearman','top3':'top3_membership_changed_sources','top5':'top5_membership_changed_sources'}
        ranks={}
        for name,metric in criteria.items():
            available=[s for s in cells if s['metrics']['M3'][metric] is not None]
            ordered=sorted(available,key=lambda s:((s['metrics']['M3'][metric] if name=='ranking' else -s['metrics']['M3'][metric]),s['excluded_edge_id']))
            ranks[name]={s['id']:i+1 for i,s in enumerate(ordered)}
        rows.extend({k:s[k] for k in ('id','tau','lambda','excluded_edge_id','excluded_edge','configuration_hash','baseline_id')}
            | s['metrics']['M3'] | {f'{name}_rank':rank.get(s['id']) for name,rank in ranks.items()} for s in cells)
    return rows


def execute_experiment3(session,snapshot):
    if len(snapshot.profiles)!=14: raise ValueError('Experiment 3 requires 14 profiles / 182 directed transitions')
    configs={g:graph_configuration(snapshot,g) for g in ('G1','G2','G3')}
    if configs['G1']['edge_count']!=51: raise ValueError('G1 must contain exactly 51 original edges')
    diagnostics=weight_diagnostics(snapshot)
    parameters={'controls':[{'tau':t,'lambda':l,'stress':l==2} for t,l in CONTROLS], 'graphs':['G1','G2','G3'],
        'studies':{'A':['A0','A1','A2'],'B':['B0','B1','B2'],'C':'G1 leave-one-edge-out, 51 edges'},
        'algorithm':'kahn','tie_break':'lexicographic','verification_scope':'all','normalization':'none',
        'profile_ids':sorted(p.id for p in snapshot.profiles),'rules':RULES,'scenario_count':345}
    canonical={'dataset':snapshot.version.id,'record_hash':snapshot.metadata['record_hash'],
        'source_data_hash':digest(snapshot.version.manifest),'classification_hash':snapshot.classification['classification_hash'],
        'configuration_hashes':{g:c['configuration_hash'] for g,c in configs.items()},'parameters':parameters,
        'implementation':'1.1.0','analysis_version':PROTOCOL,'experiment_kind':'experiment3'}
    run_id=digest(canonical)
    saved=session.get(ExperimentRun,run_id)
    if saved: return saved.payload
    edge_configs={}
    for e in configs['G1']['edges']:
        c={k:v for k,v in configs['G1'].items() if k!='configuration_hash'}
        c.update(name='G1-LOO',parent_configuration_hash=configs['G1']['configuration_hash'],excluded_edge_ids=[e['edge_id']],
            included_edge_ids=[i for i in c['included_edge_ids'] if i!=e['edge_id']],edges=[r for r in c['edges'] if r['edge_id']!=e['edge_id']],edge_count=50)
        c['relation_counts']=dict(Counter(r['relation_type'] for r in c['edges']))
        edge_configs[e['edge_id']]={**c,'configuration_hash':digest(c)}
    def descriptor(study,variant,graph,tau,lambda_,edge=None):
        config=edge_configs[edge['edge_id']] if edge else configs[graph]
        d={'study':study,'variant':variant,'graph':graph,'tau':tau,'lambda':lambda_,
           'unknown_source_level':int(variant[-1]) if study=='A' else 0,
           'weight_mode':variant if study=='B' else 'B0',
           'weight_source':ALTERNATIVE if variant=='B1' else 'unit' if variant=='B2' else FINAL,
           'excluded_edge_id':edge['edge_id'] if edge else None,
           'excluded_edge':[edge['from_skill'],edge['to_skill']] if edge else None,
           'configuration_hash':config['configuration_hash']}
        return {'id':digest({'parent_run':run_id,**d}),**d}
    baselines={(g,t,l):calculate_scenario(snapshot,configs[g],t,l) for g in configs for t,l in CONTROLS}
    specs=[descriptor(study,variant,g,t,l) for study in ('A','B') for variant in parameters['studies'][study] for g in configs for t,l in CONTROLS]
    specs += [descriptor('C','LOO','G1',t,l,e) for e in configs['G1']['edges'] for t,l in CONTROLS]
    scenarios=[]
    for d in specs:
        baseline=baselines[d['graph'],d['tau'],d['lambda']]
        original=d['variant'] in ('A0','B0')
        results=baseline if original else calculate_scenario(snapshot,configs[d['graph']],d['tau'],d['lambda'],d['unknown_source_level'],d['weight_mode'],d['excluded_edge'])
        if len(results)!=182 or any(r['M3']<r['M2'] for r in results): raise ValueError('Model invariant/population contradiction')
        if d['study']=='C' and any(r['M2']!=b['M2'] for r,b in zip(results,baseline)): raise ValueError('Edge removal changed M2')
        metrics,rankings=comparison_metrics(baseline,results)
        base=descriptor('B' if d['study']=='B' else 'A','B0' if d['study']=='B' else 'A0',d['graph'],d['tau'],d['lambda'])
        baseline_index={(r['source_profile'],r['target_profile']):r for r in baseline}
        pair_results=[{**r,'baseline_M2':baseline_index[r['source_profile'],r['target_profile']]['M2'],
                          'baseline_M3':baseline_index[r['source_profile'],r['target_profile']]['M3']} for r in results]
        scenarios.append({**d,'baseline_id':base['id'],'baseline_configuration_hash':configs[d['graph']]['configuration_hash'],
            'metrics':metrics,'rankings':rankings,'results':pair_results})
    payload={'provenance':{**canonical,'run_id':run_id,'input_manifest':snapshot.version.manifest,
        'data_provenance':snapshot.metadata,'runtime':{'python':platform.python_version()},
        'warning':'Unverified research inputs. Alternative source levels are assumptions, not observations. Robustness is not recommendation correctness.'},
        'configurations':configs,'edge_configurations':edge_configs,'weight_diagnostics':diagnostics,
        'scenario_count':len(scenarios),'scenarios':scenarios,'edge_influence':edge_influence(scenarios)}
    try:
        with session.begin_nested():
            session.add(ExperimentRun(id=run_id,version_id=snapshot.version.id,kind='experiment3',parameters=parameters,payload=payload));session.flush()
    except IntegrityError:
        saved=session.get(ExperimentRun,run_id)
        if saved is None: raise
        return saved.payload
    session.commit()
    return payload


def export_rows(payload,table):
    p=payload['provenance']
    common={k:p[k] for k in ('run_id','dataset','source_data_hash','record_hash','classification_hash','implementation','analysis_version')}
    common.update(algorithm='kahn_lexicographical',verification_scope='all',normalization='none',input_warning=p['warning'])
    if table=='edges': return [{**common,'study':'C','graph':'G1','weight_mode':'B0','weight_source':FINAL,
        'weight_rule':'MAX(weight_0_1) after skill_mapping; fallback=1','unknown_source_level':0,
        'baseline_configuration_hash':payload['configurations']['G1']['configuration_hash'],**r} for r in payload['edge_influence']]
    rows=[]
    for s in payload['scenarios']:
        meta={**common,**{k:v for k,v in s.items() if k not in ('metrics','rankings','results')},
            'weight_rule':'unit weights=1; complete coverage' if s['weight_mode']=='B2' else 'imported weight; fallback=1' if s['weight_mode']=='B1' else 'MAX(weight_0_1) after skill_mapping; fallback=1'}
        if table=='summary':
            rows.append({**meta,**{k:v for k,v in s['metrics'].items() if k not in ('M2','M3')},
                **{f'{model}_{k}':v for model in ('M2','M3') for k,v in s['metrics'][model].items()}})
        elif table=='results': rows.extend({**meta,**r,'M2_difference':r['M2']-r['baseline_M2'],'M3_difference':r['M3']-r['baseline_M3']} for r in s['results'])
        elif table=='rankings':
            for model in ('M2','M3'):
                for rank in s['rankings'][model]:
                    targets=sorted((r for r in s['results'] if r['source_profile']==rank['source_profile']),key=lambda r:r['target_profile'])
                    a=average_ranks([r[f'baseline_{model}'] for r in targets]);b=average_ranks([r[model] for r in targets])
                    rows.append({**meta,'model':model,**rank,'target_ranks':[{'target':r['target_profile'],'baseline_rank':a[i],'scenario_rank':b[i]} for i,r in enumerate(targets)]})
        else: raise ValueError('Unknown Experiment 3 table')
    return rows


def export_file(payload,filename):
    if filename not in EXPORTS: raise ValueError('Unknown Experiment 3 export')
    if filename.endswith('.json'): return json.dumps(payload,ensure_ascii=False,sort_keys=True,allow_nan=False),'application/json'
    rows=export_rows(payload,filename.removeprefix('experiment3-').removesuffix('.csv'))
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
    writer.writeheader();writer.writerows({k:json.dumps(v,ensure_ascii=False,allow_nan=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows)
    return stream.getvalue(),'text/csv; charset=utf-8'
