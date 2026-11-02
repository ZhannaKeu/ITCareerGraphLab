"""Copy-on-write datasets: editing or reviewing never changes an existing snapshot."""
import copy
import hashlib
import json
from collections import Counter, defaultdict
import networkx as nx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .. import models as m
from ..research.graph import build_graph
from .origins import DISCLOSURE

MODELS = {
    "skill": m.Skill, "profile": m.Profile, "requirement": m.Requirement,
    "prerequisite": m.Prerequisite, "weight": m.SkillWeight, "source_row": m.SourceRecord,
    "group": m.SkillGroup, "membership": m.SkillMapping, "level": m.SkillLevel,
    "course_skill": m.CourseSkill, "survey_mapping": m.SurveyMapping,
    "dependency_count": m.SkillDependencyCount,
}
KEY_FIELDS = {
    "skill": ("id",), "profile": ("id",), "prerequisite": ("prerequisite_id", "skill_id"),
    "weight": ("source", "role", "skill_id"), "source_row": ("filename", "row_number"),
    "group": ("id",), "membership": ("group_id", "skill_id"), "level": ("level",),
    "course_skill": ("course_id", "skill_id"), "survey_mapping": ("survey_name",),
    "dependency_count": ("skill_id",),
}
FILES = {
    "skill": "skills.csv", "profile": "role_requirements.csv", "requirement": "role_requirements.csv",
    "prerequisite": "prerequisites.csv", "group": "skill_groups.csv", "membership": "skill_groups.csv",
    "level": "skill_levels.csv", "course_skill": "course_skills.csv", "survey_mapping": "skill_mapping.csv",
    "dependency_count": "skill_dependents.csv",
}


def key(parts):
    return json.dumps([str(p) for p in parts], ensure_ascii=False, separators=(",", ":"))


def natural_key(entity, data):
    if entity == "requirement":
        return key([data["profile_id"], "skill" if data["skill_id"] else "group", data["skill_id"] or data["group_id"]])
    if entity == "level":
        return key([f"{data['level']:g}"])
    return key([data[f] for f in KEY_FIELDS[entity]])


def catalog(session, version_id):
    records = {}
    for entity, model in MODELS.items():
        for obj in session.scalars(select(model).where(model.version_id == version_id)):
            data = {c.name: getattr(obj, c.name) for c in model.__table__.columns if c.name != "version_id"}
            if entity not in ("skill", "profile", "group"):
                data.pop("id", None)  # Surrogate IDs are not part of scientific identity.
            records[(entity, natural_key(entity, data))] = data
    return records


def annotations(session, version_id):
    return {(p.entity, p.record_key): {"status": p.status, "origin": copy.deepcopy(p.origin),
             "reviewer": p.reviewer, "evidence": p.evidence, "verification_note": p.verification_note}
            for p in session.scalars(select(m.RecordProvenance).where(m.RecordProvenance.version_id == version_id))}


def record_hash(records, provenance):
    content = [{"entity": e, "key": k, "data": records[e, k], "provenance": provenance[e, k]} for e, k in sorted(records)]
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def source_references(records):
    refs = defaultdict(list)
    mapping = {d["survey_name"].casefold(): d["skill_id"] for (e, _), d in records.items() if e == "survey_mapping"}
    for (entity, _), d in records.items():
        if entity != "source_row":
            continue
        file, n, row = d["filename"], d["row_number"], d["data"]
        targets = []
        if file == "skills.csv": targets = [("skill", key([row["skill_id"]]))]
        elif file == "role_requirements.csv":
            profile = f"{row['role']}:{row['grade']}"
            targets = [("requirement", key([profile, row["item_type"], row["item_id"]])), ("profile", key([profile]))]
        elif file == "prerequisites.csv": targets = [("prerequisite", key([row["from_skill"], row["to_skill"]]))]
        elif file == "skill_groups.csv": targets = [("group", key([row["group_id"]])), ("membership", key([row["group_id"], row["skill_id"]]))]
        elif file == "skill_levels.csv": targets = [("level", key([f"{float(row['level']):g}"]))]
        elif file == "skill_mapping.csv": targets = [("survey_mapping", key([row["survey_name"]]))]
        elif file == "skill_dependents.csv": targets = [("dependency_count", key([row["skill_id"]]))]
        elif file == "course_skills.csv": targets = [("course_skill", key([row["course_id"], row["skill_id"]]))]
        elif file == "role_skill_weights.csv": targets = [("weight", key([file, row["role"], row["skill_id"]]))]
        elif file == "skill_weights_by_role_final_v2.csv":
            skill = mapping.get(row["skill"].casefold())
            if skill: targets = [("weight", key([file, row["role"], skill]))]
        for target in targets:
            refs[target].append(n)
    return refs


