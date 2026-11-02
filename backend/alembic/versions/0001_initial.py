"""Versioned datasets and normalized research entities; pgvector reserved for NLP extension."""
from alembic import op
import sqlalchemy as sa
revision = "0001"
down_revision = None
branch_labels = depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table("dataset_versions", sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("label", sa.String(), nullable=False), sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False), sa.Column("manifest", sa.JSON(), nullable=False), sa.Column("quality", sa.JSON(), nullable=False))
    def ver(pk=False):
        return sa.Column("version_id", sa.String(64), sa.ForeignKey("dataset_versions.id"), primary_key=pk, nullable=False)
    op.create_table("active_dataset", sa.Column("id", sa.Integer(), primary_key=True), ver(), sa.CheckConstraint("id = 1"))
    op.create_table("skills", ver(True), sa.Column("id", sa.String(), primary_key=True), sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False), sa.Column("description", sa.String(), nullable=False))
    op.create_table("profiles", ver(True), sa.Column("id", sa.String(), primary_key=True), sa.Column("role", sa.String(), nullable=False), sa.Column("level", sa.String(), nullable=False))
    op.create_table("requirements", sa.Column("id", sa.Integer(), primary_key=True), ver(), sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("skill_id", sa.String()), sa.Column("group_id", sa.String()), sa.Column("required_level", sa.Float()),
        sa.UniqueConstraint("version_id", "profile_id", "skill_id", "group_id"), sa.CheckConstraint("required_level IS NULL OR (required_level >= 0 AND required_level <= 4)"))
    op.create_table("prerequisites", ver(True), sa.Column("prerequisite_id", sa.String(), primary_key=True), sa.Column("skill_id", sa.String(), primary_key=True), sa.CheckConstraint("prerequisite_id <> skill_id"))
    op.create_table("skill_weights", sa.Column("id", sa.Integer(), primary_key=True), ver(), sa.Column("source", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False), sa.Column("skill_id", sa.String(), nullable=False), sa.Column("weight", sa.Float(), nullable=False),
        sa.UniqueConstraint("version_id", "source", "role", "skill_id"), sa.CheckConstraint("weight >= 0"))
    op.create_table("source_records", sa.Column("id", sa.Integer(), primary_key=True), ver(), sa.Column("filename", sa.String(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False), sa.Column("data", sa.JSON(), nullable=False), sa.UniqueConstraint("version_id", "filename", "row_number"))
    op.create_table("skill_groups", ver(True), sa.Column("id", sa.String(), primary_key=True), sa.Column("name", sa.String(), nullable=False))
    op.create_table("skill_mappings", sa.Column("id", sa.Integer(), primary_key=True), ver(), sa.Column("skill_id", sa.String(), nullable=False), sa.Column("group_id", sa.String(), nullable=False), sa.UniqueConstraint("version_id", "skill_id", "group_id"))
    op.create_table("skill_levels", ver(True), sa.Column("level", sa.Float(), primary_key=True), sa.Column("name", sa.String(), nullable=False), sa.CheckConstraint("level >= 0 AND level <= 4"))
    op.create_table("course_skills", sa.Column("id", sa.Integer(), primary_key=True), ver(), sa.Column("course_id", sa.String(), nullable=False), sa.Column("skill_id", sa.String(), nullable=False), sa.UniqueConstraint("version_id", "course_id", "skill_id"))
    for table in ["requirements", "skill_weights", "source_records", "skill_mappings", "course_skills"]:
        op.create_index(f"ix_{table}_version_id", table, ["version_id"])


def downgrade():
    for table in ["course_skills", "skill_levels", "skill_mappings", "skill_groups", "source_records", "skill_weights", "prerequisites", "requirements", "profiles", "skills", "active_dataset", "dataset_versions"]:
        op.drop_table(table)
    # Shared vector extension intentionally retained.
