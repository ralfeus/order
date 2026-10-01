"""Product composite primary key (id, vendor)

Revision ID: c8b2d3e4f5a6
Revises: b7a1c2d3e4f5
Create Date: 2026-09-30 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8b2d3e4f5a6'
down_revision = 'b7a1c2d3e4f5'
branch_labels = None
depends_on = None

DEFAULT_VENDOR = 'Atomy'
# Tables referring to products
REFERENCES = ['order_products', 'invoice_items', 'products_shipping', 'warehouse_products']


def _product_foreign_keys(table: str) -> list[str]:
    '''Returns names of foreign keys of the table referring to products.
    Names differ between environments so they are looked up'''
    return list(op.get_bind().execute(sa.text("""
        SELECT DISTINCT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table
            AND REFERENCED_TABLE_NAME = 'products'
    """), {'table': table}).scalars())


def _drop_product_foreign_keys(table: str):
    for name in _product_foreign_keys(table):
        op.drop_constraint(name, table, type_='foreignkey')


def upgrade():
    for table in REFERENCES:
        _drop_product_foreign_keys(table)

    op.add_column('order_products', sa.Column('product_vendor', sa.String(16)))
    op.add_column('invoice_items', sa.Column('product_vendor', sa.String(16)))
    op.add_column('products_shipping', sa.Column('product_vendor', sa.String(16)))
    # Part of primary key so can't be NULL
    op.add_column('warehouse_products', sa.Column(
        'product_vendor', sa.String(16), nullable=False, server_default=DEFAULT_VENDOR))
    op.alter_column('warehouse_products', 'product_vendor', server_default=None,
                    existing_type=sa.String(16), existing_nullable=False)
    # All existing products are of default vendor. References to non-existing
    # products (e.g. "SHIPPING" invoice item if there is no such product) stay NULL
    for table in ['order_products', 'invoice_items', 'products_shipping']:
        op.execute(f"""
            UPDATE {table} SET product_vendor = '{DEFAULT_VENDOR}'
            WHERE product_id IN (SELECT id FROM products)
        """)

    op.execute("ALTER TABLE products DROP PRIMARY KEY, ADD PRIMARY KEY (id, vendor)")
    op.execute("""
        ALTER TABLE warehouse_products DROP PRIMARY KEY,
            ADD PRIMARY KEY (warehouse_id, product_id, product_vendor)
    """)
    op.drop_constraint('product_shipping', 'products_shipping', type_='unique')
    op.create_unique_constraint('product_shipping', 'products_shipping',
                                ['product_id', 'product_vendor', 'shipping_method_id'])

    for table in REFERENCES:
        op.create_foreign_key(f'fk_{table}_product', table, 'products',
                              ['product_id', 'product_vendor'], ['id', 'vendor'])


def downgrade():
    other_vendors = op.get_bind().execute(sa.text(
        f"SELECT COUNT(*) FROM products WHERE vendor <> '{DEFAULT_VENDOR}'")).scalar()
    if other_vendors:
        raise Exception(
            f"Can't downgrade: there are {other_vendors} products of vendors "
            f"other than {DEFAULT_VENDOR}")

    for table in REFERENCES:
        _drop_product_foreign_keys(table)

    op.drop_constraint('product_shipping', 'products_shipping', type_='unique')
    op.create_unique_constraint('product_shipping', 'products_shipping',
                                ['product_id', 'shipping_method_id'])
    op.execute("""
        ALTER TABLE warehouse_products DROP PRIMARY KEY,
            ADD PRIMARY KEY (warehouse_id, product_id)
    """)
    op.execute("ALTER TABLE products DROP PRIMARY KEY, ADD PRIMARY KEY (id)")

    for table in REFERENCES:
        op.drop_column(table, 'product_vendor')
        op.create_foreign_key(None, table, 'products', ['product_id'], ['id'])
