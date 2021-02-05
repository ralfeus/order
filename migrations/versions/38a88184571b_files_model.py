"""Files model

Revision ID: 38a88184571b
Revises: 0bdc8953cd67
Create Date: 2021-02-03 20:12:44.752619

"""
from alembic import op
import logging
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '38a88184571b'
down_revision = '0bdc8953cd67'
branch_labels = None
depends_on = None


def upgrade():
    logger = logging.getLogger("Alembic")
    logger.setLevel(logging.DEBUG)
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('files',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('when_created', sa.DateTime(), nullable=True),
    sa.Column('when_changed', sa.DateTime(), nullable=True),
    sa.Column('file_name', sa.String(length=128), nullable=True),
    sa.Column('path', sa.String(length=128), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_files_when_created'), 'files', ['when_created'], unique=False)
    op.create_table('payments_files',
    sa.Column('payment_id', sa.Integer(), nullable=True),
    sa.Column('file_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['file_id'], ['files.id'], ),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], )
    )
    conn = op.get_bind()
    res = conn.execute("SELECT id, evidence_image FROM payments WHERE evidence_image IS NOT NULL")
    results = res.fetchall()
    try:
        for evidence_image in results:
            res = conn.execute(
                "INSERT INTO files (when_created, file_name, path) VALUES (NOW(), '{0}', '{0}')"
                .format(evidence_image[1])
            )

            conn.execute("INSERT INTO payments_files VALUES ({0}, {1})"
                .format(evidence_image[0], res.inserted_primary_key()))
        op.drop_column('payments', 'evidence_image')
    finally:
        op.execute('DROP table payments_files')
        op.execute('DROP table files')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('payments', sa.Column('evidence_image', mysql.VARCHAR(collation='utf8_unicode_ci', length=256), nullable=True))
    op.drop_table('payments_files')
    op.drop_index(op.f('ix_files_when_created'), table_name='files')
    op.drop_table('files')
    # ### end Alembic commands ###
