import hashlib
import json
import platform
from dataclasses import dataclass
from importlib.metadata import version
from sqlalchemy import select
from ..models import ActiveDataset, DatasetVersion, Skill, Profile, Prerequisite, Requirement, SkillWeight
from ..research.models import compare, Parameters
from .versions import annotations, metadata, key
from ..models import ExperimentRun
from .relation_graphs import classification_manifest, graph_configuration, validate_named_request

class DatasetUnavailable(ValueError):
    pass

@dataclass
class Snapshot:
    version: DatasetVersion
    skills: list
    profiles: list
    edges: list
    requirements: list
    weights: list
    record_provenance: dict
    metadata: dict
    classification: dict | None


def load_snapshot(session, version_id=None):
    if not version_id:
        active = session.get(ActiveDataset, 1)
        version_id = active.version_id if active else None
    dataset = session.get(DatasetVersion, version_id) if version_id else None
    if dataset is None:
        raise DatasetUnavailable("No dataset imported. Run python -m app.cli import <directory>.")
    def get(model, order):
        return list(session.scalars(select(model).where(model.version_id == version_id).order_by(*order)))
    return Snapshot(dataset, get(Skill, [Skill.id]), get(Profile, [Profile.id]),
                    get(Prerequisite, [Prerequisite.prerequisite_id, Prerequisite.skill_id]),
                    get(Requirement, [Requirement.profile_id, Requirement.skill_id, Requirement.group_id]),
                    get(SkillWeight, [SkillWeight.source, SkillWeight.role, SkillWeight.skill_id]),
                    annotations(session, version_id), metadata(session, version_id),
                    classification_manifest(session, metadata(session, version_id)["root_id"]))


def run_experiment(snapshot, request, source_id=None, target_id=None):
    profiles = {p.id: p for p in snapshot.profiles}
    source_id, target_id = source_id or request.source_profile, target_id or request.target_profile
    if source_id not in profiles or target_id not in profiles:
        raise ValueError("Unknown source or target profile")
    if source_id == target_id:
        raise ValueError("Source and target must differ")
    def eligible(entity, parts):
        return request.verification_scope == "all" or snapshot.record_provenance.get((entity, key(parts)), {}).get("status") in ("Expert Verified", "Source Verified")
    validate_named_request(request)
    config = graph_configuration(snapshot, request.graph_configuration) if request.graph_configuration else None
    stored_edges = {(p.prerequisite_id, p.skill_id) for p in snapshot.edges}
    if config:
        stored_edges = {(e['from_skill'],e['to_skill']) for e in config['edges']}
    edges = {(a,b) for a,b in stored_edges if eligible("prerequisite", [a,b])}
    excluded, included = set(map(tuple, request.excluded_edges)), set(map(tuple, request.included_edges))
    if excluded & included:
        raise ValueError("An edge cannot be both included and excluded")
    if excluded - stored_edges:
        raise ValueError("Excluded edge does not exist in the dataset")
    if request.verification_scope == "verified" and included:
        raise ValueError("Unverified experimental edge additions are not permitted in verified-only scope; create and review a dataset revision")
    edges = (edges - excluded) | included
    reqs = {}
    for r in snapshot.requirements:
        if r.skill_id is not None and eligible("requirement", [r.profile_id, "skill", r.skill_id]):  # Group requirements preserved but excluded.
            reqs.setdefault(r.profile_id, {})[r.skill_id] = r.required_level
    weights = {w.skill_id: w.weight for w in snapshot.weights
               if w.source == request.weight_source and w.role == profiles[target_id].role and eligible("weight", [w.source, w.role, w.skill_id])}
    if request.verification_scope == "verified" and (not reqs.get(source_id) or not reqs.get(target_id)):
        raise ValueError("Verified-only calculation requires reviewed skill requirements for both source and target profiles; no verified coverage is not a zero gap")
    if not weights:
        raise ValueError(f"No weights in {request.weight_source} for target role")
    result = compare([s.id for s in snapshot.skills], edges, reqs.get(source_id, {}), reqs.get(target_id, {}), weights,
                     Parameters(request.minimum_prerequisite_level, request.lambda_, request.algorithm))
    result.update(source_profile=source_id, target_profile=target_id, verification_scope=request.verification_scope,
                  interpretation="Model-based proficiency deficit, not factual career transition difficulty")
    return result


def provenance(snapshot, request, kind="pair"):
    params = request.model_copy(update={"version_id": snapshot.version.id}).model_dump(mode="json", by_alias=True)
    # Null configuration is omitted to preserve exact historical parameter/run hashes.
    if params.get('graph_configuration') is None:
        params.pop('graph_configuration', None)
    config = graph_configuration(snapshot, request.graph_configuration) if request.graph_configuration else None
    canonical = {"dataset": snapshot.version.id, "record_hash": snapshot.metadata["record_hash"],
                 "parameters": params, "implementation": "1.1.0", "experiment_kind": kind}
    if config:
        canonical['graph_configuration'] = config
    return {**canonical, "run_id": hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest(),
            "is_demo": snapshot.version.is_demo, "manifest": snapshot.version.manifest,
            "data_provenance": snapshot.metadata,
            "runtime": {"python": platform.python_version(), "networkx": version("networkx")},
            "weight_rule": "Only target-role weights from the selected file; missing weights explicitly default to 1",
            "warning": "AI-assisted inputs are unverified unless explicitly reviewed. Scores are model outputs, not factual transition difficulty, time estimates or evidence of recommendation quality. Group requirements excluded."}


def execute_run(session, snapshot, request, kind="pair"):
    """Persist exact results, resolved version, parameters and provenance for replay."""
    from sqlalchemy.exc import IntegrityError
    meta = provenance(snapshot, request, kind)
    saved = session.get(ExperimentRun, meta["run_id"])
    if saved:
        return saved.payload
    if kind == "batch":
        payload = {"results": [run_experiment(snapshot, request, a.id, b.id) for a in snapshot.profiles for b in snapshot.profiles if a.id != b.id], "provenance": meta}
    else:
        payload = {"result": run_experiment(snapshot, request), "provenance": meta}
    try:
        with session.begin_nested():
            session.add(ExperimentRun(id=meta["run_id"], version_id=snapshot.version.id, kind=kind, parameters=meta["parameters"], payload=payload))
            session.flush()
    except IntegrityError:
        existing = session.get(ExperimentRun, meta["run_id"])
        if existing is None: raise
        return existing.payload
    session.commit()
    return payload
