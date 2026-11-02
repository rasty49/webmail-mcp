from contextlib import contextmanager
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webmail_mcp import server as app
from webmail_mcp.settings import validate_config


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = patch.dict(os.environ, {"WEBMAIL_MCP_HOME": self.temp.name})
        self.base.start()
        self.addCleanup(self.base.stop)
        self.addCleanup(self.temp.cleanup)
        self.account = validate_config(
            {
                "version": 1,
                "email": "student@example.edu",
                "imap": {"host": "imap.example.edu", "port": 993, "security": "tls", "username": "student@example.edu"},
                "smtp": {"host": "smtp.example.edu", "port": 465, "security": "tls", "username": "student@example.edu"},
                "send_enabled": True,
                "sent_folder": "",
            }
        )
        (Path(self.temp.name) / "account.json").write_text(json.dumps(self.account))
        self.creds = patch.object(app, "credentials", return_value=(self.account, "fake-password-never-real"))
        self.creds.start()
        self.addCleanup(self.creds.stop)

    def draft(self):
        result = app.prepare_email(["recipient@example.com"], "Experiment 320", "Hello, can we arrange the experiment?")
        self.assertNotIn("error", result)
        return result["draft_id"]

    def test_header_injection_is_rejected(self):
        for addr in ["a@example.com\r\nBcc: b@example.com", "Display Name <a@example.com>"]:
            self.assertIn("error", app.prepare_email([addr], "Subject", "Body"))
        self.assertIn("error", app.prepare_email(["a@example.com"], "Subject\nInjected", "Body"))

    def test_from_is_fixed_and_drafts_are_local(self):
        result = app.prepare_email(["a@example.com"], "Subject", "Body")
        self.assertEqual(result["preview"]["from"], "student@example.edu")
        self.assertEqual(app.local_draft_status(result["draft_id"])["state"], "prepared")
        with app.database() as db:
            data = db.execute("SELECT data FROM drafts").fetchone()[0]
        self.assertNotIn("fake-password", data)

    def test_reject_bad_inputs_before_network(self):
        self.assertIn("error", app.search_email(subject="x\r\nLOGOUT"))
        self.assertIn("error", app.search_email(limit=31))
        self.assertIn("error", app.search_email(since="2026-02-30"))
        self.assertIn("error", app.read_email(0, "1"))

    def test_quote_escapes_but_rejects_controls(self):
        self.assertEqual(app.quoted('a"b\\c'), '"a\\"b\\\\c"')
        with self.assertRaises(app.MailError):
            app.quoted("INBOX\nLOGOUT")

    def test_html_is_not_executed_and_script_text_removed(self):
        msg = EmailMessage()
        msg.set_content('<p>Hello</p><script>steal()</script><img src="https://example.com/pixel">', subtype="html")
        self.assertEqual(app.message_text(msg.as_bytes()).strip(), "Hello")

    def test_read_only_select_and_uidvalidity(self):
        fake = MagicMock()
        fake.select.return_value = ("OK", [b"1"])
        fake.response.return_value = ("UIDVALIDITY", [b"42"])
        with patch.object(app.imaplib, "IMAP4_SSL", return_value=fake):
            with app.mailbox("INBOX", "42") as (_, validity):
                self.assertEqual(validity, "42")
            fake.select.assert_called_once_with('"INBOX"', readonly=True)
            with self.assertRaises(app.MailError):
                with app.mailbox("INBOX", "41"):
                    pass

    def test_search_uses_peek_and_paginates(self):
        fake = MagicMock()
        fake.uid.side_effect = [("OK", [b"7 9 10"]), ("OK", [(b"header", b"Subject: Test\r\n\r\n")])]

        @contextmanager
        def box(*args):
            yield fake, "42"

        with patch.object(app, "mailbox", box):
            result = app.search_email(limit=1, offset=1)
        self.assertEqual(result["messages"][0]["uid"], 9)
        self.assertEqual(result["next_offset"], 2)
        self.assertIn("BODY.PEEK", fake.uid.call_args_list[1].args[2])

    def test_read_uses_peek_and_plain_text(self):
        fake = MagicMock()
        msg = EmailMessage()
        msg["Subject"] = "Hello"
        msg.set_content("Test body")
        raw = msg.as_bytes()
        fake.uid.side_effect = [("OK", [f"1 (RFC822.SIZE {len(raw)})".encode()]), ("OK", [(b"data", raw)])]

        @contextmanager
        def box(*args):
            yield fake, "42"

        with patch.object(app, "mailbox", box):
            result = app.read_email(7, "42")
        self.assertEqual(result["body"].strip(), "Test body")
        self.assertEqual(fake.uid.call_args_list[1].args, ("FETCH", "7", "(BODY.PEEK[])"))

    def test_large_message_not_downloaded(self):
        fake = MagicMock()
        fake.uid.return_value = ("OK", [b"1 (RFC822.SIZE 9999999)"])

        @contextmanager
        def box(*args):
            yield fake, "42"

        with patch.object(app, "mailbox", box):
            self.assertIn("error", app.read_email(7, "42"))
        self.assertEqual(fake.uid.call_count, 1)

    def test_cancel_never_connects_to_smtp(self):
        identity = self.draft()
        with patch.object(app, "approve_locally", return_value=False), patch.object(app.smtplib, "SMTP_SSL") as smtp:
            self.assertFalse(app.send_prepared_email(identity)["sent"])
            smtp.assert_not_called()

    def test_missing_gui_never_connects(self):
        identity = self.draft()
        with (
            patch.object(app, "approve_locally", side_effect=app.MailError("No GUI")),
            patch.object(app.smtplib, "SMTP_SSL") as smtp,
        ):
            self.assertIn("error", app.send_prepared_email(identity))
            smtp.assert_not_called()
        self.assertEqual(app.local_draft_status(identity)["state"], "prepared")

    def test_send_and_no_duplicate(self):
        identity = self.draft()
        smtp = MagicMock()
        smtp.send_message.return_value = {}
        with (
            patch.object(app, "approve_locally", return_value=True) as approval,
            patch.object(app.smtplib, "SMTP_SSL", return_value=smtp),
        ):
            self.assertEqual(app.send_prepared_email(identity)["state"], "sent")
            self.assertEqual(app.send_prepared_email(identity)["state"], "sent")
            self.assertEqual(smtp.send_message.call_count, 1)
            self.assertEqual(approval.call_count, 1)
        sent = smtp.send_message.call_args
        self.assertEqual(sent.kwargs["from_addr"], "student@example.edu")
        self.assertEqual(str(sent.args[0]["From"]), "student@example.edu")

    def test_disconnect_on_quit_does_not_change_accepted_state(self):
        identity = self.draft()
        smtp = MagicMock()
        smtp.send_message.return_value = {}
        smtp.quit.side_effect = smtplib.SMTPServerDisconnected("bye")
        with (
            patch.object(app, "approve_locally", return_value=True),
            patch.object(app.smtplib, "SMTP_SSL", return_value=smtp),
        ):
            self.assertEqual(app.send_prepared_email(identity)["state"], "sent")

    def test_uncertain_send_cannot_be_retried_and_diagnostics_are_hidden(self):
        identity = self.draft()
        smtp = MagicMock()
        smtp.send_message.side_effect = smtplib.SMTPServerDisconnected("sensitive server detail fake-password")
        with (
            patch.object(app, "approve_locally", return_value=True),
            patch.object(app.smtplib, "SMTP_SSL", return_value=smtp),
        ):
            result = app.send_prepared_email(identity)
            self.assertEqual(result["state"], "delivery_uncertain")
            self.assertNotIn("fake-password", json.dumps(result))
            app.send_prepared_email(identity)
            self.assertEqual(smtp.send_message.call_count, 1)

    def test_partial_send_is_blocked_from_repeat(self):
        identity = self.draft()
        smtp = MagicMock()
        smtp.send_message.return_value = {"recipient@example.com": (550, b"no")}
        with (
            patch.object(app, "approve_locally", return_value=True),
            patch.object(app.smtplib, "SMTP_SSL", return_value=smtp),
        ):
            self.assertEqual(app.send_prepared_email(identity)["state"], "partially_sent")
            app.send_prepared_email(identity)
            self.assertEqual(smtp.send_message.call_count, 1)

    def test_concurrent_send_cannot_send_twice(self):
        identity = self.draft()
        entered, release = threading.Event(), threading.Event()

        def approve(draft):
            entered.set()
            release.wait(5)
            return True

        smtp = MagicMock()
        smtp.send_message.return_value = {}
        with (
            patch.object(app, "approve_locally", side_effect=approve),
            patch.object(app.smtplib, "SMTP_SSL", return_value=smtp),
        ):
            worker = threading.Thread(target=app.send_prepared_email, args=(identity,))
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(app.send_prepared_email(identity)["state"], "reviewing")
            finally:
                release.set()
                worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(smtp.send_message.call_count, 1)

    def test_changed_sender_requires_new_draft(self):
        identity = self.draft()
        with (
            patch.object(app, "config", return_value={**self.account, "email": "other@example.edu"}),
            patch.object(app, "approve_locally") as approve,
        ):
            self.assertIn("error", app.send_prepared_email(identity))
            approve.assert_not_called()

    def test_exception_details_are_redacted(self):
        @app.safe_tool
        def broken():
            raise RuntimeError("password=should-never-appear")

        self.assertNotIn("should-never-appear", json.dumps(broken()))


if __name__ == "__main__":
    unittest.main()
