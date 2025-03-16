"""change_event_tenant_id_to_integer

Revision ID: 3a1b2c3d4e5f
Revises: 
Create Date: 2023-03-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a1b2c3d4e5f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # First, create a temporary column with the correct type
    op.add_column('events', sa.Column('tenant_id_new', sa.Integer(), nullable=True))
    
    # Update the temporary column with converted values
    op.execute("UPDATE events SET tenant_id_new = CASE WHEN tenant_id ~ E'^\\\\d+$' THEN tenant_id::integer ELSE 1 END")
    
    # Drop the old column and rename the new one
    op.drop_column('events', 'tenant_id')
    op.alter_column('events', 'tenant_id_new', new_column_name='tenant_id')
    
    # Add foreign key constraint and not null constraint
    op.alter_column('events', 'tenant_id', nullable=False)
    op.create_foreign_key('fk_events_tenant_id_tenants', 'events', 'tenants', ['tenant_id'], ['id'])
    
    # Add default value for new rows
    op.execute("ALTER TABLE events ALTER COLUMN tenant_id SET DEFAULT 1")


def downgrade():
    # Remove foreign key constraint
    op.drop_constraint('fk_events_tenant_id_tenants', 'events', type_='foreignkey')
    
    # Create a temporary column with the old type
    op.add_column('events', sa.Column('tenant_id_old', sa.String(), nullable=True))
    
    # Update the temporary column with converted values
    op.execute("UPDATE events SET tenant_id_old = tenant_id::text")
    
    # Drop the new column and rename the old one back
    op.drop_column('events', 'tenant_id')
    op.alter_column('events', 'tenant_id_old', new_column_name='tenant_id')
    
    # Add not null constraint and default value
    op.alter_column('events', 'tenant_id', nullable=False)
    op.execute("ALTER TABLE events ALTER COLUMN tenant_id SET DEFAULT 'default'") 