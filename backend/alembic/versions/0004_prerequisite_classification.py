"""Frozen AI-assisted prerequisite relation classification, separate from original data."""
from alembic import op
import sqlalchemy as sa
revision = "0004"
down_revision = "0003"
branch_labels = depends_on = None

def upgrade():
    op.create_table("prerequisite_classifications",
        sa.Column("version_id",sa.String(64),sa.ForeignKey("dataset_versions.id"),primary_key=True),
        sa.Column("edge_id",sa.String(64),primary_key=True),
        sa.Column("from_skill",sa.String(),nullable=False),sa.Column("to_skill",sa.String(),nullable=False),
        sa.Column("source_row",sa.Integer(),nullable=False),sa.Column("relation_type",sa.String(),nullable=False),
        sa.Column("min_level",sa.Float()),sa.Column("classification_source",sa.String(),nullable=False),
        sa.Column("verification_status",sa.String(),nullable=False),sa.Column("protocol",sa.String(),nullable=False),
        sa.UniqueConstraint("version_id","source_row"),sa.UniqueConstraint("version_id","from_skill","to_skill"),
        sa.CheckConstraint("relation_type IN ('Required','Recommended','Related')"),
        sa.CheckConstraint("verification_status = 'Unverified'",name="preliminary_classification_unverified"),
        sa.CheckConstraint("min_level IS NULL",name="preliminary_min_level_unset"),
        sa.CheckConstraint("source_row >= 1 AND source_row <= 51"),
        sa.ForeignKeyConstraint(["version_id","from_skill"],["skills.version_id","skills.id"]),
        sa.ForeignKeyConstraint(["version_id","to_skill"],["skills.version_id","skills.id"]))

def downgrade():
    op.drop_table("prerequisite_classifications")
