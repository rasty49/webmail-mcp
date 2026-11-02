"""Local configuration and native OS credential storage. No network operations."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys

SERVICE = "Webmail-MCP"


class MailError(Exception):
    """A credential-free error safe to return to an MCP client."""


def data_dir():
    override = os.environ.get("WEBMAIL_MCP_HOME")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise MailError("WEBMAIL_MCP_HOME must be an absolute path.")
        return path
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / SERVICE
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / SERVICE
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / SERVICE


def private_dir():
    path = data_dir()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        path.chmod(0o700)
    return path


def addresses(values):
    if not isinstance(values, list) or len(values) > 20:
        raise MailError("Supply up to 20 plain email addresses per recipient field.")
    for value in values:
        if (
            not isinstance(value, str)
            or len(value) > 254
            or not re.fullmatch(
                r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}", value
            )
        ):
            raise MailError("Use plain email addresses only, without display names or line breaks.")
    return values


def clean_text(value, label, limit=254):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise MailError(f"Invalid {label}.")
    return value


def endpoint(value, label):
    if not isinstance(value, dict):
        raise MailError(f"Missing {label} server configuration.")
    host = clean_text(value.get("host"), f"{label} hostname")
    # User-owned configuration only, never provided as tool input. No URL or paths.
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
        raise MailError(f"{label} host must be a hostname or IPv4 address, without a scheme or port.")
    port = value.get("port")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise MailError(f"Invalid {label} port.")
    security = value.get("security")
    if security not in {"tls", "starttls"}:
        raise MailError(f"{label} security must be tls or starttls. Plaintext connections are unsupported.")
    return {
        "host": host.lower(),
        "port": port,
        "security": security,
        "username": clean_text(value.get("username"), f"{label} username"),
    }


def validate_config(value):
    if not isinstance(value, dict) or value.get("version") != 1:
        raise MailError("Unsupported config version. Run webmail-mcp setup.")
    email = addresses([value.get("email")])[0]
    send_enabled = value.get("send_enabled", False)
    if not isinstance(send_enabled, bool):
        raise MailError("send_enabled must be true or false.")
    sent = value.get("sent_folder", "")
    if sent:
        clean_text(sent, "Sent folder", 500)
    if not isinstance(sent, str):
        raise MailError("sent_folder must be a string.")
    return {
        "version": 1,
        "email": email,
        "imap": endpoint(value.get("imap"), "IMAP"),
        "smtp": endpoint(value.get("smtp"), "SMTP"),
        "send_enabled": send_enabled,
        "sent_folder": sent,
    }


def config():
    try:
        raw = json.loads((data_dir() / "account.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise MailError("No valid local account configuration. Run webmail-mcp setup locally.") from None
    return validate_config(raw)


def write_config(value):
    value = validate_config(value)
    path = private_dir() / "account.json"
    temp = path.with_suffix(".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(value, indent=2) + "\n")
    os.replace(temp, path)


def secure_keyring():
    import keyring

    # Select only the native encrypted backend. Fail instead of falling back to files.
    if sys.platform == "win32":
        from keyring.backends.Windows import WinVaultKeyring

        backend = WinVaultKeyring()
    elif sys.platform == "darwin":
        from keyring.backends.macOS import Keyring

        backend = Keyring()
    elif sys.platform.startswith("linux"):
        from keyring.backends.SecretService import Keyring

        backend = Keyring()
    else:
        raise MailError("No supported native credential store for this OS.")
    try:
        if backend.priority <= 0:
            raise ValueError()
    except Exception:
        raise MailError("Unlock your native OS credential store first. Plaintext fallback is disabled.") from None
    keyring.set_keyring(backend)
    return keyring


def credential_key(c, protocol):
    # Same username at different providers must never share a credential entry.
    identity = json.dumps({"email": c["email"], "protocol": protocol, **c[protocol]}, sort_keys=True)
    return protocol + ":" + hashlib.sha256(identity.encode()).hexdigest()


def account_fingerprint(c):
    """Bind outgoing drafts to the account and endpoints reviewed at preparation."""
    identity = {key: c[key] for key in ("email", "imap", "smtp")}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def credentials(protocol="imap"):
    if protocol not in {"imap", "smtp"}:
        raise MailError("Invalid credential type.")
    c = config()
    try:
        password = secure_keyring().get_password(SERVICE, credential_key(c, protocol))
    except MailError:
        raise
    except Exception:
        raise MailError("Cannot access the OS credential store. Unlock it and check local setup.") from None
    if not password:
        raise MailError("No saved credential for this endpoint. Run webmail-mcp setup locally again.")
    return c, password


def save_credentials(c, imap_password, smtp_password):
    ring = secure_keyring()
    ring.set_password(SERVICE, credential_key(c, "imap"), imap_password)
    ring.set_password(SERVICE, credential_key(c, "smtp"), smtp_password)
    write_config(c)


def forget_account():
    c = config()
    ring = secure_keyring()
    import keyring.errors

    for protocol in ("imap", "smtp"):
        try:
            ring.delete_password(SERVICE, credential_key(c, protocol))
        except keyring.errors.PasswordDeleteError:
            pass
    (data_dir() / "account.json").unlink()


def client_config():
    """Generate launch settings only; no mailbox login or password is exported."""
    # Do not resolve a venv Python symlink to the system interpreter: that would
    # lose access to the installed package and its dependencies.
    result = {"command": str(Path(sys.executable).absolute()), "args": ["-m", "webmail_mcp", "serve"]}
    if os.environ.get("WEBMAIL_MCP_HOME"):
        result["env"] = {"WEBMAIL_MCP_HOME": str(data_dir())}
    return {"mcpServers": {"webmail": result}}
