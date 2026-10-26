"""Start the cloud backend for local demos and testing.

Usage:
    python scripts/run_server.py                 # random tokens, printed once
    python scripts/run_server.py --demo-tokens   # fixed, INSECURE tokens for the video
"""
import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.ml.config import DATA_DIR  # noqa: E402
from app.ml.domain import Role  # noqa: E402
from app.ml.server import Principal, make_server  # noqa: E402
from app.ml.storage import ScreeningRepository  # noqa: E402

DEMO_TOKENS = {
    "demo-clinician-token": Principal("clinic-nurse", Role.CLINICIAN),
    "demo-specialist-token": Principal("dr-specialist", Role.SPECIALIST),
    "demo-admin-token": Principal("admin-user", Role.ADMIN),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", default=str(DATA_DIR / "server"))
    parser.add_argument("--demo-tokens", action="store_true",
                        help="use fixed insecure tokens (demos only)")
    args = parser.parse_args()

    if args.demo_tokens:
        tokens = DEMO_TOKENS
        print("WARNING: demo tokens are public. Never use them with real data.")
    else:
        tokens = {secrets.token_urlsafe(16): Principal(name, role) for name, role in (
            ("clinic-nurse", Role.CLINICIAN), ("dr-specialist", Role.SPECIALIST),
            ("admin-user", Role.ADMIN))}
    data_dir = Path(args.data_dir)
    repository = ScreeningRepository(data_dir / "server.db", data_dir / "images")
    server = make_server(repository, tokens, args.host, args.port)
    print(f"Backend listening on http://{args.host}:{server.server_address[1]}")
    for token, principal in tokens.items():
        print(f"  {principal.role.value:<10} token: {token}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
