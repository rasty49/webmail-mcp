"""Real subprocess MCP handshake, discovery, validation and local draft call."""

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def result_data(result):
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(next(block.text for block in result.content if block.type == "text"))


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        # Simulate a writable Claude project that shadows the installed server.
        shadow = Path(tmp) / "webmail_mcp"
        shadow.mkdir()
        (shadow / "__init__.py").write_text("raise RuntimeError('project package executed')")
        (shadow / "__main__.py").write_text("raise SystemExit(0)")
        base = Path(tmp) / "account"
        base.mkdir()
        (base / "account.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "email": "student@example.edu",
                    "imap": {"host": "imap.example.edu", "port": 993, "security": "tls", "username": "student"},
                    "smtp": {"host": "smtp.example.edu", "port": 587, "security": "starttls", "username": "student"},
                    "send_enabled": False,
                }
            )
        )
        params = StdioServerParameters(
            command=sys.executable,
            args=["-I", "-m", "webmail_mcp", "serve"],
            env={**os.environ, "WEBMAIL_MCP_HOME": str(base), "PYTHONPATH": tmp},
            cwd=tmp,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                names = {t.name for t in result.tools}
                assert names == {
                    "list_folders",
                    "search_email",
                    "read_email",
                    "prepare_email",
                    "send_prepared_email",
                    "local_draft_status",
                }, names
                for tool in result.tools:
                    assert "password" not in json.dumps(tool.inputSchema).lower()
                draft = await session.call_tool(
                    "prepare_email", {"to": ["test@example.com"], "subject": "MCP test", "body": "Not sent."}
                )
                assert not draft.isError, draft
                data = result_data(draft)
                assert data["state"] == "prepared", data
                state = await session.call_tool("local_draft_status", {"draft_id": data["draft_id"]})
                assert result_data(state)["state"] == "prepared", state
                invalid = await session.call_tool("read_email", {"uid": 0, "uidvalidity": "1"})
                assert "error" in result_data(invalid), invalid
                print(
                    "PASS: real MCP initialization, six tool schemas, draft creation, status and validation; no network or credentials used."
                )


if __name__ == "__main__":
    asyncio.run(main())
