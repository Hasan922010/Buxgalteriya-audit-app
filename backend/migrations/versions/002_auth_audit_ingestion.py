"""Audit logs, document ingestion logs, users and organization memberships

Revision ID: 002_auth_audit_ingestion
Revises: 001_initial
Create Date: 2026-09-28 12:00:00.000000

Idempotent on purpose: existing databases were built with Base.metadata.create_all (no Alembic
history), so after `alembic stamp 001_initial` this revision only creates what is missing.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_auth_audit_ingestion'
down_revision = '001_initial'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in _inspector().get_columns(table)}


def _has_index(table: str, name: str) -> bool:
    return name in {i["name"] for i in _inspector().get_indexes(table)}


def upgrade() -> None:
    if not _has_column('counterparties', 'phone'):
        op.add_column('counterparties', sa.Column('phone', sa.String(length=50), nullable=True))

    if not _has_table('audit_logs'):
        op.create_table(
            'audit_logs',
            sa.Column('id', UUID, nullable=False),
            sa.Column('organization_id', UUID, sa.ForeignKey('organizations.id'), nullable=False),
            sa.Column('action', sa.String(length=50), nullable=False),
            sa.Column('entity_type', sa.String(length=50), nullable=False),
            sa.Column('entity_id', sa.String(length=100), nullable=True),
            sa.Column('performed_by', sa.String(length=100), nullable=True),
            sa.Column('details', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_audit_logs_organization_id', 'audit_logs', ['organization_id'])
        op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
        op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

    if not _has_table('document_ingestion_logs'):
        op.create_table(
            'document_ingestion_logs',
            sa.Column('id', UUID, nullable=False),
            sa.Column('organization_id', UUID, sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('document_type', sa.String(length=50), nullable=False),
            sa.Column('rows_parsed', sa.Integer(), nullable=True),
            sa.Column('rows_committed', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=True),
            sa.Column('metadata_info', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
    if not _has_column('document_ingestion_logs', 'file_sha256'):
        op.add_column('document_ingestion_logs', sa.Column('file_sha256', sa.String(length=64), nullable=True))
    if not _has_index('document_ingestion_logs', 'ix_document_ingestion_logs_file_sha256'):
        op.create_index('ix_document_ingestion_logs_file_sha256', 'document_ingestion_logs', ['file_sha256'])
    if not _has_index('document_ingestion_logs', 'uq_ingestion_org_file_completed'):
        op.create_index(
            'uq_ingestion_org_file_completed', 'document_ingestion_logs', ['organization_id', 'file_sha256'],
            unique=True,
            postgresql_where=sa.text("status = 'COMPLETED'"),
            sqlite_where=sa.text("status = 'COMPLETED'"),
        )

    if not _has_table('users'):
        op.create_table(
            'users',
            sa.Column('id', UUID, nullable=False),
            sa.Column('username', sa.String(length=64), nullable=False),
            sa.Column('full_name', sa.String(length=255), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('role', sa.String(length=32), nullable=False),
            sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_users_username', 'users', ['username'], unique=True)

    if not _has_table('user_organizations'):
        op.create_table(
            'user_organizations',
            sa.Column('user_id', UUID, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('organization_id', UUID, sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
            sa.PrimaryKeyConstraint('user_id', 'organization_id'),
        )
        op.create_index('ix_user_organizations_organization_id', 'user_organizations', ['organization_id'])


def downgrade() -> None:
    op.drop_table('user_organizations')
    op.drop_table('users')
    op.drop_index('uq_ingestion_org_file_completed', table_name='document_ingestion_logs')
    op.drop_index('ix_document_ingestion_logs_file_sha256', table_name='document_ingestion_logs')
    op.drop_column('document_ingestion_logs', 'file_sha256')
