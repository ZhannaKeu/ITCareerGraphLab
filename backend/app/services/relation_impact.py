"""Controlled relation-type experiment over unchanged M1/M2/M3 functions."""
import math
import platform
from collections import defaultdict
import numpy as np
from sqlalchemy.exc import IntegrityError
from ..models import ExperimentRun
from .experiments import execute_run
from .relation_graphs import digest, graph_configuration
from .research_results import average_ranks

TITLE = 'Impact of Prerequisite Relation Types on Weighted IT Career Transition Modeling'
ANALYSIS_VERSION = 'relation-impact-1.0.0'
GRAPHS = ('G1','G2','G3')


def kendall_tau_b(x,y):
    if len(x)!=len(y): raise ValueError('Rank vectors must have equal lengths')
    concordant=discordant=tie_x=tie_y=0
    for i in range(len(x)):
        for j in range(i+1,len(x)):
            a=(x[i]>x[j])-(x[i]<x[j]); b=(y[i]>y[j])-(y[i]<y[j])
            if a==0 and b==0: continue
            if a==0: tie_x+=1
            elif b==0: tie_y+=1
            elif a==b: concordant+=1
            else: discordant+=1
    denominator=math.sqrt((concordant+discordant+tie_x)*(concordant+discordant+tie_y))
    return (concordant-discordant)/denominator if denominator else None


def correlations(x,y):
    a,b=average_ranks(x),average_ranks(y)
    spearman=float(np.corrcoef(a,b)[0,1]) if len(x)>1 and len(set(a))>1 and len(set(b))>1 else None
    return spearman,kendall_tau_b(x,y)


def compare_rankings(left,right,left_metric='M3',right_metric='M3'):
    left_index={(r['source_profile'],r['target_profile']):r for r in left}
    right_index={(r['source_profile'],r['target_profile']):r for r in right}
    if left_index.keys()!=right_index.keys(): raise ValueError('Directed pair populations must match')
    grouped=defaultdict(list)
    for source,target in sorted(left_index): grouped[source].append(target)
    sources=[]
    for source,targets in sorted(grouped.items()):
        x=[left_index[source,t][left_metric] for t in targets]
        y=[right_index[source,t][right_metric] for t in targets]
        spearman,kendall=correlations(x,y)
        a=sorted(targets,key=lambda t:(left_index[source,t][left_metric],t))
        b=sorted(targets,key=lambda t:(right_index[source,t][right_metric],t))
        row={'source_profile':source,'spearman':spearman,'kendall_tau_b':kendall}
        for k in (3,5):
            n=min(k,len(targets)); sa,sb=a[:n],b[:n]
            row.update({f'top{k}_left':sa,f'top{k}_right':sb,f'top{k}_overlap':len(set(sa)&set(sb))/n,
                        f'top{k}_membership_changed':set(sa)!=set(sb),f'top{k}_order_changed':sa!=sb})
        sources.append(row)
    summary={}
    for metric in ('spearman','kendall_tau_b'):
        defined=[s[metric] for s in sources if s[metric] is not None]
        summary[f'mean_{metric}']=math.fsum(defined)/len(defined) if defined else None
        summary[f'undefined_{metric}_sources']=len(sources)-len(defined)
    for k in (3,5):
        summary.update({f'mean_top{k}_overlap':math.fsum(s[f'top{k}_overlap'] for s in sources)/len(sources),
            f'top{k}_membership_changed_sources':sum(s[f'top{k}_membership_changed'] for s in sources),
            f'top{k}_order_changed_sources':sum(s[f'top{k}_order_changed'] for s in sources)})
    deltas=[right_index[p][right_metric]-left_index[p][left_metric] for p in sorted(left_index)]
    summary.update(changed_pairs=sum(d!=0 for d in deltas),mean_score_change=math.fsum(deltas)/len(deltas),
                   max_absolute_score_change=max(map(abs,deltas),default=0))
    return {'summary':summary,'sources':sources}


def summary(results,name,config):
    burden=[r['prerequisite_burden'] for r in results]
    extra=[r['M3']-r['M2'] for r in results]
    return {'graph':name,'configuration_hash':config['configuration_hash'],'nodes':config['node_count'],'edges':config['edge_count'],
        'pairs':len(results),'prerequisite_deficit_pairs':sum(v>0 for v in burden),
        'weighted_extra_pairs':sum(v>0 for v in extra),'mean_burden':math.fsum(burden)/len(burden),'max_burden':max(burden),
        'mean_extra':math.fsum(extra)/len(extra),'max_extra':max(extra),
        'mean_M2':math.fsum(r['M2'] for r in results)/len(results),'mean_M3':math.fsum(r['M3'] for r in results)/len(results)}


def assert_common_baseline(runs):
    baseline={(r['source_profile'],r['target_profile']):(r['M1'],r['M2']) for r in runs['G1']['results']}
    if len(baseline)!=182: raise ValueError('Controlled relation experiment requires exactly 14 profiles and 182 directed pairs')
    for name in GRAPHS[1:]:
        actual={(r['source_profile'],r['target_profile']):(r['M1'],r['M2']) for r in runs[name]['results']}
        if actual!=baseline: raise ValueError('M1/M2 baseline changed across graphs; controlled comparison rejected')


def common_distributions(runs):
    maximum=max(r['M3']-r['M2'] for run in runs.values() for r in run['results'])
    output={}
    for name,run in runs.items():
        values=[r['M3']-r['M2'] for r in run['results']]
        buckets=[{'label':'= 0','lower':0.,'upper':0.,'count':sum(v==0 for v in values)}]
        if maximum>0:
            width=maximum/8; counts=[0]*8
            for v in values:
                if v>0: counts[min(7,int(v/width))]+=1
            buckets.extend({'label':f'{i*width:.3g}–{(i+1)*width:.3g}','lower':i*width,'upper':(i+1)*width,'count':count} for i,count in enumerate(counts))
        output[name]=buckets
    return output


