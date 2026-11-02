"""Experiment 2: fixed 60-cell protocol, reusing existing controlled M3 batches."""
import csv
import io
import json
import platform
from sqlalchemy.exc import IntegrityError
from ..api.schemas import ExperimentRequest, RelationImpactRequest
from ..models import ExperimentRun
from .relation_graphs import digest, graph_configuration
from .research_results import average_ranks
from .relation_impact import GRAPHS, compare_rankings, execute_relation_impact

TAUS = (1., 2., 3., 4.)
LAMBDAS = (0., .25, .5, 1., 2.)
PROTOCOL = 'experiment2-sensitivity-1.0.0'
TITLE = 'Experiment 2 — Parameter Sensitivity Analysis'
EXPORTS = ('experiment2-summary.csv', 'experiment2-scenarios.csv', 'experiment2-rankings.csv', 'experiment2-results.json')


def execute_experiment2(session, snapshot):
    profiles = sorted(p.id for p in snapshot.profiles)
    if len(profiles) != 14:
        raise ValueError('Experiment 2 requires 14 profiles and 182 directed transitions')
    configurations = {g: graph_configuration(snapshot, g) for g in GRAPHS}
    template = ExperimentRequest(source_profile=profiles[0], target_profile=profiles[1],
        version_id=snapshot.version.id, minimum_prerequisite_level=1, lambda_=0,
        algorithm='kahn', weight_source='skill_weights_by_role_final_v2.csv',
        verification_scope='all', included_edges=[], excluded_edges=[])
    parameters = {'experiment': template.model_dump(mode='json', by_alias=True, exclude={'graph_configuration'}),
        'graphs': list(GRAPHS), 'taus': list(TAUS), 'lambdas': list(LAMBDAS),
        'profile_ids': profiles, 'weight_rule': 'MAX(weight_0_1) after canonical skill mapping; explicit unit fallback unchanged',
        'top_k': [3, 5], 'scenario_count': 60}
    canonical = {'dataset': snapshot.version.id, 'record_hash': snapshot.metadata['record_hash'],
        'source_data_hash': digest(snapshot.version.manifest), 'classification_hash': snapshot.classification['classification_hash'],
        'configuration_hashes': {g: c['configuration_hash'] for g, c in configurations.items()},
        'parameters': parameters, 'implementation': '1.1.0', 'analysis_version': PROTOCOL, 'experiment_kind': 'experiment2'}
    run_id = digest(canonical)
    existing = session.get(ExperimentRun, run_id)
    if existing:
        return existing.payload
    # The established G1/G2/G3 engine executes and persists every scenario.
    study = execute_relation_impact(session, snapshot, RelationImpactRequest(experiment=template,
        taus=list(TAUS), lambdas=list(LAMBDAS)))
    baseline = {(r['source_profile'], r['target_profile']): r['M2'] for r in study['runs']['G1']['results']}
    expected_pairs = {(a, b) for a in profiles for b in profiles if a != b}
    scenarios, rankings, graph_rankings = [], [], []
    point_index = {(p['graph'], p['tau'], p['lambda']): p for p in study['sensitivity']}
    if len(point_index) != 60:
        raise ValueError('Controlled engine did not produce exactly 60 unique scenarios')
    for graph in GRAPHS:
        for tau in TAUS:
            for lambda_ in LAMBDAS:
                point = point_index[graph, tau, lambda_]
                saved = session.get(ExperimentRun, point['run_id'])
                if saved is None:
                    raise ValueError('Missing persisted scenario batch')
                batch = saved.payload
                results = batch['results']
                pairs = {(r['source_profile'], r['target_profile']) for r in results}
                if len(results) != 182 or pairs != expected_pairs:
                    raise ValueError('Scenario directed transition population differs from the fixed protocol')
                if {(r['source_profile'], r['target_profile']): r['M2'] for r in results} != baseline:
                    raise ValueError('Contradiction: M2 changed across graph or sensitivity parameters')
                if any(r['M3'] < r['M2'] or (lambda_ == 0 and r['M3'] != r['M2']) for r in results):
                    raise ValueError('Contradiction: unchanged M3 violates nonnegative-lambda or zero-lambda invariant')
                comparison = compare_rankings(results, results, 'M2', 'M3')
                changes = {}
                for k in (3, 5):
                    changes[f'top{k}_replaced_targets'] = sum(len(set(r[f'top{k}_left']) - set(r[f'top{k}_right'])) for r in comparison['sources'])
                descriptor = {'graph': graph, 'tau': tau, 'lambda': lambda_, 'scenario_run_id': point['run_id'],
                    'configuration_hash': configurations[graph]['configuration_hash']}
                compact = [{k: r[k] for k in ('source_profile', 'target_profile', 'M1', 'M2', 'M3', 'prerequisite_burden', 'weighted_prerequisite_burden')}
                           | {'extra': r['M3'] - r['M2'], 'unknown_source_count': len(r['unknown_source_skills']),
                              'unknown_target_count': len(r['unknown_target_skills']), 'fallback_weight_count': len(r['fallback_weight_skills'])} for r in results]
                scenarios.append({**descriptor, 'metrics': {k: v for k, v in point.items() if k not in ('graph', 'tau', 'lambda', 'run_id', 'configuration_hash')}
                    | comparison['summary'] | changes, 'results': compact})
                rankings.extend({**descriptor, **r, 'comparison_type': 'M2_vs_M3'} for r in comparison['sources'])
    # Same-tau/lambda graph comparisons use the same existing ranking implementation.
    lookup = {(s['graph'], s['tau'], s['lambda']): s for s in scenarios}
    for tau in TAUS:
        for lambda_ in LAMBDAS:
            for left, right in (('G1', 'G2'), ('G1', 'G3'), ('G2', 'G3')):
                a, b = lookup[left, tau, lambda_], lookup[right, tau, lambda_]
                cmp = compare_rankings(a['results'], b['results'])
                graph_rankings.extend({'tau': tau, 'lambda': lambda_, 'left_graph': left, 'right_graph': right,
                    'comparison': f'{left}_{right}', 'left_scenario_run_id': a['scenario_run_id'], 'right_scenario_run_id': b['scenario_run_id'],
                    'left_configuration_hash': a['configuration_hash'], 'right_configuration_hash': b['configuration_hash'],
                    'comparison_type': 'graph_vs_graph', **r} for r in cmp['sources'])
    comparisons = study['sensitivity_comparisons']
    provenance = {**study['provenance'], **canonical, 'run_id': run_id, 'title': TITLE,
        'controlled_study_run_id': study['provenance']['run_id'],
        'input_manifest': snapshot.version.manifest,
        'analysis_runtime': {'python': platform.python_version()},
        'rules': {**study['provenance']['rules'],
            'fixed_controls': 'G1/G2/G3; tau=1,2,3,4; lambda=0,.25,.5,1,2; final_v2 MAX; lexicographic Kahn; All incl Unverified; no overrides',
            'recommendation_changes': 'changed source profiles, changed order, and replaced Top-K targets are distinct; replacements count left-minus-right set size',
            'correlations': 'Per source; Spearman uses average ties, Kendall tau-b; undefined coefficients are null and excluded from means',
            'export_tables': 'summary=60 aggregates; scenarios=10920 pair rows; rankings=10920 M2/M3 + 10920 graph-comparison target-rank rows'},
        'warning': 'All inputs/classifications remain preliminary/Unverified. Stability is not evidence of recommendation efficacy or factual transition difficulty.'}
    payload = {'provenance': provenance, 'configurations': configurations, 'scenario_count': len(scenarios),
        'scenarios': scenarios, 'rankings': rankings, 'graph_rankings': graph_rankings, 'graph_comparisons': comparisons}
    try:
        with session.begin_nested():
            session.add(ExperimentRun(id=run_id, version_id=snapshot.version.id, kind='experiment2', parameters=parameters, payload=payload))
            session.flush()
    except IntegrityError:
        saved = session.get(ExperimentRun, run_id)
        if saved is None:
            raise
        return saved.payload
    session.commit()
    return payload


