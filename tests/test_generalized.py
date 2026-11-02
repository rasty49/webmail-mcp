from copy import deepcopy
import json
import os
from pathlib import Path
import smtplib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from webmail_mcp import server as app
from webmail_mcp import settings


def example_account():
    return settings.validate_config(
        {
            "version": 1,
            "email": "student@uni.example.edu",
            "imap": {
                "host": "imap.uni.example.edu",
                "port": 993,
                "security": "tls",
                "username": "student@uni.example.edu",
            },
            "smtp": {
                "host": "smtp.uni.example.edu",
                "port": 587,
                "security": "starttls",
                "username": "campus\\student",
            },
            "send_enabled": True,
            "sent_folder": "",
        }
    )


class SettingsTests(unittest.TestCase):
    def test_non_rub_domain_and_distinct_usernames(self):
        c = example_account()
        self.assertEqual(c["email"], "student@uni.example.edu")
        self.assertEqual(c["smtp"]["username"], "campus\\student")

    def test_reject_plaintext_or_malformed_endpoints(self):
        for patch_values in (
            {"security": "none"},
            {"host": "https://mail.example.edu"},
            {"port": True},
            {"port": 0},
            {"username": "x\r\n"},
        ):
            c = example_account()
            c["imap"].update(patch_values)
            with self.assertRaises(settings.MailError):
                settings.validate_config(c)

    def test_sending_defaults_to_disabled(self):
        c = example_account()
        del c["send_enabled"]
        self.assertFalse(settings.validate_config(c)["send_enabled"])

    def test_keyring_identity_separates_providers_and_protocols(self):
        c = example_account()
        changed = deepcopy(c)
        changed["imap"]["host"] = "other.example.edu"
        self.assertNotEqual(settings.credential_key(c, "imap"), settings.credential_key(changed, "imap"))
        self.assertNotEqual(settings.credential_key(c, "imap"), settings.credential_key(c, "smtp"))

    def test_config_file_is_nonsecret_and_has_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"WEBMAIL_MCP_HOME": directory}):
            settings.write_config(example_account())
            result = settings.config()
            self.assertEqual(result["imap"]["host"], "imap.uni.example.edu")
            content = (Path(directory) / "account.json").read_text()
            self.assertNotIn("password", content)
            if os.name != "nt":
                self.assertEqual((Path(directory) / "account.json").stat().st_mode & 0o777, 0o600)

    def test_no_relative_data_directory(self):
        with patch.dict(os.environ, {"WEBMAIL_MCP_HOME": "relative/path"}):
            with self.assertRaises(settings.MailError):
                settings.data_dir()

    def test_export_keeps_virtualenv_interpreter_and_has_no_credentials(self):
        base = Path(tempfile.gettempdir())
        interpreter = str(base / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        mail_home = str(base / "mail-data")
        with (
            patch.object(sys, "executable", interpreter),
            patch.dict(os.environ, {"WEBMAIL_MCP_HOME": mail_home}),
        ):
            value = settings.client_config()
        item = value["mcpServers"]["webmail"]
        self.assertEqual(item["command"], interpreter)
        self.assertEqual(item["env"]["WEBMAIL_MCP_HOME"], mail_home)
        self.assertEqual(item["args"], ["-I", "-m", "webmail_mcp", "serve"])
        self.assertNotIn("username", json.dumps(value))
        self.assertNotIn("password", json.dumps(value))

    def test_credentials_load_from_protocol_specific_native_store(self):
        ring = MagicMock()
        ring.get_password.return_value = "synthetic-password"
        c = example_account()
        with (
            patch.object(settings, "config", return_value=c),
            patch.object(settings, "secure_keyring", return_value=ring),
        ):
            self.assertEqual(settings.credentials("smtp")[1], "synthetic-password")
        ring.get_password.assert_called_once_with(settings.SERVICE, settings.credential_key(c, "smtp"))

    def test_native_store_errors_are_redacted(self):
        with (
            patch.object(settings, "config", return_value=example_account()),
            patch.object(settings, "secure_keyring", side_effect=RuntimeError("sensitive diagnostic")),
        ):
            with self.assertRaises(settings.MailError) as error:
                settings.credentials()
        self.assertNotIn("sensitive diagnostic", str(error.exception))


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.c = example_account()
        self.mock_creds = patch.object(
            app, "credentials", side_effect=lambda protocol="imap": (self.c, "synthetic-password")
        )
        self.mock_creds.start()
        self.addCleanup(self.mock_creds.stop)

    def test_imap_starttls_happens_before_login_and_failure_never_logs_in(self):
        self.c["imap"].update(security="starttls", port=143)
        client = MagicMock()
        with patch.object(app.imaplib, "IMAP4", return_value=client):
            app.open_imap()
        self.assertEqual([c[0] for c in client.method_calls], ["starttls", "login"])
        context = client.starttls.call_args.kwargs["ssl_context"]
        self.assertTrue(context.check_hostname)
        client.reset_mock()
        client.starttls.side_effect = RuntimeError("TLS failure")
        with patch.object(app.imaplib, "IMAP4", return_value=client), self.assertRaises(RuntimeError):
            app.open_imap()
        client.login.assert_not_called()

    def test_smtp_starttls_and_distinct_username(self):
        client = MagicMock()
        with patch.object(app.smtplib, "SMTP", return_value=client) as smtp:
            app.open_smtp()
        self.assertEqual([c[0] for c in client.method_calls], ["ehlo", "starttls", "ehlo", "login"])
        smtp.assert_called_once_with("smtp.uni.example.edu", 587, timeout=30)
        client.login.assert_called_once_with("campus\\student", "synthetic-password")
        self.assertTrue(client.starttls.call_args.kwargs["context"].check_hostname)

    def test_smtp_starttls_failure_never_logs_in(self):
        client = MagicMock()
        client.starttls.side_effect = RuntimeError("TLS failure")
        with patch.object(app.smtplib, "SMTP", return_value=client), self.assertRaises(RuntimeError):
            app.open_smtp()
        client.login.assert_not_called()

    def test_account_change_before_connection_is_rejected(self):
        expected = deepcopy(self.c)
        expected["imap"]["host"] = "old.example.edu"
        with patch.object(app.imaplib, "IMAP4_SSL") as imap, patch.object(app.smtplib, "SMTP") as smtp:
            with self.assertRaises(app.MailError):
                app.open_imap(expected=expected)
            with self.assertRaises(app.MailError):
                app.open_smtp(expected=expected)
        imap.assert_not_called()
        smtp.assert_not_called()

    def test_modified_utf7_handles_german_and_ampersand(self):
        for folder in ("INBOX", "Entwürfe", "Gesendet & Archiv", "日本語", "A & B"):
            self.assertEqual(app.decode_folder(app.encode_folder(folder)), folder)

    def test_folder_listing_parses_quoted_and_literal_names(self):
        fake = MagicMock()
        encoded = app.encode_folder("Entwürfe").encode()
        fake.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"', (b'(\\Drafts) "/" {12}', encoded), b'(\\Noselect) "/" "Parent"'],
        )
        with patch.object(app, "open_imap", return_value=fake):
            result = app.list_folders()
        self.assertEqual([f["name"] for f in result["folders"]], ["INBOX", "Entwürfe", "Parent"])
        self.assertFalse(result["folders"][2]["selectable"])
        fake.logout.assert_called_once()

    def test_local_review_has_no_cli_approval_shortcut(self):
        with patch.object(app.subprocess, "run", return_value=MagicMock(returncode=2)) as run:
            self.assertFalse(app.approve_locally({"body": "synthetic"}))
        self.assertEqual(run.call_args.args[0], [sys.executable, "-I", "-m", "webmail_mcp.approval"])
        self.assertEqual(json.loads(run.call_args.kwargs["input"])["body"], "synthetic")

    def test_review_timeout_and_no_gui_refuse_send(self):
        with patch.object(app.subprocess, "run", side_effect=subprocess.TimeoutExpired("review", 190)):
            self.assertFalse(app.approve_locally({}))
        with patch.object(app.subprocess, "run", return_value=MagicMock(returncode=1)):
            with self.assertRaises(app.MailError):
                app.approve_locally({})


class SendStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"WEBMAIL_MCP_HOME": self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.c = example_account()
        settings.write_config(self.c)

    def draft(self):
        result = app.prepare_email(["recipient@example.com"], "Test", "Synthetic message")
        return result["draft_id"]

    def test_disabled_sending_never_opens_review_or_smtp(self):
        self.c["send_enabled"] = False
        settings.write_config(self.c)
        with patch.object(app, "approve_locally") as approve, patch.object(app, "open_smtp") as smtp:
            self.assertIn("error", app.send_prepared_email(self.draft()))
        approve.assert_not_called()
        smtp.assert_not_called()

    def test_endpoint_change_invalidates_draft(self):
        identity = self.draft()
        self.c["smtp"]["host"] = "different.example.edu"
        settings.write_config(self.c)
        with patch.object(app, "approve_locally") as approve:
            self.assertIn("error", app.send_prepared_email(identity))
        approve.assert_not_called()

    def test_send_toggle_rechecked_after_review(self):
        def change_config(draft):
            self.c["send_enabled"] = False
            settings.write_config(self.c)
            return True

        with patch.object(app, "approve_locally", side_effect=change_config), patch.object(app, "open_smtp") as smtp:
            self.assertEqual(app.send_prepared_email(self.draft())["state"], "not_sent")
        smtp.assert_not_called()

    def test_sent_copy_failure_never_causes_resend(self):
        identity = self.draft()
        smtp = MagicMock()
        smtp.send_message.return_value = {}
        with (
            patch.object(app, "approve_locally", return_value=True),
            patch.object(app, "open_smtp", return_value=smtp),
            patch.object(app, "append_sent_copy", side_effect=OSError("server error")),
        ):
            result = app.send_prepared_email(identity)
            self.assertEqual(result["state"], "sent")
            self.assertEqual(result["sent_folder_copy"], "failed")
            app.send_prepared_email(identity)
        self.assertEqual(smtp.send_message.call_count, 1)

    def test_sent_append_uses_configured_folder_and_seen_flag(self):
        self.c["sent_folder"] = "Gesendet & Archiv"
        client = MagicMock()
        client.append.return_value = ("OK", [b"saved"])
        with patch.object(app, "open_imap", return_value=client):
            msg = app.message_for(
                {
                    "from": self.c["email"],
                    "to": ["a@example.com"],
                    "cc": [],
                    "subject": "Test",
                    "message_id": "<test@example.com>",
                    "body": "Synthetic",
                }
            )
            self.assertEqual(app.append_sent_copy(self.c, msg), "saved")
        self.assertEqual(client.append.call_args.args[0], '"Gesendet &- Archiv"')
        self.assertEqual(client.append.call_args.args[1], "\\Seen")

    def test_auth_failure_reports_not_sent(self):
        with (
            patch.object(app, "approve_locally", return_value=True),
            patch.object(app, "open_smtp", side_effect=smtplib.SMTPAuthenticationError(535, b"redacted")),
        ):
            result = app.send_prepared_email(self.draft())
        self.assertEqual(result["state"], "not_sent")
        self.assertNotIn("redacted", json.dumps(result))

    def test_rejected_message_reports_not_sent_and_does_not_repeat(self):
        identity = self.draft()
        smtp = MagicMock()
        smtp.send_message.side_effect = smtplib.SMTPDataError(550, b"rejected")
        with patch.object(app, "approve_locally", return_value=True), patch.object(app, "open_smtp", return_value=smtp):
            self.assertEqual(app.send_prepared_email(identity)["state"], "not_sent")
            app.send_prepared_email(identity)
        self.assertEqual(smtp.send_message.call_count, 1)


if __name__ == "__main__":
    unittest.main()
