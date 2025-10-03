#!/bin/sh
# Entrypoint for netkit-api
# Default: MCP stdio server (primary use case)
# Override: --http for HTTP API mode

set -e

# If args provided, check for mode flag
if [ $# -gt 0 ]; then
  case "$1" in
    --http)
      echo "Starting netkit-api HTTP API server on port 8090..." >&2
      shift
      exec python /app/api/api.py "$@"
      ;;
    --stdin|--mcp)
      echo "Starting netkit-api MCP stdio server..." >&2
      shift
      exec python /app/mcp/server.py "$@"
      ;;
    -h|--help)
      cat >&2 <<EOF
netkit-api - Network diagnostics and security toolkit

Usage:
  netkit-api [MODE] [OPTIONS]

Modes:
  (default)    Start MCP stdio server (for AI assistants)
  --stdin      Start MCP stdio server (explicit)
  --mcp        Start MCP stdio server (alias)
  --http       Start HTTP API server on port 8090

Examples:
  # MCP mode (default - for Claude, Gemini, etc.)
  docker run -i flengure/netkit-api:latest

  # HTTP API mode
  docker run -p 8090:8090 flengure/netkit-api:latest --http

  # Direct command override
  docker run flengure/netkit-api:latest python /app/api/api.py

Environment Variables:
  SCAN_WHITELIST     Allowed scan targets (comma-separated)
  SCAN_BLACKLIST     Blocked scan targets (comma-separated)
  ALLOW_PRIVATE_IPS  Allow RFC1918 private IPs (default: false)
  API_KEYS           API keys for HTTP mode (comma-separated)
  JWT_SECRET         JWT secret for HTTP mode
EOF
      exit 0
      ;;
    python|sh|bash|/*)
      # Direct command execution
      exec "$@"
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Run with --help for usage information" >&2
      exit 1
      ;;
  esac
else
  # No args = default to MCP stdio mode
  echo "Starting netkit-api MCP stdio server (default)..." >&2
  exec python /app/mcp/server.py
fi
