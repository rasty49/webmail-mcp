# Changelog

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
