"""wp9 deletion marker on selection history; no location in stored raw fields

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-24 13:50:00
"""
import json

from alembic import op
import sqlalchemy as sa

from backend.importers.location import is_location_field

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ride_selection_history',
                  sa.Column('source_deleted', sa.Boolean(), server_default='0', nullable=False))
    # Spec 8.2: raw record fields copied into the database keep no position. The vault keeps the original bytes.
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT activity_id, sample_index, original_field_json FROM samples "
                                "WHERE original_field_json LIKE '%lat%' OR original_field_json LIKE '%long%' "
                                "OR original_field_json LIKE '%position%'")).all()
    for aid, idx, doc in rows:
        fields = json.loads(doc)
        kept = {k: v for k, v in fields.items() if not is_location_field(k)}
        if kept != fields:
            conn.execute(sa.text("UPDATE samples SET original_field_json = :d WHERE activity_id = :a AND sample_index = :i"),
                         {"d": json.dumps(kept, default=str, sort_keys=True), "a": aid, "i": idx})


def downgrade() -> None:
    with op.batch_alter_table('ride_selection_history') as b:
        b.drop_column('source_deleted')
