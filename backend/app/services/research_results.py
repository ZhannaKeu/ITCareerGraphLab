"""Descriptive analyses of unchanged M1/M2/M3; no empirical efficacy claims."""
import hashlib
import json
import math
import platform
from collections import defaultdict
import numpy as np
from sqlalchemy.exc import IntegrityError
from ..models import ExperimentRun
from .experiments import execute_run

ANALYSIS_VERSION = "1.0.0"
RANK_RULE = "ascending distance; exact ties use average ranks for Spearman, target ID for deterministic Top-K"


def average_ranks(values):
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    ranks = [0.] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + 1 + end) / 2
        for i in order[start:end]:
            ranks[i] = rank
        start = end
    return ranks


def ranking_comparison(results, top_k=3):
    sources = defaultdict(list)
    for r in results:
        sources[r['source_profile']].append(r)
    output = []
    for source, rows in sorted(sources.items()):
        rows = sorted(rows, key=lambda r: r['target_profile'])
        m2, m3 = [r['M2'] for r in rows], [r['M3'] for r in rows]
        a, b = average_ranks(m2), average_ranks(m3)
        correlation = None
        if len(rows) >= 2 and len(set(a)) > 1 and len(set(b)) > 1:
            correlation = float(np.corrcoef(a, b)[0, 1])
        top2 = [r['target_profile'] for r in sorted(rows, key=lambda r: (r['M2'], r['target_profile']))[:top_k]]
        top3 = [r['target_profile'] for r in sorted(rows, key=lambda r: (r['M3'], r['target_profile']))[:top_k]]
        k = min(top_k, len(rows))
        output.append({'source_profile': source, 'spearman': correlation,
            'top_k': k, 'top_m2': top2, 'top_m3': top3,
            'overlap': len(set(top2) & set(top3)) / k if k else None,
            'targets': [{'target_profile': r['target_profile'], 'M2': r['M2'], 'M3': r['M3'],
                         'rank_m2': a[i], 'rank_m3': b[i], 'rank_shift': a[i] - b[i]} for i, r in enumerate(rows)]})
    return output


def deficit_distribution(results, bins=8):
    values = [r['M3'] - r['M2'] for r in results]
    positive = [v for v in values if v > 0]
    maximum = max(positive, default=0.)
    output = [{'label': '= 0', 'lower': 0., 'upper': 0., 'count': sum(v == 0 for v in values)}]
    if maximum:
        width = maximum / bins
        counts = [0] * bins
        for value in positive:
            counts[min(bins - 1, int(value / width))] += 1
        output.extend({'label': f'{i*width:.3g}–{(i+1)*width:.3g}', 'lower': i*width,
                       'upper': (i+1)*width, 'count': count} for i, count in enumerate(counts))
    return output


def summarize(results, top_k):
    extras = [r['M3'] - r['M2'] for r in results]
    ranks = ranking_comparison(results, top_k)
    defined = [r['spearman'] for r in ranks if r['spearman'] is not None]
    return {'pairs': len(results), 'affected_pairs': sum(d > 0 for d in extras),
        'mean_extra': math.fsum(extras) / len(extras), 'max_extra': max(extras, default=0),
        'mean_M2': math.fsum(r['M2'] for r in results) / len(results),
        'mean_M3': math.fsum(r['M3'] for r in results) / len(results),
        'mean_spearman': math.fsum(defined) / len(defined) if defined else None,
        'undefined_spearman_sources': len(ranks) - len(defined),
        'mean_top_k_overlap': math.fsum(r['overlap'] for r in ranks) / len(ranks)}


def execute_research(session, snapshot, request):
    baseline = execute_run(session, snapshot, request.experiment, 'batch')
    params = {'experiment': baseline['provenance']['parameters'], 'taus': request.taus,
              'lambdas': request.lambdas, 'top_k': request.top_k}
    canonical = {'dataset': snapshot.version.id, 'record_hash': snapshot.metadata['record_hash'],
        'parameters': params, 'implementation': baseline['provenance']['implementation'],
        'experiment_kind': 'research', 'analysis_version': ANALYSIS_VERSION}
    run_id = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    saved = session.get(ExperimentRun, run_id)
    if saved:
        return saved.payload
    points = []
    for tau in request.taus:
        for lambda_ in request.lambdas:
            modified = request.experiment.model_copy(update={'minimum_prerequisite_level': tau, 'lambda_': lambda_})
            batch = execute_run(session, snapshot, modified, 'batch')
            points.append({'tau': tau, 'lambda': lambda_, 'run_id': batch['provenance']['run_id'],
                           **summarize(batch['results'], request.top_k)})
    results = baseline['results']
    extra = sorted([{'source_profile': r['source_profile'], 'target_profile': r['target_profile'],
                     'M1': r['M1'], 'M2': r['M2'], 'M3': r['M3'], 'extra': r['M3'] - r['M2']} for r in results],
                    key=lambda r: (-r['extra'], r['source_profile'], r['target_profile']))
    meta = {**baseline['provenance'], **canonical, 'run_id': run_id, 'baseline_run_id': baseline['provenance']['run_id'],
        'analysis_rules': {'ranking': RANK_RULE, 'extra': 'M3 - M2 = lambda * additional prerequisite burden',
                           'histogram': 'explicit zero bucket; 8 equal-width positive bins; last includes maximum',
                           'diagonal': 'undefined/excluded, never imputed as zero'},
        'runtime': baseline['provenance']['runtime'],
        'analysis_runtime': {'python': platform.python_version(), 'numpy': np.__version__}}
    payload = {'baseline': baseline, 'provenance': meta, 'max_extra': extra,
               'distribution': deficit_distribution(results), 'ranking': ranking_comparison(results, request.top_k),
               'sensitivity': points, 'summary': summarize(results, request.top_k)}
    try:
        with session.begin_nested():
            session.add(ExperimentRun(id=run_id, version_id=snapshot.version.id, kind='research', parameters=params, payload=payload))
            session.flush()
    except IntegrityError:
        existing = session.get(ExperimentRun, run_id)
        if existing is None: raise
        return existing.payload
    session.commit()
    return payload
