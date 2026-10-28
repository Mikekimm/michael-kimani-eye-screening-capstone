"""Local mode (no SMTP_HOST): emails are saved to the outbox folder and printed to the backend console."""
from app.services.email import OutboxEmailSender


def test_local_email_is_saved_and_printed_to_the_console(tmp_path, capsys):
    OutboxEmailSender(tmp_path).send("nurse@example.org", "Reset your password", "Open http://localhost/reset?token=abc")
    saved = list(tmp_path.glob("*.txt"))
    assert len(saved) == 1 and "token=abc" in saved[0].read_text(encoding="utf-8")
    printed = capsys.readouterr().out
    assert "LOCAL EMAIL (not sent; no SMTP_HOST set)" in printed and "http://localhost/reset?token=abc" in printed


def test_console_echo_can_be_turned_off(tmp_path, capsys):
    OutboxEmailSender(tmp_path, echo=False).send("a@example.org", "s", "b")
    assert capsys.readouterr().out == ""