def export_rows(payload, table):
    """Pure export projection; old saved results are neither modified nor recalculated."""
    meta = payload['provenance']
    common = {'experiment_run_id': meta['run_id'], 'dataset_version': meta['dataset'], 'source_data_hash': meta['source_data_hash'],
        'record_hash': meta['record_hash'], 'classification_hash': meta['classification_hash'],
        'algorithm': 'kahn_lexicographical', 'model_implementation': meta['implementation'], 'analysis_version': meta['analysis_version'],
        'weight_source': 'skill_weights_by_role_final_v2.csv', 'weight_rule': 'MAX(weight_0_1)',
        'verification_scope': 'all', 'input_status': 'Unverified', 'manual_edge_overrides': 'none'}
    if table == 'summary':
        return [{**common, **{k: v for k, v in s.items() if k not in ('metrics', 'results')}, **s['metrics']} for s in payload['scenarios']]
    if table == 'scenarios':
        return [{**common, **{k: v for k, v in s.items() if k not in ('metrics', 'results')}, **r} for s in payload['scenarios'] for r in s['results']]
    if table == 'rankings':
        lookup = {(s['graph'],s['tau'],s['lambda']): s for s in payload['scenarios']}
        output = []
        for row in payload['rankings'] + payload['graph_rankings']:
            graph_comparison = row['comparison_type'] == 'graph_vs_graph'
            left_graph = row['left_graph'] if graph_comparison else row['graph']
            right_graph = row['right_graph'] if graph_comparison else row['graph']
            a = lookup[left_graph,row['tau'],row['lambda']]
            b = lookup[right_graph,row['tau'],row['lambda']]
            left_metric = 'M3' if graph_comparison else 'M2'
            left = {r['target_profile']: r[left_metric] for r in a['results'] if r['source_profile'] == row['source_profile']}
            right = {r['target_profile']: r['M3'] for r in b['results'] if r['source_profile'] == row['source_profile']}
            targets = sorted(left)
            ranks_left = average_ranks([left[t] for t in targets])
            ranks_right = average_ranks([right[t] for t in targets])
            output.extend({**common, **row, 'target_profile': target, 'left_metric': left_metric, 'right_metric': 'M3',
                'left_score': left[target], 'right_score': right[target], 'left_rank': ranks_left[i],
                'right_rank': ranks_right[i], 'rank_shift': ranks_left[i]-ranks_right[i],
                'left_top3': target in row['top3_left'], 'right_top3': target in row['top3_right'],
                'left_top5': target in row['top5_left'], 'right_top5': target in row['top5_right']}
                for i,target in enumerate(targets))
        return output
    raise ValueError('Unknown Experiment 2 export table')


def export_file(payload, filename):
    if filename not in EXPORTS:
        raise ValueError('Unknown Experiment 2 export file')
    if filename.endswith('.json'):
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False), 'application/json'
    table = filename.removeprefix('experiment2-').removesuffix('.csv')
    rows = export_rows(payload, table)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows({k: json.dumps(v, ensure_ascii=False, allow_nan=False) if isinstance(v, (dict, list)) else v for k, v in r.items()} for r in rows)
    return stream.getvalue(), 'text/csv; charset=utf-8'
