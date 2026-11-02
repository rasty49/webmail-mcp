# Changelog

## 0.1.1 — 2026-11-02

- Isolate the Python server and approval process from the client’s working directory and Python import environment. Existing users must update saved MCP arguments.
- Validate outgoing text at preparation and review, mark external recipients, and require the end of the message to be visible before Send.
- Prefer extracted HTML for multipart mail, warn about differing alternatives, and label unverified sender data.
- Honor client cancellation before SMTP submission, add local credential recovery and optional draft cleanup, and install hash-locked dependencies in the setup scripts and CI.

## 0.1.0 — 2026-11-02

- Generalized the original RUBMail connector into configurable IMAP/SMTP tools.
- Added separate incoming/outgoing servers, ports, usernames and credentials.
- Required verified TLS or STARTTLS; no plaintext fallback.
- Added native Windows, macOS and Linux Secret Service credential backends.
- Added decoded folder discovery, including German folder names.
- Moved the local send-review window into its own process.
- Added a local sending toggle, account-bound drafts and duplicate-send protection.
- Added optional Sent-folder copies without retrying accepted SMTP delivery.
- Added ChatGPT desktop and Claude Code setup documentation, tests and CI.

The predecessor was reported working with RUBMail on Windows. Generic provider
support is tested with mocks; a compatibility listing is not a certification.