def ensure_original_provenance(session, version_id):
    """Idempotent conservative backfill; never interprets CSV 'expert' as reviewed."""
    if session.get(m.DatasetLineage, version_id):
        return
    records = catalog(session, version_id)
    refs = source_references(records)
    provenance = {}
    for (entity, k), data in records.items():
        file = data["filename"] if entity == "source_row" else data["source"] if entity == "weight" else FILES.get(entity)
        family = "requirements" if entity in ("requirement", "profile") else "prerequisites" if entity in ("prerequisite", "dependency_count") else "weights" if entity == "weight" else "course_mappings" if entity == "course_skill" else "other"
        origin = {"kind": "imported", "source_version": version_id, "file": file,
                  "rows": [data["row_number"]] if entity == "source_row" else sorted(refs.get((entity, k), [])),
                  "declared_origin": DISCLOSURE[family], "declaration_is_evidence": False,
                  "csv_labels_are_claims": True}
        if entity == "course_skill": origin["course_name_origin"] = DISCLOSURE["curriculum"]
        if entity == "weight": origin["transformation"] = "MAX(weight_0_1) after skill_mapping" if data["source"].startswith("skill_weights") else "weight, Python/Colab computation as declared by owner"
        if entity == "source_row": origin["raw_claims"] = {f: data["data"][f] for f in ("source", "weight_source") if f in data["data"]}
        provenance[entity, k] = {"status": "Unverified", "origin": origin, "reviewer": None, "evidence": None, "verification_note": None}
    session.add(m.DatasetLineage(version_id=version_id, parent_id=None, root_id=version_id, kind="original",
        author="dataset owner disclosure", reason="Initial import with explicitly unverified origins", disclosure=copy.deepcopy(DISCLOSURE), record_hash=record_hash(records, provenance)))
    session.add_all(m.RecordProvenance(version_id=version_id, entity=e, record_key=k, **p) for (e, k), p in provenance.items())
    session.flush()


def metadata(session, version_id):
    line = session.get(m.DatasetLineage, version_id)
    if line is None:
        raise ValueError("Provenance not initialized. Re-run the idempotent CSV import after migrations.")
    grouped = defaultdict(Counter)
    for p in session.scalars(select(m.RecordProvenance).where(m.RecordProvenance.version_id == version_id)):
        grouped[p.entity][p.status] += 1
    return {"parent_id": line.parent_id, "root_id": line.root_id, "kind": line.kind,
            "author": line.author, "reason": line.reason, "record_hash": line.record_hash,
            "disclosure": line.disclosure, "verification_counts": {e: dict(counts) for e, counts in sorted(grouped.items())}}


def public_records(session, version_id, entity=None, status=None, offset=0, limit=50):
    query = select(m.RecordProvenance).where(m.RecordProvenance.version_id == version_id)
    if entity: query = query.where(m.RecordProvenance.entity == entity)
    if status: query = query.where(m.RecordProvenance.status == status)
    from sqlalchemy import func
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    records = catalog(session, version_id)
    selected = session.scalars(query.order_by(m.RecordProvenance.entity, m.RecordProvenance.record_key).offset(offset).limit(limit))
    return {"total": total, "records": [{"entity": p.entity, "key": json.loads(p.record_key),
        "data": records[p.entity, p.record_key], "status": p.status, "origin": p.origin,
        "reviewer": p.reviewer, "evidence": p.evidence, "verification_note": p.verification_note} for p in selected]}


