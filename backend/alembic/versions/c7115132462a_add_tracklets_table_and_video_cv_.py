"""Add tracklets table and video cv_processed fields

Revision ID: c7115132462a
Revises: 002_phase_2_video_mgmt
Create Date: 2025-11-01 15:43:04.784923

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7115132462a'
down_revision = '002_phase_2_video_mgmt'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)

    # Add CV processing fields to videos table (check if not exists)
    existing_cols = [c['name'] for c in inspector.get_columns('videos')]

    if 'cv_processed' not in existing_cols:
        op.add_column('videos', sa.Column('cv_processed', sa.Boolean(), nullable=False, server_default='false'))

    if 'tracklet_count' not in existing_cols:
        op.add_column('videos', sa.Column('tracklet_count', sa.Integer(), nullable=False, server_default='0'))

    if 'cv_job_id' not in existing_cols:
        op.add_column('videos', sa.Column('cv_job_id', sa.UUID(), nullable=True))
        # Add foreign key for cv_job_id
        op.create_foreign_key(
            'fk_videos_cv_job_id',
            'videos', 'processing_jobs',
            ['cv_job_id'], ['id'],
            ondelete='SET NULL'
        )

    # Create tracklets table only if it doesn't exist
    if 'tracklets' not in inspector.get_table_names():
        op.create_table(
        'tracklets',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('mall_id', sa.UUID(), nullable=False),
        sa.Column('pin_id', sa.UUID(), nullable=False),
        sa.Column('video_id', sa.UUID(), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('t_in', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('t_out', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('duration_seconds', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('outfit_vec', sa.LargeBinary(), nullable=False),  # 512 bytes (128 floats)
        sa.Column('outfit_json', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('physique', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('box_stats', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('quality', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['mall_id'], ['malls.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pin_id'], ['camera_pins.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
    )

        # Create indexes for tracklets
        op.create_index('idx_tracklets_video_id', 'tracklets', ['video_id'])
        op.create_index('idx_tracklets_pin_id', 'tracklets', ['pin_id'])
        op.create_index('idx_tracklets_mall_id', 'tracklets', ['mall_id'])
        op.create_index('idx_tracklets_time', 'tracklets', ['t_in', 't_out'])
        op.create_index('idx_tracklets_quality', 'tracklets', ['quality'], postgresql_using='btree', postgresql_ops={'quality': 'DESC'})


def downgrade() -> None:
    # Drop tracklets indexes
    op.drop_index('idx_tracklets_quality', table_name='tracklets')
    op.drop_index('idx_tracklets_time', table_name='tracklets')
    op.drop_index('idx_tracklets_mall_id', table_name='tracklets')
    op.drop_index('idx_tracklets_pin_id', table_name='tracklets')
    op.drop_index('idx_tracklets_video_id', table_name='tracklets')

    # Drop tracklets table
    op.drop_table('tracklets')

    # Drop foreign key and columns from videos table
    op.drop_constraint('fk_videos_cv_job_id', 'videos', type_='foreignkey')
    op.drop_column('videos', 'cv_job_id')
    op.drop_column('videos', 'tracklet_count')
    op.drop_column('videos', 'cv_processed')
