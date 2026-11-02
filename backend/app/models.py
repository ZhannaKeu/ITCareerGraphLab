from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, UniqueConstraint, CheckConstraint, JSON, DateTime, ForeignKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str]
    is_demo: Mapped[bool] = mapped_column(default=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    manifest: Mapped[dict] = mapped_column(JSON)
    quality: Mapped[dict] = mapped_column(JSON)

class ActiveDataset(Base):
    __tablename__ = "active_dataset"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    __table_args__ = (CheckConstraint("id = 1"),)

class Skill(Base):
    __tablename__ = "skills"
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    category: Mapped[str]
    description: Mapped[str] = mapped_column(default="")

class Profile(Base):
    __tablename__ = "profiles"
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    role: Mapped[str]
    level: Mapped[str]

class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    profile_id: Mapped[str]
    skill_id: Mapped[str | None]
    group_id: Mapped[str | None]
    required_level: Mapped[float | None]
    original_weight: Mapped[float]
    weight_origin: Mapped[str]
    __table_args__ = (UniqueConstraint("version_id", "profile_id", "skill_id", "group_id"), CheckConstraint("required_level IS NULL OR (required_level >= 0 AND required_level <= 4)"),)

class Prerequisite(Base):
    __tablename__ = "prerequisites"
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), primary_key=True)
    prerequisite_id: Mapped[str] = mapped_column(primary_key=True)
    skill_id: Mapped[str] = mapped_column(primary_key=True)
    __table_args__ = (CheckConstraint("prerequisite_id <> skill_id"),)

class SkillWeight(Base):
    __tablename__ = "skill_weights"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    source: Mapped[str]
    role: Mapped[str]
    skill_id: Mapped[str]
    weight: Mapped[float]
    __table_args__ = (UniqueConstraint("version_id", "source", "role", "skill_id"), CheckConstraint("weight >= 0"),)

class SourceRecord(Base):
    """Lossless logical CSV rows: mappings, groups, levels, courses and all other inputs."""
    __tablename__ = "source_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    filename: Mapped[str]
    row_number: Mapped[int]
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("version_id", "filename", "row_number"),)

class SkillGroup(Base):
    __tablename__ = "skill_groups"
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]

class SkillMapping(Base):
    __tablename__ = "skill_mappings"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    skill_id: Mapped[str]
    group_id: Mapped[str]
    __table_args__ = (UniqueConstraint("version_id", "skill_id", "group_id"),)

class SkillLevel(Base):
    __tablename__ = "skill_levels"
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), primary_key=True)
    level: Mapped[float] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str]
    __table_args__ = (CheckConstraint("level >= 0 AND level <= 4"),)

class CourseSkill(Base):
    __tablename__ = "course_skills"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    course_id: Mapped[str]
    skill_id: Mapped[str]
    contribution: Mapped[float]
    note: Mapped[str]
    __table_args__ = (UniqueConstraint("version_id", "course_id", "skill_id"),)


class SurveyMapping(Base):
    __tablename__ = "survey_mappings"
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), primary_key=True)
    survey_name: Mapped[str] = mapped_column(primary_key=True)
    skill_id: Mapped[str | None]
    action: Mapped[str]

class SkillDependencyCount(Base):
    __tablename__ = "skill_dependency_counts"
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), primary_key=True)
    skill_id: Mapped[str] = mapped_column(primary_key=True)
    dependents: Mapped[int]
    prerequisites: Mapped[int]

# Version-scoped references prevent links across immutable dataset versions.
for model, field, target in [
    (Requirement,"profile_id","profiles.id"), (Requirement,"skill_id","skills.id"),
    (Requirement,"group_id","skill_groups.id"), (Prerequisite,"prerequisite_id","skills.id"),
    (Prerequisite,"skill_id","skills.id"), (SkillWeight,"skill_id","skills.id"),
    (SkillMapping,"skill_id","skills.id"), (SkillMapping,"group_id","skill_groups.id"),
    (CourseSkill,"skill_id","skills.id"), (SurveyMapping,"skill_id","skills.id"),
    (SkillDependencyCount,"skill_id","skills.id")]:
    table = target.split(".")[0]
    model.__table__.append_constraint(ForeignKeyConstraint(["version_id",field],[f"{table}.version_id",target]))
Requirement.__table__.append_constraint(CheckConstraint("(skill_id IS NOT NULL AND group_id IS NULL) OR (skill_id IS NULL AND group_id IS NOT NULL)",name="requirement_exactly_one_item"))

class DatasetLineage(Base):
    """Immutable interpretation/provenance envelope, separate from original byte hashes."""
    __tablename__ = "dataset_lineage"
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_versions.id"))
    root_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    kind: Mapped[str]
    author: Mapped[str]
    reason: Mapped[str]
    disclosure: Mapped[dict] = mapped_column(JSON)
    record_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (CheckConstraint("kind IN ('original','corrected')"),)

class RecordProvenance(Base):
    __tablename__ = "record_provenance"
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), primary_key=True)
    entity: Mapped[str] = mapped_column(primary_key=True)
    record_key: Mapped[str] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(default="Unverified")
    origin: Mapped[dict] = mapped_column(JSON)
    reviewer: Mapped[str | None]
    evidence: Mapped[str | None]
    verification_note: Mapped[str | None]
    __table_args__ = (CheckConstraint("status IN ('Unverified','Expert Verified','Source Verified')", name="valid_verification_status"),
        CheckConstraint("status = 'Unverified' OR (reviewer IS NOT NULL AND length(trim(reviewer)) > 0 AND evidence IS NOT NULL AND length(trim(evidence)) > 0)", name="verification_requires_evidence"),)

class ChangeEvent(Base):
    __tablename__ = "change_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    sequence: Mapped[int]
    entity: Mapped[str]
    record_key: Mapped[str]
    operation: Mapped[str]
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    author: Mapped[str]
    reason: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("version_id", "sequence"),)

class ExperimentRun(Base):
    __tablename__ = "experiment_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    kind: Mapped[str]
    parameters: Mapped[dict] = mapped_column(JSON)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PrerequisiteClassification(Base):
    """Frozen preliminary overlay; independent of historical dataset/status hashes."""
    __tablename__ = "prerequisite_classifications"
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), primary_key=True)
    edge_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    from_skill: Mapped[str]
    to_skill: Mapped[str]
    source_row: Mapped[int]
    relation_type: Mapped[str]
    min_level: Mapped[float | None]
    classification_source: Mapped[str]
    verification_status: Mapped[str]
    protocol: Mapped[str]
    __table_args__ = (
        UniqueConstraint("version_id", "source_row"),
        UniqueConstraint("version_id", "from_skill", "to_skill"),
        CheckConstraint("relation_type IN ('Required','Recommended','Related')"),
        CheckConstraint("verification_status = 'Unverified'", name="preliminary_classification_unverified"),
        CheckConstraint("min_level IS NULL", name="preliminary_min_level_unset"),
        CheckConstraint("source_row >= 1 AND source_row <= 51"),
        ForeignKeyConstraint(["version_id","from_skill"],["skills.version_id","skills.id"]),
        ForeignKeyConstraint(["version_id","to_skill"],["skills.version_id","skills.id"]),
    )
