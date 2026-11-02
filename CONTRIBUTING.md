# Contributing

Useful contributions include verified university settings, better IMAP server
compatibility, accessible local review, and tests for delivery edge cases.

1. Create a virtual environment and install with `python -m pip install -e .`.
2. Run `python -m unittest discover -s tests -v` and `python tests/mcp_smoke.py`.
3. Keep test fixtures synthetic, using reserved example domains.
4. Describe the user-visible change and the validation in your pull request.

Do not commit account files, passwords, local MCP configuration, native keyring
exports, draft databases, email files, or private screenshots. Those files are
excluded by `.gitignore`, which is a convenience rather than a secret scanner.

For a provider compatibility report, include its official IMAP/SMTP instructions,
OS, Python version, client, and which actions you actually tested. Never claim
that all accounts at a university work from one report. OAuth support, account
migration, and headless sending need separate designs; do not bypass TLS or
the local review step as a compatibility fix.
