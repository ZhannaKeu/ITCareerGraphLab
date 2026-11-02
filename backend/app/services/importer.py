"""Import the observed research schemas; never mutate source CSVs.

Prerequisite direction: from_skill -> to_skill. Dependents are transitive counts.
Final-v2 names map ONLY through skill_mapping; dropped names stay in SourceRecord.
Multiple survey names mapped to one skill use MAX(weight_0_1), never a sum.
"""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import networkx as nx
from ..models import (ActiveDataset, DatasetVersion, Skill, Profile, Requirement,
    Prerequisite, SkillWeight, SourceRecord, SkillGroup, SkillMapping, SkillLevel,
    CourseSkill, SurveyMapping, SkillDependencyCount)
from ..research.graph import build_graph, InvalidGraph

SCHEMAS = {
 "skills.csv": ["skill_id", "name", "category", "aliases", "source"],
 "skill_mapping.csv": ["survey_name", "skill_id", "action"],
 "skill_groups.csv": ["group_id", "group_name", "skill_id"],
 "skill_levels.csv": ["level", "name", "description"],
 "prerequisites.csv": ["from_skill", "to_skill"],
 "skill_dependents.csv": ["skill_id", "dependents", "prerequisites"],
 "role_skill_weights.csv": ["role", "skill_id", "weight", "source"],
 "role_requirements.csv": ["role", "grade", "item_id", "item_type", "required", "weight", "weight_source"],
 "course_skills.csv": ["course_id", "skill_id", "contribution", "note"],
 "skill_weights_by_role_final_v2.csv": ["role", "skill", "raw_frequency", "relative_weight", "weight_0_1"],
}

