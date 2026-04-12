#!/usr/bin/env python3
"""CLI for managing ECmgmt admin/customer users.

Usage:
    python manage_users.py create <username> <password> [--admin]
    python manage_users.py delete <username>
    python manage_users.py reset-password <username> <new_password>
"""
import argparse
import sys

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User


def get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def cmd_create(args):
    db = SessionLocal()
    try:
        existing = db.query(User).filter_by(username=args.username).first()
        if existing:
            print(f'ERROR: user "{args.username}" already exists.', file=sys.stderr)
            sys.exit(1)

        role = 'admin' if args.admin else None
        user = User(
            username=args.username,
            password_hash=hash_password(args.password),
            role=role,
        )
        db.add(user)
        db.commit()
        role_label = 'admin' if role else 'customer'
        print(f'Created {role_label} user "{args.username}".')
    finally:
        db.close()


def cmd_delete(args):
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username=args.username).first()
        if not user:
            print(f'ERROR: user "{args.username}" not found.', file=sys.stderr)
            sys.exit(1)

        db.delete(user)
        db.commit()
        print(f'Deleted user "{args.username}".')
    finally:
        db.close()


def cmd_reset_password(args):
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username=args.username).first()
        if not user:
            print(f'ERROR: user "{args.username}" not found.', file=sys.stderr)
            sys.exit(1)

        user.password_hash = hash_password(args.new_password)
        db.commit()
        print(f'Password reset for user "{args.username}".')
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description='Manage ECmgmt users',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest='command', required=True)

    # create
    p_create = sub.add_parser('create', help='Create a new user')
    p_create.add_argument('username')
    p_create.add_argument('password')
    p_create.add_argument('--admin', action='store_true',
                          help='Grant admin role (default: customer)')

    # delete
    p_delete = sub.add_parser('delete', help='Delete a user')
    p_delete.add_argument('username')

    # reset-password
    p_reset = sub.add_parser('reset-password', help="Reset a user's password")
    p_reset.add_argument('username')
    p_reset.add_argument('new_password')

    args = parser.parse_args()

    dispatch = {
        'create': cmd_create,
        'delete': cmd_delete,
        'reset-password': cmd_reset_password,
    }
    dispatch[args.command](args)


if __name__ == '__main__':
    main()
