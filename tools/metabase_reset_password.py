#!/usr/bin/env python3
"""Reset a Metabase user's password directly in the database."""

import argparse
import sys

try:
    import bcrypt
except ImportError:
    print("Error: 'bcrypt' package is required. Install with: pip install bcrypt", file=sys.stderr)
    sys.exit(1)

try:
    import pymysql
except ImportError:
    print("Error: 'pymysql' package is required. Install with: pip install pymysql", file=sys.stderr)
    sys.exit(1)


def reset_password(email, new_password, db_host, db_name, db_user, db_password, db_port=3306):
    conn = pymysql.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            # Get the user and their password salt
            cur.execute(
                "SELECT u.id, ai.credentials "
                "FROM core_user u "
                "JOIN auth_identity ai ON ai.user_id = u.id AND ai.provider = 'password' "
                "WHERE u.email = %s",
                (email,),
            )
            row = cur.fetchone()
            if not row:
                print(f"Error: user '{email}' not found or has no password identity.", file=sys.stderr)
                sys.exit(1)

            user_id, credentials_json = row

            import json
            credentials = json.loads(credentials_json)
            salt = credentials.get("password_salt", "default")

            # Hash: bcrypt(salt + password)
            new_hash = bcrypt.hashpw(
                (salt + new_password).encode("utf-8"),
                bcrypt.gensalt(rounds=10, prefix=b"2a"),
            ).decode("utf-8")

            # Update auth_identity credentials
            credentials["password_hash"] = new_hash
            cur.execute(
                "UPDATE auth_identity SET credentials = %s "
                "WHERE user_id = %s AND provider = 'password'",
                (json.dumps(credentials), user_id),
            )

            # Keep core_user.password in sync
            cur.execute(
                "UPDATE core_user SET password = %s WHERE id = %s",
                (new_hash, user_id),
            )

            conn.commit()
            print(f"Password for '{email}' reset successfully.")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Reset a Metabase user password via direct DB update.")
    parser.add_argument("email", help="Metabase user email")
    parser.add_argument("new_password", help="New password")
    parser.add_argument("db_host", help="MySQL host")
    parser.add_argument("db_name", help="MySQL database name")
    parser.add_argument("db_user", help="MySQL user")
    parser.add_argument("db_password", help="MySQL password")
    parser.add_argument("--db-port", type=int, default=3306, help="MySQL port (default: 3306)")
    args = parser.parse_args()

    reset_password(
        email=args.email,
        new_password=args.new_password,
        db_host=args.db_host,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=args.db_password,
        db_port=args.db_port,
    )


if __name__ == "__main__":
    main()