class ImportFailure(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__(json.dumps(report, ensure_ascii=False))


def inspect_dataset(directory: Path):
    directory = Path(directory)
    tables, manifest, errors, warnings = {}, {}, [], []
    def issue(code, file, row, message, fatal=True):
        (errors if fatal else warnings).append(dict(code=code, file=file, row=row, message=message))
    for filename, columns in SCHEMAS.items():
        path = directory / filename
        if not path.is_file():
            issue("missing_file", filename, None, "Required CSV is absent")
            continue
        data = path.read_bytes()
        manifest[filename] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        try:
            reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
            headers = reader.fieldnames or []
            if len(set(headers)) != len(headers):
                issue("duplicate_header", filename, 1, "Duplicate column names")
            if not set(columns) <= set(headers):
                issue("schema_mismatch", filename, 1, f"Expected {columns}; actual {headers}. No implicit schema guessing.")
                continue
            rows = []
            for rownum, raw in enumerate(reader, 2):
                if None in raw or any(v is None for v in raw.values()):
                    issue("malformed_row", filename, rownum, "Different number of CSV columns")
                    continue
                rows.append((rownum, {k: v.strip() for k, v in raw.items()}, raw))
            tables[filename] = rows
            manifest[filename].update(headers=headers, rows=len(rows))
        except (UnicodeError, csv.Error) as exc:
            issue("csv_error", filename, None, str(exc))
    if errors:
        raise ImportFailure({"errors": errors, "warnings": warnings, "manifest": manifest})
    def rows(file):
        return [(n, r) for n, r, _ in tables[file]]
    optional = {"skills.csv": {"aliases"}, "skill_mapping.csv": {"skill_id"},
                "course_skills.csv": {"note"}, "role_requirements.csv": {"required"},
                "skill_weights_by_role_final_v2.csv": {"relative_weight"}}
    for file, columns in SCHEMAS.items():
        for n, row in rows(file):
            for key in set(columns) - optional.get(file, set()):
                if not row[key]:
                    issue("missing_value", file, n, f"{key} must not be empty")
    unique_keys = {
        "skills.csv": ["skill_id"], "skill_mapping.csv": ["survey_name"],
        "skill_groups.csv": ["group_id", "skill_id"], "skill_levels.csv": ["level"],
        "prerequisites.csv": ["from_skill", "to_skill"], "skill_dependents.csv": ["skill_id"],
        "role_skill_weights.csv": ["role", "skill_id"],
        "role_requirements.csv": ["role", "grade", "item_type", "item_id"],
        "course_skills.csv": ["course_id", "skill_id"], "skill_weights_by_role_final_v2.csv": ["role", "skill"]}
    for file, columns in unique_keys.items():
        seen = {}
        for n, row in rows(file):
            key = tuple(row[c] for c in columns)
            if key in seen:
                issue("duplicate_or_conflict", file, n, f"Duplicate key {key}; first row {seen[key]}")
            seen[key] = n
    skills = {r["skill_id"] for _, r in rows("skills.csv")}
    groups = {r["group_id"] for _, r in rows("skill_groups.csv")}
    group_names = {}
    for n, r in rows("skill_groups.csv"):
        if r["group_id"] in group_names and group_names[r["group_id"]] != r["group_name"]:
            issue("group_name_conflict", "skill_groups.csv", n, "Same group has different names")
        group_names[r["group_id"]] = r["group_name"]
    numeric = {"skill_levels.csv": {"level": 4}, "skill_dependents.csv": {"dependents": None, "prerequisites": None},
        "role_skill_weights.csv": {"weight": 1}, "role_requirements.csv": {"required": 4, "weight": 1},
        "course_skills.csv": {"contribution": 1},
        "skill_weights_by_role_final_v2.csv": {"raw_frequency": None, "relative_weight": None, "weight_0_1": 1}}
    for file in tables:
        for n, row in rows(file):
            for field in ("skill_id", "from_skill", "to_skill"):
                if row.get(field) and row[field] not in skills:
                    issue("dangling_skill", file, n, f"Unknown {field}: {row[field]}")
            for field, upper in numeric.get(file, {}).items():
                if not row[field] and field == "relative_weight":
                    row[field] = None
                    issue("missing_auxiliary_weight", file, n, "relative_weight absent; selected weight_0_1 is present and used; no imputation", False)
                    continue
                if not row[field] and field == "required":
                    row[field] = None
                    issue("unknown_level", file, n, "Explicit conservative scenario: unknown source=0, unknown target=4", False)
                    continue
                try:
                    value = float(row[field])
                    if not math.isfinite(value) or value < 0 or (upper is not None and value > upper):
                        raise ValueError()
                    if field in ("level", "required", "dependents", "prerequisites") and not value.is_integer():
                        raise ValueError()
                    row[field] = value
                except (ValueError, TypeError):
                    issue("invalid_number", file, n, f"Invalid {field}: {row[field]}")
    profiles = set()
    req_lookup = {}
    for n, r in rows("role_requirements.csv"):
        if r["grade"] not in ("junior", "middle"):
            issue("invalid_grade", "role_requirements.csv", n, "grade must be junior or middle")
        if r["item_type"] not in ("skill", "group"):
            issue("invalid_item_type", "role_requirements.csv", n, "item_type must be skill or group")
        elif r["item_id"] not in (skills if r["item_type"] == "skill" else groups):
            issue("dangling_requirement", "role_requirements.csv", n, f"Unknown {r['item_type']}: {r['item_id']}")
        if r["item_type"] == "group":
            issue("excluded_group_requirement", "role_requirements.csv", n, "Ambiguous ANY-group requirement: stored, excluded from M1/M2/M3", False)
        profiles.add((r["role"], r["grade"]))
        req_lookup[(r["role"], r["grade"], r["item_type"], r["item_id"])] = r["required"]
    for (role, grade, kind, item), level in req_lookup.items():
        junior = req_lookup.get((role, "junior", kind, item))
        if grade == "middle" and isinstance(level, float) and isinstance(junior, float) and level < junior:
            issue("grade_regression", "role_requirements.csv", None, f"{role}/{item}: middle requirement lower than junior")
    roles = {role for role, _ in profiles}
    for file in ("role_skill_weights.csv", "skill_weights_by_role_final_v2.csv"):
        for n, r in rows(file):
            if r["role"] not in roles:
                issue("unknown_role", file, n, f"No requirements for role {r['role']}")
    mappings = {}
    for n, r in rows("skill_mapping.csv"):
        key = r["survey_name"].casefold()
        if key in mappings:
            issue("ambiguous_mapping", "skill_mapping.csv", n, f"Case-insensitive duplicate {key}")
        mappings[key] = r["skill_id"]
        if not r["skill_id"] and not r["action"].startswith("dropped"):
            issue("missing_mapping", "skill_mapping.csv", n, "Empty skill_id only allowed for explicitly dropped items")
        if r["skill_id"] and r["action"].startswith("dropped"):
            issue("mapping_conflict", "skill_mapping.csv", n, "Dropped item must have no skill_id")
    final_weights, dropped, merged = {}, 0, 0
    for n, r in rows("skill_weights_by_role_final_v2.csv"):
        key = r["skill"].casefold()
        if key not in mappings:
            issue("unmapped_weight", "skill_weights_by_role_final_v2.csv", n, f"No explicit skill_mapping for {r['skill']}")
            continue
        skill = mappings[key]
        if not skill:
            dropped += 1
            continue
        k = (r["role"], skill)
        if k in final_weights:
            merged += 1
        if isinstance(r["weight_0_1"], float):
            final_weights[k] = max(final_weights.get(k, 0), r["weight_0_1"])
    if dropped:
        issue("dropped_weight_rows", "skill_weights_by_role_final_v2.csv", None, f"{dropped} package/OS-tool rows excluded via explicit mapping", False)
    if merged:
        issue("merged_weight_rows", "skill_weights_by_role_final_v2.csv", None, f"{merged} alias collisions aggregated with MAX(weight_0_1); raw rows preserved", False)
    edges = {(r["from_skill"], r["to_skill"]) for _, r in rows("prerequisites.csv")}
    try:
        graph = build_graph(skills, edges)
        count_ids = {r["skill_id"] for _, r in rows("skill_dependents.csv")}
        if count_ids != skills:
            issue("count_coverage", "skill_dependents.csv", None, "Counts must cover exactly all skills")
        for n, r in rows("skill_dependents.csv"):
            if r["skill_id"] in graph and (r["dependents"] != len(nx.descendants(graph, r["skill_id"])) or r["prerequisites"] != len(nx.ancestors(graph, r["skill_id"]))):
                issue("dependency_count_mismatch", "skill_dependents.csv", n, "Transitive dependency counts disagree with prerequisites.csv")
    except InvalidGraph as exc:
        issue("invalid_graph", "prerequisites.csv", None, str(exc))
    valid_levels = {r["level"] for _, r in rows("skill_levels.csv") if isinstance(r["level"], float)}
    if valid_levels != {0., 1., 2., 3., 4.}:
        issue("level_scale", "skill_levels.csv", None, "Scale must explicitly declare 0,1,2,3,4")
    if not skills or len(profiles) < 2:
        issue("empty_dataset", "role_requirements.csv", None, "Need skills and at least two profiles")
    if len(profiles) != 14:
        issue("profile_count", "role_requirements.csv", None, f"Found {len(profiles)} profiles, batch={len(profiles)*(len(profiles)-1)}", False)
    # Fingerprint includes adapter version because interpretation is part of dataset identity.
    fingerprint = hashlib.sha256(json.dumps({"files": manifest, "adapter": "research-csv-v2"}, sort_keys=True).encode()).hexdigest()
    report = {"errors": errors, "warnings": warnings, "manifest": manifest, "version_id": fingerprint,
        "stats": {"skills": len(skills), "roles": len(roles), "profiles": len(profiles), "edges": len(edges),
                  "groups": len(groups), "group_requirements_excluded": sum(r['item_type']=='group' for _,r in rows('role_requirements.csv')),
                  "transitions": len(profiles)*(len(profiles)-1), "final_weight_rows_dropped": dropped, "final_weight_alias_merges": merged},
        "rules": {"adapter": "research-csv-v2", "level_scale": "0..4", "graph_authority": "prerequisites.csv",
                  "group_requirements": "excluded", "final_weight": "MAX(weight_0_1) after explicit skill_mapping; dropped excluded",
                  "weight_sources": "Never blended; requirement.weight retained for audit only"}}
    if errors:
        raise ImportFailure(report)
    return tables, report


def profile_id(role, grade):
    return f"{role}:{grade}"


def import_dataset(session, directory, demo=False, activate=False):
    directory = Path(directory)
    tables, report = inspect_dataset(directory)
    version = report["version_id"]
    existing = session.get(DatasetVersion, version)
    if existing and existing.is_demo != demo:
        raise ValueError("Existing version has a different demo label")
    def rows(file):
        return [r for _, r, _ in tables[file]]
    if not existing:
        session.add(DatasetVersion(id=version, label=directory.name, is_demo=demo, manifest=report["manifest"], quality=report))
        session.flush()
        for filename, records in tables.items():
            session.add_all(SourceRecord(version_id=version, filename=filename, row_number=n, data=raw) for n, _, raw in records)
        session.add_all(Skill(version_id=version, id=r['skill_id'], name=r['name'], category=r['category'], description=r['aliases']) for r in rows('skills.csv'))
        group_names = {r['group_id']:r['group_name'] for r in rows('skill_groups.csv')}
        session.add_all(SkillGroup(version_id=version, id=k, name=v) for k,v in sorted(group_names.items()))
        pairs = sorted({(r['role'],r['grade']) for r in rows('role_requirements.csv')})
        session.add_all(Profile(version_id=version, id=profile_id(role,grade), role=role, level=grade.title()) for role,grade in pairs)
        session.add_all(SkillLevel(version_id=version, level=r['level'], name=r['name'], description=r['description']) for r in rows('skill_levels.csv'))
        session.flush()  # Parents before composite foreign keys.
        session.add_all(SkillMapping(version_id=version, skill_id=r['skill_id'], group_id=r['group_id']) for r in rows('skill_groups.csv'))
        session.add_all(SurveyMapping(version_id=version, survey_name=r['survey_name'], skill_id=r['skill_id'] or None, action=r['action']) for r in rows('skill_mapping.csv'))
        session.add_all(Prerequisite(version_id=version, prerequisite_id=r['from_skill'], skill_id=r['to_skill']) for r in rows('prerequisites.csv'))
        session.add_all(SkillDependencyCount(version_id=version, skill_id=r['skill_id'], dependents=int(r['dependents']), prerequisites=int(r['prerequisites'])) for r in rows('skill_dependents.csv'))
        session.add_all(CourseSkill(version_id=version, course_id=r['course_id'], skill_id=r['skill_id'], contribution=r['contribution'], note=r['note']) for r in rows('course_skills.csv'))
        for r in rows('role_requirements.csv'):
            session.add(Requirement(version_id=version, profile_id=profile_id(r['role'],r['grade']),
                skill_id=r['item_id'] if r['item_type']=='skill' else None, group_id=r['item_id'] if r['item_type']=='group' else None,
                required_level=r['required'], original_weight=r['weight'], weight_origin=r['weight_source']))
        session.add_all(SkillWeight(version_id=version, source='role_skill_weights.csv', role=r['role'], skill_id=r['skill_id'], weight=r['weight']) for r in rows('role_skill_weights.csv'))
        mapping = {r['survey_name'].casefold():r['skill_id'] for r in rows('skill_mapping.csv')}
        final = {}
        for r in rows('skill_weights_by_role_final_v2.csv'):
            skill = mapping[r['skill'].casefold()]
            if skill:
                key = (r['role'], skill)
                final[key] = max(final.get(key,0),r['weight_0_1'])
        session.add_all(SkillWeight(version_id=version, source='skill_weights_by_role_final_v2.csv', role=role, skill_id=skill, weight=weight) for (role,skill),weight in sorted(final.items()))
        session.flush()
    from .versions import ensure_original_provenance
    ensure_original_provenance(session, version)
    from .relation_graphs import ensure_classification
    ensure_classification(session, version)
    active = session.get(ActiveDataset, 1)
    if not active:
        session.add(ActiveDataset(id=1, version_id=version))
    elif activate:
        active.version_id = version
    session.commit()
    return report
