"""Create a local .env with a random JWT secret and random demo-account passwords.

Usage (from the repo root):  .venv\\Scripts\\python scripts\\init_env.py [--demo-passwords]
--demo-passwords uses the fixed demo-only passwords documented in README section 7 instead of random ones,
so a clean install matches the walkthrough. Never use them on a hosted deployment.
Refuses to overwrite an existing .env. The generated file is git-ignored; never commit it.
"""
import argparse
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Demo-only, synthetic data, local use. Documented in README section 7.
DEMO_PASSWORDS = {"SEED_ADMIN_PASSWORD": "DemoAdmin2026!", "SEED_SPECIALIST_PASSWORD": "DemoSpecialist2026!",
                  "SEED_HEALTH_WORKER_PASSWORD": "DemoNurse2026!"}
TEMPLATE = ROOT / ".env.example"
TARGET = ROOT / ".env"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo-passwords", action="store_true", help="use the documented demo-only passwords")
    args = parser.parse_args()
    if TARGET.exists():
        print(f"{TARGET} already exists; delete it first if you want new secrets.")
        return 1
    values = {
        "JWT_SECRET": secrets.token_hex(32),
        "SEED_ADMIN_PASSWORD": secrets.token_urlsafe(12),
        "SEED_SPECIALIST_PASSWORD": secrets.token_urlsafe(12),
        "SEED_HEALTH_WORKER_PASSWORD": secrets.token_urlsafe(12),
    }
    if args.demo_passwords:
        values.update(DEMO_PASSWORDS)
    lines = []
    for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0]
        lines.append(f"{key}={values[key]}" if key in values else line)
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {TARGET}. Demo accounts (synthetic, local only):")
    for line in lines:
        if line.startswith("SEED_") and ("EMAIL" in line or "PASSWORD" in line):
            print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
