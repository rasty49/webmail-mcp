# Webmail MCP

**Your university inbox, in ChatGPT desktop or Claude Code.**

A local MCP server that connects compatible email accounts through **IMAP and
SMTP**. Search messages, read your inbox, prepare replies, and send from your own
email address—with a local review window before sending.

Built for people whose university or self-hosted email isn't covered by the
usual Gmail and Microsoft integrations. It grew out of a working RUBMail
connector at Ruhr University Bochum, and now accepts your provider's own server
settings.

**No forwarding. No browser-session access. No public mail proxy.** Your email
password is stored in your native OS credential store. Mail content returned by
the tools is shared with the AI service you use.

> **Compatibility:** This is an IMAP/SMTP connector, not a scraper for every
> webmail website. Your provider must allow password or app-password IMAP/SMTP
> authentication. Browser-only SSO, OAuth-only mailboxes, and Exchange/EWS-only
> accounts are not supported. Check your university's mail-client instructions.

## What it does

| Tool | Purpose |
| --- | --- |
| `list_folders` | Discover folders, including names with German characters |
| `search_email` | Filter by sender, subject, text, date or unread state |
| `read_email` | Read text without marking the message as read |
| `prepare_email` | Create a local draft and return its complete preview |
| `send_prepared_email` | Send after local configuration allows it and you approve the review window |
| `local_draft_status` | Check a draft's preparation or delivery state |

- Separate IMAP/SMTP hosts, ports, usernames and passwords.
- Verified TLS or STARTTLS; no plaintext fallback.
- Windows Credential Manager, macOS Keychain, or Linux Secret Service.
- Sending is disabled by default. Enabling it still requires local review.
- Optional Sent-folder copies; a failed copy never triggers another send.
- No OpenAI or Anthropic API key needed by this connector. Your MCP client has
  its own account/subscription requirements.

## Quick start

### Upgrade an existing installation to 0.1.1

Stop the MCP server. Download the updated source from this repository, then run the installation commands below from that trusted folder. On Windows, `setup.cmd` installs into its adjacent virtual environment. If you keep the same account settings, you can also update an existing installation without re-entering your passwords:

```powershell
.\.venv\Scripts\python.exe -I -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.\.venv\Scripts\python.exe -I -m pip install --no-build-isolation --no-deps .
.\.venv\Scripts\python.exe -I -m webmail_mcp client-config
```

**Replace the saved launch arguments in every MCP client and restart it.** Updating the package alone leaves old client entries vulnerable to a project directory shadowing the server. The first argument must be `-I`. Install outside folders the AI can modify and use a dedicated virtual environment. An editable install is for development only.

### Windows

