"""cleanup products_shipping

Revision ID: 58dbba4ccddd
Revises: 8090c06d2b01
Create Date: 2023-06-02 12:39:32.676993

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '58dbba4ccddd'
down_revision = '8090c06d2b01'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE products_shipping_temp (
            product_id varchar(16) CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci NOT NULL,
            shipping_method_id int,
            KEY product_id (product_id),
            KEY shipping_method_id (shipping_method_id),
            CONSTRAINT FOREIGN KEY (product_id) REFERENCES products (id),   
            CONSTRAINT FOREIGN KEY (shipping_method_id) REFERENCES shipping (id), 
            UNIQUE product_shipping(product_id,shipping_method_id)
        )
    """)
    op.execute("INSERT INTO products_shipping_temp SELECT DISTINCT * FROM products_shipping")
    op.execute("DROP TABLE products_shipping")
    op.execute("ALTER TABLE products_shipping_temp RENAME TO products_shipping")


def downgrade():
    pass
