"""Initial Accounting and BHMS Schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-09-27 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Chart of Accounts
    op.create_table(
        'chart_of_accounts',
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('account_type', sa.Enum('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE', name='accounttype'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
        sa.PrimaryKeyConstraint('code')
    )

    # 2. Organizations
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('inn', sa.String(length=9), nullable=False),
        sa.Column('mode', sa.Enum('SIMPLE', 'BHMS', name='accountingmode'), server_default='SIMPLE', nullable=False),
        sa.Column('vat_payer', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('created_at', sa.Date(), nullable=True),
        sa.Column('locked_until_date', sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('inn')
    )
    op.create_index(op.f('ix_organizations_inn'), 'organizations', ['inn'], unique=True)

    # 3. Counterparties
    op.create_table(
        'counterparties',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('inn', sa.String(length=9), nullable=True),
        sa.Column('mfo', sa.String(length=5), nullable=True),
        sa.Column('bank_account', sa.String(length=20), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('is_supplier', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('is_client', sa.Boolean(), server_default='true', nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_counterparties_inn'), 'counterparties', ['inn'], unique=False)
    op.create_index(op.f('ix_counterparties_name'), 'counterparties', ['name'], unique=False)
    op.create_index(op.f('ix_counterparties_organization_id'), 'counterparties', ['organization_id'], unique=False)

    # 4. Inventory Items
    op.create_table(
        'inventory_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('ikpu_code', sa.String(length=50), nullable=True),
        sa.Column('package_code', sa.String(length=50), nullable=True),
        sa.Column('unit', sa.String(length=50), server_default='dona', nullable=True),
        sa.Column('min_stock_alert', sa.Numeric(precision=15, scale=3), server_default='0', nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_items_ikpu_code'), 'inventory_items', ['ikpu_code'], unique=False)
    op.create_index(op.f('ix_inventory_items_name'), 'inventory_items', ['name'], unique=False)
    op.create_index(op.f('ix_inventory_items_organization_id'), 'inventory_items', ['organization_id'], unique=False)

    # 5. Transactions
    op.create_table(
        'transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doc_number', sa.String(length=100), nullable=True),
        sa.Column('doc_date', sa.Date(), nullable=False),
        sa.Column('doc_type', sa.String(length=50), nullable=False),
        sa.Column('debit_account', sa.String(length=10), nullable=True),
        sa.Column('credit_account', sa.String(length=10), nullable=True),
        sa.Column('counterparty_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=15, scale=3), server_default='0', nullable=True),
        sa.Column('price', sa.Numeric(precision=18, scale=2), server_default='0', nullable=True),
        sa.Column('total_amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('vat_rate', sa.Numeric(precision=5, scale=2), server_default='0', nullable=True),
        sa.Column('vat_amount', sa.Numeric(precision=18, scale=2), server_default='0', nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('raw_payload', sa.Text(), nullable=True),
        sa.Column('is_reversed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('reversal_ref_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reversal_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['counterparty_id'], ['counterparties.id'], ),
        sa.ForeignKeyConstraint(['credit_account'], ['chart_of_accounts.code'], ),
        sa.ForeignKeyConstraint(['debit_account'], ['chart_of_accounts.code'], ),
        sa.ForeignKeyConstraint(['item_id'], ['inventory_items.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transactions_credit_account'), 'transactions', ['credit_account'], unique=False)
    op.create_index(op.f('ix_transactions_debit_account'), 'transactions', ['debit_account'], unique=False)
    op.create_index(op.f('ix_transactions_doc_date'), 'transactions', ['doc_date'], unique=False)
    op.create_index(op.f('ix_transactions_doc_number'), 'transactions', ['doc_number'], unique=False)
    op.create_index(op.f('ix_transactions_is_reversed'), 'transactions', ['is_reversed'], unique=False)
    op.create_index(op.f('ix_transactions_organization_id'), 'transactions', ['organization_id'], unique=False)

def downgrade() -> None:
    op.drop_table('transactions')
    op.drop_table('inventory_items')
    op.drop_table('counterparties')
    op.drop_table('organizations')
    op.drop_table('chart_of_accounts')
