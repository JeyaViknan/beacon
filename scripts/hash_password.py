"""Prompt for the admin password (twice) and print its argon2id hash.

    make hash
    echo -n 'password' | python scripts/hash_password.py --stdin   # used by put_secrets.sh

The plaintext never touches disk or shell history; only the hash goes to SSM.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))

from beacon_core.auth import hash_password

MIN_LENGTH = 12


def main() -> int:
    if "--stdin" in sys.argv:
        password = sys.stdin.read().rstrip("\n")
    else:
        password = getpass.getpass("Admin password: ")
        if password != getpass.getpass("Repeat: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1
    if len(password) < MIN_LENGTH:
        print(f"Use at least {MIN_LENGTH} characters.", file=sys.stderr)
        return 1
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