1. Download or clone this repository and extract it to a private folder.
2. Install [Python 3.11+](https://www.python.org/downloads/) with the launcher and
   Tcl/Tk components.
3. Run **`setup.cmd`** yourself. It installs the package, prompts for your mail
   settings locally, checks login without sending a message, and prints client
   launch settings.

Your university may call your username a LoginID, Benutzername, or full email
address. Use its published settings rather than assuming it equals your address.

### macOS / Linux desktop

```sh
python3 -m venv .venv
.venv/bin/python -I -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.venv/bin/python -I -m pip install --no-build-isolation --no-deps .
.venv/bin/python -I -m webmail_mcp setup
.venv/bin/python -I -m webmail_mcp check
.venv/bin/python -I -m webmail_mcp client-config
```

You can also run `sh setup.sh` from this repository. Linux needs an unlocked
Secret Service keyring and Python's Tk support, often provided by your system's
`python3-tk` package. macOS needs a Python build with working Tcl/Tk. Sending needs
an unlocked graphical desktop; headless/remote/WSL GUI approval is not tested.

**Enter credentials only in the local setup prompt—not in your chat or MCP
configuration.** Use a provider-specific app password if your provider requires
one. The wizard refuses noninteractive stdin to prevent accidental secret entry
through an AI tool call.

## Connect ChatGPT desktop

Use a version of ChatGPT desktop with local MCP support.

Run the following using the Python in your installation:

```powershell
.\.venv\Scripts\python.exe -I -m webmail_mcp client-config
```

On macOS/Linux, use `.venv/bin/python` instead. The command prints a standard
`mcpServers` JSON block with your **actual Python path**, without your mailbox
credentials.

In **Settings → MCP servers → Add server**:

| Field | Value |
| --- | --- |
| Name | `webmail` |
| Type | `STDIO` |
| Command | The generated `command` path, without surrounding quotes |
| Arguments | Four separate arguments: `-I`, `-m`, `webmail_mcp`, `serve` |
| Environment | Empty, unless you deliberately set `WEBMAIL_MCP_HOME` |

Restart the server and check `/mcp`. If your client supports a tool timeout, use
240 seconds to allow local review. For Codex-compatible configuration:

```toml
[mcp_servers.webmail]
command = 'C:\path\to\webmail-mcp\.venv\Scripts\python.exe'
args = ["-I", "-m", "webmail_mcp", "serve"]
tool_timeout_sec = 240
```

Replace the path with the generated one; preserve other client settings.

**Scope:** This local STDIO server does not appear automatically in ordinary
ChatGPT web chats. It needs a local MCP-capable desktop/host. It isn't a hosted
ChatGPT connector. See [OpenAI's current MCP setup guide](https://learn.chatgpt.com/docs/extend/mcp).

## Connect Claude Code

Use the absolute Python path printed by `client-config`:

```sh
claude mcp add --transport stdio --scope user webmail -- "/absolute/path/to/.venv/bin/python" -I -m webmail_mcp serve
```

Windows PowerShell example:

```powershell
claude mcp add --transport stdio --scope user webmail -- "C:\path\to\webmail-mcp\.venv\Scripts\python.exe" -I -m webmail_mcp serve
```

Then run `claude mcp get webmail` or open `/mcp` in Claude Code. The local review
window must be able to open on the machine where the MCP server runs. Keep any
configured timeout at least 240 seconds. See [Anthropic's MCP guide](https://code.claude.com/docs/en/mcp).

Other local MCP clients can use the same `client-config` JSON block. Client
compatibility beyond the documented setup and protocol tests is not certified.

## Example requests

> Use webmail to show my five newest inbox messages. Do not send anything.

> Find emails from the examination office since 2026-10-01.

> Read the message about my lab appointment and prepare a short reply for review.

> Send the prepared draft. Show me the local review window.

The sender is fixed to your locally configured email address. You review the
exact From, To, Cc, Subject, and body in a local window and click **Send this
email**. The window lists body length and line count and marks recipients outside the sender’s exact domain. Send becomes available when the bottom of the preview is visible. Check the whole message and every address. Cancel, close, or wait three minutes to decline. Outgoing subject and body reject control and Unicode format characters, including invisible directional overrides. Body text accepts newlines and tabs.

## Provider settings

Find your university's instructions for Thunderbird, Outlook classic, Apple Mail,
or another IMAP mail client. Copy the IMAP/SMTP values into the setup wizard.
There is no automatic discovery or guess based on the webmail URL.

| Setting | Example values—not universal defaults |
| --- | --- |
| IMAP | Host from your provider; port 993 with `tls`, or 143 with `starttls` |
| SMTP | Host from your provider; port 465 with `tls`, or 587 with `starttls` |
| Username | Your provider's LoginID or full email address |
| Password | Account password or provider-issued app password |
| Sent folder | Exact name from `list_folders`, or blank for a local record only |

`tls` means encryption from connection start (often called SSL/TLS in mail
instructions). `starttls` upgrades the connection before any login. Certificate
verification stays enabled.

### Ruhr University Bochum (RUBMail)

The predecessor was reported working on Windows with RUBMail. Its [official
settings](https://mail.rub.de/mail/anleitungen) are:

| Field | Value |
| --- | --- |
| IMAP host / port / security | `mail.ruhr-uni-bochum.de` / `993` / `tls` |
| SMTP host / port / security | `mail.ruhr-uni-bochum.de` / `465` / `tls` |
| Username | RUB LoginID |

RUBMail and RUBExchange are different services. No affiliation with or endorsement
by RUB, other universities, OpenAI, or Anthropic is implied. Other providers are
configurable but have not yet been verified against live accounts. Contributions
should include a provider's official configuration link and no personal data.

## Privacy and local storage

The connector runs on your computer, opens no listening port, and contacts only
the mail servers you configure during normal operation. It has no telemetry.
Installing dependencies contacts the Python package index.

| Data | Where it goes |
| --- | --- |
| Passwords | Native OS credential store; not tool inputs or outputs |
| Mail settings | `account.json` in the private application data directory |
| Prepared messages and delivery states | Local `drafts.sqlite3` database |
| Search results, read messages, draft previews | Your MCP client and the AI service processing the conversation |

Data directory defaults:

- Windows: `%LOCALAPPDATA%\Webmail-MCP`
- macOS: `~/Library/Application Support/Webmail-MCP`
- Linux: `$XDG_DATA_HOME/Webmail-MCP`, or `~/.local/share/Webmail-MCP`

`WEBMAIL_MCP_HOME` can select another absolute private directory, primarily for
isolated testing. Never choose a repository or shared/cloud-sync folder for real
mail data. If you set it, also pass it to the MCP server's environment.

Local drafts are not separately encrypted. OS credential storage is not a
security boundary against all programs running as the same user. A client with
broad shell/computer access may be able to access the same credential store.
Do not describe this as an air gap or a guarantee that other local tools cannot
retrieve credentials. See [SECURITY.md](SECURITY.md).

For mailbox reading, use a dedicated chat or client profile with shell, web fetch, outbound connectors, and computer-control tools disabled. A malicious message can ask the client to send mailbox data through any other tool it can access. The local window covers only SMTP delivery through Webmail MCP.

## Limits and delivery behavior

- One configured account per application data directory. No OAuth flow, EWS,
  Graph API, browser login, or account provisioning.
- Reads do not mark messages as read. HTML is reduced to text without fetching
  remote images or opening links. Attachments are not exposed as tools.
- For multipart mail, the reader prefers text extracted from HTML and warns when the plain alternative differs after whitespace normalization. It skips common inline hiding styles and hidden elements. Stylesheets, inherited styles and differences between mail clients can still affect what a person sees.
- Sender-provided headers and body fields are enclosed by matching untrusted-email markers. The returned Authentication-Results fields are unverified header text. A sender can forge them. Confirm sensitive requests independently.
- Full messages above 5 MiB are refused; body output is capped at 40,000 characters.
- Outgoing mail is new plain-text email with To/Cc. Attachments, Bcc, rich text,
  automatic signatures and reply-threading headers are not implemented.
- Prepared drafts are local, not drafts in your university's webmail.
- Sent-folder copies are optional and require an exact existing folder name.
  If appending fails after delivery, the send remains successful: **do not resend**.
- SMTP acceptance isn't proof the recipient read or received the email. A network
  loss during delivery can leave state `delivery_uncertain`; repeats are blocked.
  Check before preparing a duplicate. Partial delivery is also blocked from repeat.
- If the client times out, **cancel any still-open window** and check `local_draft_status` before preparing another draft. When the client sends a cancellation during review, a late click cannot start delivery. A silent client timeout is invisible to the server, and SMTP already in progress may complete.
- Closing a client during review or delivery may leave a draft `reviewing` or
  `sending`. These states are deliberately blocked from automatic retries.
- Non-ASCII search terms require server support for UTF-8 IMAP SEARCH. Basic
  ASCII/date searches avoid requesting an unnecessary charset.

## Remove access

Disable/remove `webmail` in your MCP client, then run:

```sh
webmail-mcp forget
```

Use the executable in your virtual environment if it isn't on PATH. This removes
saved credentials for the current configuration and its account file. Draft
history remains by default. To delete local message bodies and delivery history too, stop every Webmail MCP server and run `webmail-mcp forget --all`. This removes the local database and its sidecar files. Copies in backups, chat history and the mailbox have separate retention.
New setups save a private index of opaque credential IDs so cleanup can recover from a damaged account file. Run setup once after upgrading to create this index for an existing account. For older installations with a damaged account file and no index, remove the Webmail-MCP entries in your OS credential manager, then remove the damaged account file. Before changing
to a different account or server, forget the old account to avoid orphaned secrets.

The older RUB-specific connector is independent. Generalizing this repository
does not migrate or delete its saved credentials. Disable the old `rub-mail`
server before using the replacement; run the old `forget-login.cmd` if retiring it.

## Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python tests/mcp_smoke.py
```

Tests use synthetic accounts and simulated IMAP/SMTP servers. The smoke test
starts a real STDIO MCP subprocess and verifies tool discovery and local draft
operations. They do not need real credentials or send real emails. CI is configured
for Windows, macOS and Linux on Python 3.11–3.13; it doesn't exercise native GUI
or keyring integration. This version is an early release, not a security-audited
mail gateway. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). Created by Rasty49.
