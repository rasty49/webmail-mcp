# Security and privacy

Webmail MCP grants an AI client access to a mailbox. Its narrow MCP interface
does not expose configuration editing, credential retrieval, arbitrary files,
attachment execution, or a public network listener.

## Boundaries

- Native keyring backends are selected explicitly. Plaintext fallback is refused.
- Login uses verified TLS or STARTTLS before credentials are sent.
- Reading uses read-only IMAP selection and BODY.PEEK.
- Mail content and headers are untrusted input. Tool descriptions instruct clients
  to treat them as data, not instructions. A client can still misinterpret mail.
- Sending must be enabled in local settings. Every send requires a separate local
  review window with the exact immutable prepared content. This is not protection
  against malware or an agent with unrestricted access to the same desktop.
- SMTP state is persisted before an optional Sent-folder append. Uncertain,
  in-progress, partial, and completed sends are never automatically retried.
- Unexpected exceptions returned to the model are sanitized; SMTP authentication
  replies, raw tracebacks and password values are not returned by tools.

Email returned by a tool is processed by the chosen AI service. It is not kept
entirely offline. Local draft content is not separately encrypted. Other programs
running as the same OS user may access the draft database or stored credentials.
Use the access and data controls appropriate to your mailbox and institution.

## Report a vulnerability

Use GitHub's private vulnerability reporting for this repository if the owner has
enabled it. Otherwise open a public issue containing only a high-level request
for a private reporting channel. Do not post exploit details that expose users,
credentials, real messages, screenshots of inboxes, or account configuration.

Version 0.1.x is the initial supported line. No independent security audit has
been performed, and native OS keyring/GUI behavior needs local testing.
