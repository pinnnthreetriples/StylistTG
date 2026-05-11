"""Add asset storage metadata fields."""

from alembic import op
import sqlalchemy as sa


revision = "20260430_0020"
down_revision = "20260430_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("asset", sa.Column("storage_backend", sa.String(length=32), nullable=True))
    op.add_column("asset", sa.Column("storage_bucket", sa.String(length=255), nullable=True))
    op.add_column("asset", sa.Column("source_key", sa.Text(), nullable=True))
    op.add_column("asset", sa.Column("normalized_key", sa.Text(), nullable=True))
    op.add_column("asset", sa.Column("source_size_bytes", sa.Integer(), nullable=True))
    op.add_column("asset", sa.Column("normalized_size_bytes", sa.Integer(), nullable=True))
    op.add_column("asset", sa.Column("source_content_type", sa.String(length=128), nullable=True))
    op.add_column(
        "asset", sa.Column("normalized_content_type", sa.String(length=128), nullable=True)
    )
    op.add_column("asset", sa.Column("source_checksum", sa.String(length=128), nullable=True))
    op.add_column("asset", sa.Column("normalized_checksum", sa.String(length=128), nullable=True))
    op.add_column(
        "asset", sa.Column("storage_migrated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_asset_workspace_storage", "asset", ["workspace_id", "storage_backend"])

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            update asset
            set
                storage_backend = 'local',
                source_key = replace(source_path, '\\', '/'),
                normalized_key = replace(normalized_path, '\\', '/'),
                source_content_type = mime,
                normalized_content_type = mime,
                normalized_checksum = content_hash,
                storage_migrated_at = CURRENT_TIMESTAMP
            where storage_backend is null
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_asset_workspace_storage", table_name="asset")
    op.drop_column("asset", "storage_migrated_at")
    op.drop_column("asset", "normalized_checksum")
    op.drop_column("asset", "source_checksum")
    op.drop_column("asset", "normalized_content_type")
    op.drop_column("asset", "source_content_type")
    op.drop_column("asset", "normalized_size_bytes")
    op.drop_column("asset", "source_size_bytes")
    op.drop_column("asset", "normalized_key")
    op.drop_column("asset", "source_key")
    op.drop_column("asset", "storage_bucket")
    op.drop_column("asset", "storage_backend")
