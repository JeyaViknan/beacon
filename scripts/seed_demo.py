"""Create the "Beacon Demo Target" product through the API (HANDOVER §13).

    python scripts/seed_demo.py --app https://dxxxx.cloudfront.net \\
        --target "$(terraform -chdir=infra/main output -raw demo_target_url)"

Prompts for the admin password. Safe to re-run: it does nothing if the product already exists.
"""

import argparse
import getpass
import sys

import httpx

DEMO_NAME = "Beacon Demo Target"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, help="CloudFront URL of Beacon")
    parser.add_argument("--target", required=True, help="Function URL of the demo target")
    args = parser.parse_args()
    base = args.app.rstrip("/")

    with httpx.Client(base_url=base, timeout=20) as client:
        password = getpass.getpass("Admin password: ")
        login = client.post("/api/auth/login", json={"password": password})
        if login.status_code != 200:
            print(f"Login failed: {login.status_code} {login.text}", file=sys.stderr)
            return 1
        client.headers["Authorization"] = f"Bearer {login.json()['token']}"

        existing = client.get("/api/products").json()
        if any(p["name"] == DEMO_NAME for p in existing):
            print(f"'{DEMO_NAME}' already exists; nothing to do.")
            return 0

        created = client.post(
            "/api/products",
            json={
                "name": DEMO_NAME,
                "kind": "personal",
                "note": "Used for live demos",
                "checkUrl": args.target,
                "openAfter": 1,
                "resolveAfter": 1,
                "sortOrder": 999,
                "stack": ["AWS Lambda", "SSM"],
            },
        )
        if created.status_code != 201:
            print(f"Create failed: {created.status_code} {created.text}", file=sys.stderr)
            return 1
        print(f"Created '{DEMO_NAME}' ({created.json()['id']}). First check within ~1 minute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
