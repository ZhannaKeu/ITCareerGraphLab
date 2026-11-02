"""Preserve observed CSV semantics and enforce version-scoped references."""
from alembic import op
import sqlalchemy as sa
revision = '0002'
down_revision = '0001'
branch_labels = depends_on = None
REFERENCES = [
 ('requirements','profile_id','profiles'), ('requirements','skill_id','skills'),
 ('requirements','group_id','skill_groups'), ('prerequisites','prerequisite_id','skills'),
 ('prerequisites','skill_id','skills'), ('skill_weights','skill_id','skills'),
 ('skill_mappings','skill_id','skills'), ('skill_mappings','group_id','skill_groups'),
 ('course_skills','skill_id','skills'), ('survey_mappings','skill_id','skills'),
 ('skill_dependency_counts','skill_id','skills')]

def upgrade():
    with op.batch_alter_table('requirements') as b:
        b.add_column(sa.Column('original_weight',sa.Float(),nullable=False,server_default='1'))
        b.add_column(sa.Column('weight_origin',sa.String(),nullable=False,server_default='unspecified'))
        b.create_check_constraint('requirement_exactly_one_item','(skill_id IS NOT NULL AND group_id IS NULL) OR (skill_id IS NULL AND group_id IS NOT NULL)')
    with op.batch_alter_table('skill_levels') as b:
        b.add_column(sa.Column('description',sa.String(),nullable=False,server_default=''))
    with op.batch_alter_table('course_skills') as b:
        b.add_column(sa.Column('contribution',sa.Float(),nullable=False,server_default='0'))
        b.add_column(sa.Column('note',sa.String(),nullable=False,server_default=''))
    op.create_table('survey_mappings',sa.Column('version_id',sa.String(64),sa.ForeignKey('dataset_versions.id'),primary_key=True),sa.Column('survey_name',sa.String(),primary_key=True),sa.Column('skill_id',sa.String()),sa.Column('action',sa.String(),nullable=False))
    op.create_table('skill_dependency_counts',sa.Column('version_id',sa.String(64),sa.ForeignKey('dataset_versions.id'),primary_key=True),sa.Column('skill_id',sa.String(),primary_key=True),sa.Column('dependents',sa.Integer(),nullable=False),sa.Column('prerequisites',sa.Integer(),nullable=False))
    for table,field,target in REFERENCES:
        with op.batch_alter_table(table) as b:
            b.create_foreign_key(f'fk_{table}_{field}',target,['version_id',field],['version_id','id'])

def downgrade():
    for table,field,target in reversed(REFERENCES):
        with op.batch_alter_table(table) as b:
            b.drop_constraint(f'fk_{table}_{field}',type_='foreignkey')
    op.drop_table('skill_dependency_counts')
    op.drop_table('survey_mappings')
    with op.batch_alter_table('requirements') as b:
        b.drop_constraint('requirement_exactly_one_item',type_='check')
        b.drop_column('original_weight'); b.drop_column('weight_origin')
    with op.batch_alter_table('skill_levels') as b:
        b.drop_column('description')
    with op.batch_alter_table('course_skills') as b:
        b.drop_column('contribution'); b.drop_column('note')
