"""Immutable provenance, reviewed revisions, audit history and persisted experiments."""
from alembic import op
import sqlalchemy as sa
revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None

def upgrade():
    def version(name="version_id", pk=False):
        return sa.Column(name,sa.String(64),sa.ForeignKey("dataset_versions.id"),primary_key=pk,nullable=False)
    op.create_table("dataset_lineage",version(pk=True),sa.Column("parent_id",sa.String(64),sa.ForeignKey("dataset_versions.id")),version("root_id"),
        sa.Column("kind",sa.String(),nullable=False),sa.Column("author",sa.String(),nullable=False),sa.Column("reason",sa.String(),nullable=False),
        sa.Column("disclosure",sa.JSON(),nullable=False),sa.Column("record_hash",sa.String(64),nullable=False),sa.CheckConstraint("kind IN ('original','corrected')"))
    op.create_table("record_provenance",version(pk=True),sa.Column("entity",sa.String(),primary_key=True),sa.Column("record_key",sa.String(),primary_key=True),
        sa.Column("status",sa.String(),nullable=False),sa.Column("origin",sa.JSON(),nullable=False),sa.Column("reviewer",sa.String()),sa.Column("evidence",sa.String()),sa.Column("verification_note",sa.String()),
        sa.CheckConstraint("status IN ('Unverified','Expert Verified','Source Verified')",name="valid_verification_status"),
        sa.CheckConstraint("status = 'Unverified' OR (reviewer IS NOT NULL AND length(trim(reviewer)) > 0 AND evidence IS NOT NULL AND length(trim(evidence)) > 0)",name="verification_requires_evidence"))
    op.create_table("change_events",sa.Column("id",sa.Integer(),primary_key=True),version(),sa.Column("sequence",sa.Integer(),nullable=False),
        sa.Column("entity",sa.String(),nullable=False),sa.Column("record_key",sa.String(),nullable=False),sa.Column("operation",sa.String(),nullable=False),
        sa.Column("before",sa.JSON()),sa.Column("after",sa.JSON()),sa.Column("author",sa.String(),nullable=False),sa.Column("reason",sa.String(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("version_id","sequence"))
    op.create_index("ix_change_events_version_id","change_events",["version_id"])
    op.create_table("experiment_runs",sa.Column("id",sa.String(64),primary_key=True),version(),sa.Column("kind",sa.String(),nullable=False),
        sa.Column("parameters",sa.JSON(),nullable=False),sa.Column("payload",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_experiment_runs_version_id","experiment_runs",["version_id"])
    # Existing dataset IDs, source bytes and scores are retained. Import's idempotent
    # initialization adds conservative Unverified envelopes for pre-existing datasets.

def downgrade():
    for table in ["experiment_runs","change_events","record_provenance","dataset_lineage"]:
        op.drop_table(table)