def execute_relation_impact(session,snapshot,request):
    configs={name:graph_configuration(snapshot,name) for name in GRAPHS}
    if len(snapshot.profiles)!=14: raise ValueError('G1/G2/G3 experiment requires 14 professional profiles')
    experiment=request.experiment.model_copy(update={'version_id':snapshot.version.id})
    params=experiment.model_dump(mode='json',by_alias=True)
    params.pop('graph_configuration',None)
    canonical={'dataset':snapshot.version.id,'record_hash':snapshot.metadata['record_hash'],
        'classification_hash':snapshot.classification['classification_hash'],
        'configuration_hashes':{g:c['configuration_hash'] for g,c in configs.items()},
        'parameters':{'experiment':params,'taus':request.taus,'lambdas':request.lambdas},
        'implementation':'1.1.0','analysis_version':ANALYSIS_VERSION,'experiment_kind':'relation_impact'}
    run_id=digest(canonical)
    existing=session.get(ExperimentRun,run_id)
    if existing: return existing.payload
    def calculate(tau,lambda_):
        runs={name:execute_run(session,snapshot,experiment.model_copy(update={
            'graph_configuration':name,'minimum_prerequisite_level':tau,'lambda_':lambda_}),'batch') for name in GRAPHS}
        assert_common_baseline(runs)
        return runs
    runs=calculate(experiment.minimum_prerequisite_level,experiment.lambda_)
    common_m2={(r["source_profile"],r["target_profile"]):r["M2"] for r in runs["G1"]["results"]}
    comparisons={f'{a}_{b}':compare_rankings(runs[a]['results'],runs[b]['results']) for a,b in [('G1','G2'),('G1','G3'),('G2','G3')]}
    against_m2={name:compare_rankings(runs['G1']['results'],runs[name]['results'],'M2','M3') for name in GRAPHS}
    index={g:{(r['source_profile'],r['target_profile']):r for r in runs[g]['results']} for g in GRAPHS}
    transitions=[]
    for source,target in sorted(index['G1']):
        row={'source_profile':source,'target_profile':target,'M2':index['G1'][source,target]['M2']}
        for g in GRAPHS:
            r=index[g][source,target]
            row.update({f'M3_{g}':r['M3'],f'burden_{g}':r['prerequisite_burden'],f'extra_{g}':r['M3']-r['M2']})
        row.update(delta_G2_G1=row['M3_G2']-row['M3_G1'],delta_G3_G1=row['M3_G3']-row['M3_G1'])
        transitions.append(row)
    points=[]; sensitivity_comparisons=[]
    for tau in request.taus:
        for lambda_ in request.lambdas:
            cells=calculate(tau,lambda_)
            if {(r["source_profile"],r["target_profile"]):r["M2"] for r in cells["G1"]["results"]} != common_m2:
                raise ValueError("Common M2 baseline changed across sensitivity scenarios")
            for g in GRAPHS:
                points.append({'tau':tau,'lambda':lambda_,'run_id':cells[g]['provenance']['run_id'],**summary(cells[g]['results'],g,configs[g])})
            for a,b in [('G1','G2'),('G1','G3'),('G2','G3')]:
                sensitivity_comparisons.append({'tau':tau,'lambda':lambda_,'comparison':f'{a}_{b}',
                    **compare_rankings(cells[a]['results'],cells[b]['results'])['summary']})
    meta={**runs['G1']['provenance'],**canonical,'run_id':run_id,'title':TITLE,
        'analysis_runtime':{'python':platform.python_version(),'numpy':np.__version__},
        'rules':{'min_level':'All edge-specific min_level values are null; global tau is a scenario assumption, not a confirmed edge threshold',
            'M2':'Exact common baseline across all configurations; checked for every pair and every sensitivity cell',
            'ranking':'Ascending scores; average ranks for exact ties; lexical profile ID for Top-3/5 membership',
            'kendall':'Kendall tau-b with separate x/y ties; null when denominator is zero',
            'histogram':'Shared positive-bin boundaries across G1/G2/G3; exact zero bucket; final upper boundary inclusive',
            'counts':'prerequisite_deficit_pairs counts unscaled B>0; weighted_extra_pairs counts M3-M2>0 (different when lambda=0)',
            'interpretation':'Sensitivity to preliminary relation labels is not evidence of recommendation quality'},
        'graph_configuration':None,
        'included_edge_ids':{g:c['included_edge_ids'] for g,c in configs.items()},
        'classification_source':'AI-assisted preliminary review','classification_verification_status':'Unverified'}
    payload={'provenance':meta,'configurations':configs,'runs':runs,
        'summary':[summary(runs[g]['results'],g,configs[g]) for g in GRAPHS],
        'transitions':transitions,'comparisons':comparisons,'against_M2':against_m2,
        'distributions':common_distributions(runs),
        'sensitivity':points,'sensitivity_comparisons':sensitivity_comparisons}
    try:
        with session.begin_nested():
            session.add(ExperimentRun(id=run_id,version_id=snapshot.version.id,kind='relation_impact',parameters=canonical['parameters'],payload=payload))
            session.flush()
    except IntegrityError:
        saved=session.get(ExperimentRun,run_id)
        if saved is None: raise
        return saved.payload
    session.commit()
    return payload
