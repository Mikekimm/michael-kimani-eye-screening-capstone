"""HTTP clients for the cloud backend (standard library only).

``ApiClient`` owns transport, authentication and error translation. Two subclasses
add the operations each role needs: the clinic app pushes screenings and pulls
reviews; the specialist portal lists cases and submits reviews.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .sync import RemoteClient
from .exceptions import RemoteAuthError, RemoteError, RemoteRejectedError, RemoteUnavailableError


class ApiClient:
    def __init__(self, base_url: str, token: str, timeout: float = 5.0):
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> bytes:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(self._base_url + path, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self._token}")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:  # must precede URLError (its parent)
            message = self._error_message(exc)
            if exc.code in (401, 403):
                raise RemoteAuthError(message) from exc
            if exc.code >= 500:
                raise RemoteUnavailableError(f"Server error {exc.code}: {message}") from exc
            raise RemoteRejectedError(message) from exc
        except (urllib.error.URLError, OSError) as exc:  # no route, refused, timeout, reset
            raise RemoteUnavailableError(f"Cannot reach the server: {exc}") from exc

    @staticmethod
    def _error_message(exc: urllib.error.HTTPError) -> str:
        try:
            return str(json.loads(exc.read().decode("utf-8")).get("error", exc.reason))
        except (ValueError, OSError):
            return str(exc.reason)

    def _json(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        raw = self._request(method, path, body)
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            raise RemoteError("The server sent an unreadable response.") from exc

    def ping(self) -> bool:
        """True when the server answers its health check (used for the online badge)."""
        try:
            self._request("GET", "/health")
            return True
        except RemoteError:
            return False


class ClinicClient(ApiClient, RemoteClient):
    """Operations used by the offline clinic app."""

    def push_screening(self, payload: Dict[str, Any]) -> None:
        self._json("POST", "/api/screenings", payload)

    def fetch_reviews(self, since: int) -> List[Dict[str, Any]]:
        return self._json("GET", f"/api/reviews?since={int(since)}")["reviews"]


class SpecialistClient(ApiClient):
    """Operations used by the specialist review portal."""

    def list_cases(self, unreviewed_only: bool = True) -> List[Dict[str, Any]]:
        query = urllib.parse.urlencode({"needs_review": 1, "unreviewed": int(unreviewed_only)})
        return self._json("GET", f"/api/screenings?{query}")["screenings"]

    def get_image(self, screening_id: str) -> bytes:
        return self._request("GET", f"/api/screenings/{urllib.parse.quote(screening_id)}/image")

    def submit_review(self, screening_id: str, decision: str, notes: str = "") -> Dict[str, Any]:
        path = f"/api/screenings/{urllib.parse.quote(screening_id)}/reviews"
        return self._json("POST", path, {"decision": decision, "notes": notes})

    def stats(self) -> Dict[str, int]:
        return self._json("GET", "/api/stats")
