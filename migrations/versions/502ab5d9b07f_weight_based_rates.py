"""Weight based rates

Revision ID: 502ab5d9b07f
Revises: acaa84d33edc
Create Date: 2022-04-24 14:04:18.168314

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '502ab5d9b07f'
down_revision = 'acaa84d33edc'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE shipping 
        SET discriminator = 'weight_based'
        WHERE discriminator IS NULL AND id NOT IN (2, 3)
    """)
    op.execute("""
        INSERT INTO shipping_weight_based_rates (shipping_id, destination, minimum_weight, maximum_weight, cost_per_kg, weight_step)
        SELECT 
            shipping_method_id AS shipping_id, 
            destination, 
            IFNULL(NULLIF(MIN(weight), MAX(weight)), 0) AS minimum_weight, 
            MAX(weight) AS maximum_weight, 
            (
                SELECT rate/weight*1000 
                FROM shipping_rates AS sr1 
                WHERE 
                    sr.shipping_method_id = sr1.shipping_method_id 
                    AND sr.destination = sr1.destination 
                LIMIT 1
            ) AS cost_per_kg, 
            CASE
                WHEN COUNT(*) > 1 THEN (MAX(weight) - MIN(weight)) / (COUNT(*) - 1)
                ELSE 1
            END AS weight_step 
        FROM 
            shipping_rates AS sr 
            JOIN shipping AS s ON sr.shipping_method_id = s.id 
        WHERE s.discriminator = 'weight_based' 
        GROUP BY shipping_method_id, destination
        """)


def downgrade():
    op.execute("UPDATE shipping SET discriminator = NULL WHERE discriminator = 'weight_based'")
