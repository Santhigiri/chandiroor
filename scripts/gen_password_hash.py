"""Generate a bcrypt hash for a new admin/user password.

Usage:
    python scripts/gen_password_hash.py <username> <new-password>

Prints the UPDATE statement to run against the deployed Postgres/Neon DB
(via psql or any SQL client pointed at DATABASE_URL). Uses the same hashing
as core.security.hash_password, so the result is compatible with login.
"""

import sys

import bcrypt


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <username> <new-password>", file=sys.stderr)
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    print(hashed)
    print()
    print("Run this against the target database:")
    print()
    print(f"UPDATE \"user\" SET hashed_password = '{hashed}' WHERE username = '{username}';")


if __name__ == "__main__":
    main()
