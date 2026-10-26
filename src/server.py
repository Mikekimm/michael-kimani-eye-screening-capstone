"""Cloud backend for the prototype (standard library HTTP server + SQLite).

Endpoints (JSON, ``Authorization: Bearer <token>``):
    GET  /health                          no auth
    POST /api/screenings                  clinician   upload a screening (idempotent)
    GET  /api/screenings                  specialist, admin   list cases
    GET  /api/screenings/<id>/image       specialist, admin
    POST /api/screenings/<id>/reviews     specialist   append a review
    GET  /api/reviews?since=<id>          clinician, specialist, admin
    GET  /api/stats                       specialist, admin

Design note: the proposal named FastAPI + PostgreSQL. This prototype keeps the same
REST contract on the standard library so it runs with no extra dependencies; the
``ScreeningRepository`` interface is what a PostgreSQL implementation would replace.
"""
import hmac
import json
import re
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional
from urllib.parse import parse_qs, urlparse

from .domain import Role
from .exceptions import RecordNotFoundError, RecordValidationError
from .storage import ScreeningRepository

MAX_BODY_BYTES = 12 * 1024 * 1024  # an 8 MB image grows by about a third in base64

_ID = r"([0-9a-fA-F-]{36})"
_IMAGE_ROUTE = re.compile(rf"^/api/screenings/{_ID}/image$")
_REVIEW_ROUTE = re.compile(rf"^/api/screenings/{_ID}/reviews$")


@dataclass(frozen=True)
class Principal:
    user: str
    role: Role


class TokenAuthenticator:
    """Maps bearer tokens to users and roles. Compares every token in constant time."""

    def __init__(self, tokens: Dict[str, Principal]):
        self._tokens = dict(tokens)

    def authenticate(self, header: Optional[str]) -> Optional[Principal]:
        if not header or not header.startswith("Bearer "):
            return None
        presented = header[len("Bearer "):].strip().encode("utf-8")
        match = None
        for token, principal in self._tokens.items():
            if hmac.compare_digest(presented, token.encode("utf-8")):
                match = principal
        return match


class _HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def build_handler(repository: ScreeningRepository, authenticator: TokenAuthenticator):
    class Handler(BaseHTTPRequestHandler):
        server_version = "RetinalScreeningAPI/0.3"

        def log_message(self, format, *args):  # keep test and demo output quiet
            return

        # ---- plumbing ----
        def _send(self, status: int, body: bytes, content_type: str = "application/json"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, payload) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"))

        def _principal(self, *allowed: Role) -> Principal:
            principal = authenticator.authenticate(self.headers.get("Authorization"))
            if principal is None:
                raise _HttpError(401, "Missing or invalid access token.")
            if principal.role not in allowed:
                raise _HttpError(403, f"Role '{principal.role.value}' may not do this.")
            return principal

        def _read_json(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                raise _HttpError(411, "Content-Length header is required.") from None
            if length < 0 or length > MAX_BODY_BYTES:
                raise _HttpError(413, "Request body is too large.")
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise _HttpError(400, "Body must be valid JSON.") from None
            if not isinstance(body, dict):
                raise _HttpError(400, "Body must be a JSON object.")
            return body

        def _dispatch(self, method: str) -> None:
            try:
                self._route(method)
            except _HttpError as exc:
                self._send_json(exc.status, {"error": str(exc)})
            except RecordValidationError as exc:
                self._send_json(400, {"error": str(exc)})
            except RecordNotFoundError as exc:
                self._send_json(404, {"error": str(exc)})
            except Exception:  # never leak internals to the client
                self._send_json(500, {"error": "Internal server error."})

        do_GET = lambda self: self._dispatch("GET")    # noqa: E731
        do_POST = lambda self: self._dispatch("POST")  # noqa: E731

        # ---- routes ----
        def _route(self, method: str) -> None:
            url = urlparse(self.path)
            path, query = url.path, parse_qs(url.query)

            if method == "GET" and path == "/health":
                return self._send_json(200, {"status": "ok"})

            if method == "POST" and path == "/api/screenings":
                self._principal(Role.CLINICIAN)
                record, created = repository.import_screening(self._read_json())
                return self._send_json(201 if created else 200,
                                       {"id": record.id, "created": created})

            if method == "GET" and path == "/api/screenings":
                self._principal(Role.SPECIALIST, Role.ADMIN)
                flag = lambda name: (query[name][0] == "1") if name in query else None  # noqa: E731
                records = repository.list_screenings(
                    needs_review=flag("needs_review"), unreviewed=flag("unreviewed"))
                return self._send_json(200, {"screenings": [
                    {**r.to_dict(), "quality": json.loads(r.quality_json),
                     "reviews": [v.to_dict() for v in repository.reviews_for(r.id)]}
                    for r in records]})

            image = _IMAGE_ROUTE.match(path)
            if method == "GET" and image:
                self._principal(Role.SPECIALIST, Role.ADMIN)
                return self._send(200, repository.image_bytes(image.group(1)),
                                  "application/octet-stream")

            review = _REVIEW_ROUTE.match(path)
            if method == "POST" and review:
                principal = self._principal(Role.SPECIALIST)
                body = self._read_json()
                saved = repository.add_review(
                    review.group(1), principal.user, str(body.get("decision", "")),
                    str(body.get("notes", "")))
                return self._send_json(201, saved.to_dict())

            if method == "GET" and path == "/api/reviews":
                self._principal(Role.CLINICIAN, Role.SPECIALIST, Role.ADMIN)
                try:
                    since = int(query.get("since", ["0"])[0])
                except ValueError:
                    raise _HttpError(400, "'since' must be an integer.") from None
                return self._send_json(200, {"reviews": [
                    r.to_dict() for r in repository.reviews_since(since)]})

            if method == "GET" and path == "/api/stats":
                self._principal(Role.SPECIALIST, Role.ADMIN)
                return self._send_json(200, repository.stats())

            raise _HttpError(404, "Unknown endpoint.")

    return Handler


def make_server(repository: ScreeningRepository, tokens: Dict[str, Principal],
                host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    """Create (but do not start) the HTTP server. Port 0 picks a free port."""
    return ThreadingHTTPServer((host, port), build_handler(repository, TokenAuthenticator(tokens)))
