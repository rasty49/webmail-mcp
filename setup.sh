#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
python3 -m venv .venv
.venv/bin/python -I -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.venv/bin/python -I -m pip install --no-build-isolation --no-deps .
.venv/bin/python -I -m webmail_mcp setup
.venv/bin/python -I -m webmail_mcp check
printf '\nLaunch settings for your MCP client:\n'
.venv/bin/python -I -m webmail_mcp client-config
