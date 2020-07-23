"""user model update

Revision ID: 8d9fdc6e236f
Revises: 6f580c7626c4
Create Date: 2020-07-23 22:32:38.899233

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '8d9fdc6e236f'
down_revision = '6f580c7626c4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users', 'email',
               existing_type=mysql.VARCHAR(collation='utf8_unicode_ci', length=80),
               nullable=True)
    op.alter_column('users', 'password_hash',
               existing_type=mysql.VARCHAR(collation='utf8_unicode_ci', length=200),
               nullable=True)
    op.drop_index('email', table_name='users')
    op.drop_column('users', 'fname')
    op.drop_column('users', 'lname')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('lname', mysql.VARCHAR(collation='utf8_unicode_ci', length=80), nullable=True))
    op.add_column('users', sa.Column('fname', mysql.VARCHAR(collation='utf8_unicode_ci', length=80), nullable=True))
    op.create_index('email', 'users', ['email'], unique=True)
    op.alter_column('users', 'password_hash',
               existing_type=mysql.VARCHAR(collation='utf8_unicode_ci', length=200),
               nullable=False)
    op.alter_column('users', 'email',
               existing_type=mysql.VARCHAR(collation='utf8_unicode_ci', length=80),
               nullable=False)
    # ### end Alembic commands ###
