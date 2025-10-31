"""Phase 2: Video management schema with multipart upload support

Revision ID: 002_phase_2_video_mgmt
Revises: 839d4ee251e4
Create Date: 2025-10-31 12:00:00.000000

This migration extends the videos table with Phase 2 features:
- Multipart upload support (checksum, upload_id)
- Extended metadata (recorded_at, operator_notes, uploaded_by_user_id)
- Separate file paths for original and proxy
- Enhanced status tracking
- Adds processing_jobs table for Celery task tracking

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_phase_2_video_mgmt'
down_revision = '839d4ee251e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade to Phase 2 video management schema.

    Changes:
    1. Extend videos table with new fields
    2. Create processing_jobs table
    3. Add indexes for performance
    """

    # Step 1: Add new columns to videos table
    op.add_column('videos', sa.Column('mall_id', sa.UUID(), nullable=True))
    op.add_column('videos', sa.Column('pin_id', sa.UUID(), nullable=True))
    op.add_column('videos', sa.Column('filename', sa.String(length=255), nullable=True))
    op.add_column('videos', sa.Column('original_path', sa.String(length=512), nullable=True))
    op.add_column('videos', sa.Column('proxy_path', sa.String(length=512), nullable=True))
    op.add_column('videos', sa.Column('checksum_sha256', sa.String(length=64), nullable=True))
    op.add_column('videos', sa.Column('width', sa.Integer(), nullable=True))
    op.add_column('videos', sa.Column('height', sa.Integer(), nullable=True))
    op.add_column('videos', sa.Column('fps', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('videos', sa.Column('codec', sa.String(length=50), nullable=True))
    op.add_column('videos', sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('videos', sa.Column('operator_notes', sa.Text(), nullable=True))
    op.add_column('videos', sa.Column('uploaded_by_user_id', sa.UUID(), nullable=True))
    op.add_column('videos', sa.Column('upload_status', sa.String(length=20), nullable=True, server_default='uploading'))
    op.add_column('videos', sa.Column('processing_job_id', sa.String(length=255), nullable=True))
    op.add_column('videos', sa.Column('processing_error', sa.Text(), nullable=True))
    op.add_column('videos', sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('videos', sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('videos', sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('videos', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    # Step 2: Migrate existing data
    # Set mall_id from camera_pin relationship
    op.execute("""
        UPDATE videos v
        SET mall_id = cp.mall_id,
            pin_id = v.camera_pin_id,
            filename = v.original_filename,
            original_path = v.file_path,
            upload_status = 'uploaded',
            uploaded_at = v.upload_timestamp,
            updated_at = v.created_at
        FROM camera_pins cp
        WHERE v.camera_pin_id = cp.id
    """)

    # Step 3: Make new columns NOT NULL after data migration
    op.alter_column('videos', 'mall_id', nullable=False)
    op.alter_column('videos', 'pin_id', nullable=False)
    op.alter_column('videos', 'filename', nullable=False)
    op.alter_column('videos', 'upload_status', nullable=False)
    op.alter_column('videos', 'uploaded_at', nullable=False)
    op.alter_column('videos', 'updated_at', nullable=False)

    # Step 4: Add foreign key constraints
    op.create_foreign_key(
        'fk_videos_mall_id',
        'videos', 'malls',
        ['mall_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_videos_pin_id',
        'videos', 'camera_pins',
        ['pin_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_videos_uploaded_by',
        'videos', 'users',
        ['uploaded_by_user_id'], ['id'],
        ondelete='SET NULL'
    )

    # Step 5: Add new indexes
    op.create_index('ix_videos_mall_id', 'videos', ['mall_id'])
    op.create_index('ix_videos_pin_id', 'videos', ['pin_id'])
    op.create_index('ix_videos_checksum', 'videos', ['checksum_sha256'])
    op.create_index('ix_videos_uploaded_at', 'videos', ['uploaded_at'], postgresql_ops={'uploaded_at': 'DESC'})
    op.create_index('ix_videos_recorded_at', 'videos', ['recorded_at'], postgresql_ops={'recorded_at': 'DESC'})
    op.create_index('ix_videos_upload_status', 'videos', ['upload_status'])

    # Step 6: Add unique constraint for deduplication
    op.create_index(
        'ix_videos_unique_checksum_pin',
        'videos',
        ['checksum_sha256', 'pin_id'],
        unique=True,
        postgresql_where=sa.text('checksum_sha256 IS NOT NULL')
    )

    # Step 7: Create processing_jobs table
    op.create_table(
        'processing_jobs',
        sa.Column('id', sa.UUID(), nullable=False, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('video_id', sa.UUID(), nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('worker_hostname', sa.String(length=255), nullable=True),
        sa.Column('result_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('queued_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Step 8: Add indexes to processing_jobs
    op.create_index('ix_jobs_video_id', 'processing_jobs', ['video_id'])
    op.create_index('ix_jobs_status', 'processing_jobs', ['status'])
    op.create_index('ix_jobs_celery_task_id', 'processing_jobs', ['celery_task_id'])
    op.create_index('ix_jobs_queued_at', 'processing_jobs', ['queued_at'], postgresql_ops={'queued_at': 'DESC'})

    # Step 9: Drop old columns (keep for backward compatibility initially)
    # These can be dropped after verifying migration success:
    # - file_path (replaced by original_path)
    # - original_filename (replaced by filename)
    # - processed (replaced by upload_status/processing_status)
    # - upload_timestamp (replaced by uploaded_at)

    print("✅ Phase 2 video management schema migration completed")


def downgrade() -> None:
    """
    Downgrade from Phase 2 to Phase 1 schema.

    WARNING: This will lose Phase 2 data (processing_jobs, checksums, metadata).
    """

    # Drop processing_jobs table
    op.drop_index('ix_jobs_queued_at', table_name='processing_jobs')
    op.drop_index('ix_jobs_celery_task_id', table_name='processing_jobs')
    op.drop_index('ix_jobs_status', table_name='processing_jobs')
    op.drop_index('ix_jobs_video_id', table_name='processing_jobs')
    op.drop_table('processing_jobs')

    # Drop new indexes from videos
    op.drop_index('ix_videos_unique_checksum_pin', table_name='videos')
    op.drop_index('ix_videos_upload_status', table_name='videos')
    op.drop_index('ix_videos_recorded_at', table_name='videos')
    op.drop_index('ix_videos_uploaded_at', table_name='videos')
    op.drop_index('ix_videos_checksum', table_name='videos')
    op.drop_index('ix_videos_pin_id', table_name='videos')
    op.drop_index('ix_videos_mall_id', table_name='videos')

    # Drop foreign key constraints
    op.drop_constraint('fk_videos_uploaded_by', 'videos', type_='foreignkey')
    op.drop_constraint('fk_videos_pin_id', 'videos', type_='foreignkey')
    op.drop_constraint('fk_videos_mall_id', 'videos', type_='foreignkey')

    # Drop new columns from videos
    op.drop_column('videos', 'updated_at')
    op.drop_column('videos', 'processing_completed_at')
    op.drop_column('videos', 'processing_started_at')
    op.drop_column('videos', 'uploaded_at')
    op.drop_column('videos', 'processing_error')
    op.drop_column('videos', 'processing_job_id')
    op.drop_column('videos', 'upload_status')
    op.drop_column('videos', 'uploaded_by_user_id')
    op.drop_column('videos', 'operator_notes')
    op.drop_column('videos', 'recorded_at')
    op.drop_column('videos', 'codec')
    op.drop_column('videos', 'fps')
    op.drop_column('videos', 'height')
    op.drop_column('videos', 'width')
    op.drop_column('videos', 'checksum_sha256')
    op.drop_column('videos', 'proxy_path')
    op.drop_column('videos', 'original_path')
    op.drop_column('videos', 'filename')
    op.drop_column('videos', 'pin_id')
    op.drop_column('videos', 'mall_id')

    print("⚠️  Phase 2 video management schema downgrade completed")
