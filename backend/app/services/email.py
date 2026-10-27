"""Outgoing email behind one small interface, so the rest of the app never knows how mail is sent.

* ``OutboxEmailSender`` (default): writes each message to a text file in ``data/outbox``. Used for local
  development, demos and tests, where no mail server exists.
* ``SmtpEmailSender``: sends through any SMTP provider when ``SMTP_HOST`` is set in the environment.
"""
import smtplib
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class OutboxEmailSender:
    def __init__(self, directory: Path):
        self._directory = Path(directory)

    def send(self, to: str, subject: str, body: str) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        path = self._directory / f"{stamp}-{uuid.uuid4().hex[:8]}.txt"
        path.write_text(f"To: {to}\nSubject: {subject}\n\n{body}\n", encoding="utf-8")


class SmtpEmailSender:
    def __init__(self, host: str, port: int, username: str | None, password: str | None, sender: str,
                 starttls: bool = True, timeout_seconds: float = 15.0):
        self._host, self._port = host, port
        self._username, self._password = username, password
        self._sender, self._starttls, self._timeout = sender, starttls, timeout_seconds

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = self._sender, to, subject
        message.set_content(body)
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            if self._starttls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password or "")
            smtp.send_message(message)
