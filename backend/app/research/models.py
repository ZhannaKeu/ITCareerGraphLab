"""Pure deterministic models. Scores are dimensionless, never learning time."""
from dataclasses import dataclass
from .graph import build_graph, prerequisite_closure, topological_order

MAX_LEVEL = 4.0

@dataclass(frozen=True)
class Parameters:
    minimum_prerequisite_level: float = 1.0
    lambda_: float = 0.5
    algorithm: str = "kahn"


def m1_unweighted_gap(deficits):
    """Count skills with a positive direct proficiency deficit."""
    return float(sum(delta > 0 for delta in deficits.values()))


def m2_weighted_gap(deficits, weights):
    """Sum weighted deficits normalized by the declared maximum proficiency."""
    return sum(weights.get(skill, 1.0) * max(0.0, delta) / MAX_LEVEL
               for skill, delta in sorted(deficits.items()))


def m3_prerequisite_aware_gap(direct_score, additional_deficits, weights, lambda_):
    """Compose M2 with a separately measurable prerequisite burden."""
    burden = m2_weighted_gap(additional_deficits, weights)
    return direct_score + lambda_ * burden, burden


def compare(skills, edges, source, target, weights, params=Parameters()):
    if not 0 <= params.minimum_prerequisite_level <= MAX_LEVEL or not 0 <= params.lambda_ <= 10:
        raise ValueError("Invalid research parameters")
    graph = build_graph(skills, edges)
    unknown_source, unknown_target = set(), set()

    def known(skill):
        # An absent source requirement is UNKNOWN, not evidence of no proficiency.
        value = source.get(skill)
        if value is None:
            unknown_source.add(skill)
            return 0.0  # Explicit lower-bound scenario, reported to the caller.
        return value

    required = {}
    for skill, value in sorted(target.items()):
        if value is None:
            unknown_target.add(skill)
            value = MAX_LEVEL  # Conservative upper bound for an unknown requirement.
        required[skill] = value
    direct = {s: max(0.0, level - known(s)) for s, level in required.items()}
    direct = {s: delta for s, delta in direct.items() if delta > 0}
    closure = prerequisite_closure(graph, direct)
    fallback = set()

    def weight(skill):
        if skill not in weights:
            fallback.add(skill)
        return weights.get(skill, 1.0)

    effective_weights = {s: weight(s) for s in sorted(direct)}
    direct_score = m2_weighted_gap(direct, effective_weights)
    additional = {}
    for skill in sorted(closure):
        unmet = max(0.0, params.minimum_prerequisite_level - known(skill))
        # Direct deficits already pay for the same proficiency units.
        extra = max(0.0, unmet - direct.get(skill, 0.0))
        if extra > 0:
            additional[skill] = extra
    effective_weights.update({s: weight(s) for s in sorted(additional)})
    m3, burden = m3_prerequisite_aware_gap(direct_score, additional, effective_weights, params.lambda_)
    active = set(direct) | set(additional)
    order = [s for s in topological_order(graph, params.algorithm) if s in active]
    rows = [{"skill_id": s, "known_level": source.get(s), "target_level": required.get(s),
             "direct_deficit": direct.get(s, 0.0), "additional_deficit": additional.get(s, 0.0),
             "weight": weight(s), "is_prerequisite": s in closure} for s in order]
    return {"M1": m1_unweighted_gap(direct), "M2": direct_score, "M3": m3,
            "direct_score": direct_score, "prerequisite_burden": burden,
            "weighted_prerequisite_burden": params.lambda_ * burden,
            "missing_skills": sorted(direct), "prerequisite_skills": sorted(closure), "learning_order": order,
            "details": rows, "unknown_source_skills": sorted(unknown_source),
            "unknown_target_skills": sorted(unknown_target), "fallback_weight_skills": sorted(fallback),
            "scenario": "conservative: unknown source=0; unknown target=4; missing target weight=1",
            "units": "dimensionless; M1=count, M2/M3=weighted normalized proficiency deficits"}
