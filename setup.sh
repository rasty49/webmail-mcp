#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m webmail_mcp setup
.venv/bin/python -m webmail_mcp check
printf '\nLaunch settings for your MCP client:\n'
.venv/bin/python -m webmail_mcp client-config