def verification_data(verification):
    reviewer = (verification.reviewer or "").strip() or None
    evidence = (verification.evidence or "").strip() or None
    if verification.status != "Unverified" and (not reviewer or not evidence):
        raise ValueError("Expert Verified / Source Verified requires a named reviewer and explicit evidence or assessment reference")
    return {"status": verification.status, "reviewer": reviewer if verification.status != "Unverified" else None,
            "evidence": evidence if verification.status != "Unverified" else None, "verification_note": verification.note}


def create_revision(session, request):
    parent = session.get(m.DatasetVersion, request.parent_id)
    line = session.get(m.DatasetLineage, request.parent_id)
    if not parent or not line:
        raise ValueError("Unknown parent dataset or missing provenance")
    if not all(v.strip() for v in (request.label, request.author, request.reason)):
        raise ValueError("Label, author and reason must not be blank")
    records, original_provenance = catalog(session, parent.id), annotations(session, parent.id)
    provenance = copy.deepcopy(original_provenance)
    events, touched = [], set()
    skills = {d['id'] for (e, _), d in records.items() if e == 'skill'}
    groups = {d['id'] for (e, _), d in records.items() if e == 'group'}
    profiles = {d['id'] for (e, _), d in records.items() if e == 'profile'}
    for change in request.changes:
        entity, k = change.entity, key(change.key)
        if (entity, k) in touched:
            raise ValueError("Only one operation per record per revision is allowed")
        touched.add((entity, k))
        before = {"data": copy.deepcopy(records[entity, k]), "provenance": copy.deepcopy(provenance[entity, k])} if (entity, k) in records else None
        if change.operation != 'upsert' and before is None:
            raise ValueError("Cannot delete or verify a nonexistent record")
        if change.operation in ('upsert', 'delete') and entity not in ('requirement', 'prerequisite'):
            raise ValueError("Only requirements and prerequisite edges can be edited; other records support explicit verification")
        if 'required_level' in change.model_fields_set and (entity != 'requirement' or change.operation != 'upsert'):
            raise ValueError("required_level is only valid for requirement upsert")
        if change.operation == 'delete':
            del records[entity, k]
            del provenance[entity, k]
            after = None
        else:
            if change.operation == 'upsert':
                if entity == 'prerequisite':
                    if len(change.key) != 2 or any(s not in skills for s in change.key):
                        raise ValueError("Prerequisite key must contain two existing skills")
                    data = {'prerequisite_id': change.key[0], 'skill_id': change.key[1]}
                else:
                    if len(change.key) != 3:
                        raise ValueError("Requirement key must be [profile_id, skill|group, item_id]")
                    profile, kind, item = change.key
                    if profile not in profiles or kind not in ('skill', 'group') or item not in (skills if kind == 'skill' else groups):
                        raise ValueError("Unknown requirement profile, type or item")
                    if 'required_level' not in change.model_fields_set:
                        raise ValueError("Set required_level explicitly; null means unknown")
                    if change.required_level is not None and not change.required_level.is_integer():
                        raise ValueError("Requirement level must be a declared integer from 0 through 4")
                    data = {'profile_id': profile, 'skill_id': item if kind == 'skill' else None,
                        'group_id': item if kind == 'group' else None, 'required_level': change.required_level,
                        'original_weight': before['data']['original_weight'] if before else 1.,
                        'weight_origin': before['data']['weight_origin'] if before else 'manual revision; unused in scores'}
                records[entity, k] = data
                origin = copy.deepcopy(before['provenance']['origin']) if before else {'kind': 'manual', 'source_version': line.root_id, 'file': None, 'rows': []}
                origin.update(last_edited_from=parent.id, last_editor=request.author, change_reason=request.reason)
            else:
                origin = copy.deepcopy(provenance[entity, k]['origin'])
            # Any substantive edit invalidates prior verification unless explicitly reviewed again.
            provenance[entity, k] = {'origin': origin, **verification_data(change.verification)}
            after = {'data': copy.deepcopy(records[entity, k]), 'provenance': copy.deepcopy(provenance[entity, k])}
        events.append({'entity': entity, 'record_key': k, 'operation': change.operation, 'before': before, 'after': after})
    graph = build_graph(skills, [(d['prerequisite_id'], d['skill_id']) for (e, _), d in records.items() if e == 'prerequisite'])
    # Derived counts follow the edited graph; original CSV counts stay unchanged.
    for (entity, k), data in list(records.items()):
        if entity != 'dependency_count': continue
        new = {**data, 'dependents': len(nx.descendants(graph, data['skill_id'])), 'prerequisites': len(nx.ancestors(graph, data['skill_id']))}
        if new != data:
            before = {'data': copy.deepcopy(data), 'provenance': copy.deepcopy(provenance[entity, k])}
            records[entity, k] = new
            provenance[entity, k] = {'status': 'Unverified', 'origin': {**provenance[entity, k]['origin'], 'kind': 'derived', 'derived_from_parent': parent.id, 'method': 'NetworkX ancestors/descendants on revised DAG'}, 'reviewer': None, 'evidence': None, 'verification_note': 'Recomputed counts are not expert validation of edges'}
            events.append({'entity': entity, 'record_key': k, 'operation': 'recalculate', 'before': before, 'after': {'data': new, 'provenance': copy.deepcopy(provenance[entity, k])}})
    content_hash = record_hash(records, provenance)
    identifier = hashlib.sha256(json.dumps({'parent': parent.id, 'content_hash': content_hash, 'request': request.model_dump(mode='json'), 'protocol': 'revision-v1'}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if session.get(m.DatasetVersion, identifier):
        return {'version_id': identifier, **metadata(session, identifier)}
    quality = copy.deepcopy(parent.quality)
    quality.update(version_id=identifier)
    quality['stats']['edges'] = graph.number_of_edges()
    quality['stats']['group_requirements_excluded'] = sum(e == 'requirement' and d['group_id'] is not None for (e, _), d in records.items())
    quality['warnings'].append({'code': 'corrected_snapshot', 'file': None, 'row': None, 'message': 'Manual immutable revision; source manifest/CSV rows refer to original bytes. Derived dependency counts recalculated; edits are not automatically verified.'})
    try:
        session.add(m.DatasetVersion(id=identifier, label=request.label.strip(), is_demo=parent.is_demo, manifest=copy.deepcopy(parent.manifest), quality=quality))
        session.flush()
        # Flush parent entities first for the version-scoped foreign keys.
        for phase in [('skill','group','profile','level'), tuple(e for e in MODELS if e not in ('skill','group','profile','level'))]:
            for entity in phase:
                session.add_all(MODELS[entity](version_id=identifier, **copy.deepcopy(data)) for (e, _), data in sorted(records.items()) if e == entity)
            session.flush()
        session.add(m.DatasetLineage(version_id=identifier, parent_id=parent.id, root_id=line.root_id, kind='corrected', author=request.author.strip(), reason=request.reason.strip(), disclosure=copy.deepcopy(line.disclosure), record_hash=content_hash))
        session.add_all(m.RecordProvenance(version_id=identifier, entity=e, record_key=k, **p) for (e, k), p in provenance.items())
        session.add_all(m.ChangeEvent(version_id=identifier, sequence=i, author=request.author.strip(), reason=request.reason.strip(), **event) for i, event in enumerate(events, 1))
        session.commit()
    except IntegrityError:
        session.rollback()
        if not session.get(m.DatasetVersion, identifier): raise
    return {'version_id': identifier, **metadata(session, identifier)}


def history(session, version_id):
    result, seen = [], set()
    while version_id:
        if version_id in seen: raise ValueError('Invalid lineage cycle')
        seen.add(version_id)
        line = session.get(m.DatasetLineage, version_id)
        if not line: raise ValueError('Unknown version')
        events = session.scalars(select(m.ChangeEvent).where(m.ChangeEvent.version_id == version_id).order_by(m.ChangeEvent.sequence))
        result.append({'version_id': version_id, 'parent_id': line.parent_id, 'author': line.author, 'reason': line.reason,
            'changes': [{'sequence': e.sequence, 'entity': e.entity, 'key': json.loads(e.record_key), 'operation': e.operation,
                'before': e.before, 'after': e.after, 'author': e.author, 'reason': e.reason, 'created_at': e.created_at} for e in events]})
        version_id = line.parent_id
    return result
