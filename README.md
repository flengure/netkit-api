# netkit-api

**Remote operations toolkit**

FastAPI-based HTTP/MCP API for network diagnostics, scanning, and security auditing.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Docker Pulls](https://img.shields.io/docker/pulls/flengure/netkit-api)](https://hub.docker.com/r/flengure/netkit-api)

## ⚠️ Security Warning

**Do not expose the HTTP API publicly without:**
1. **Strong authentication** (OIDC/JWT preferred, API keys minimum)
2. **IP whitelist configuration** (SCAN_WHITELIST)
3. **Aggressive rate limiting** (RATE_LIMIT_PER_IP)
4. **Target restrictions** (SCAN_BLACKLIST to prevent abuse)

### Two-Tier Deployment Architecture

This project supports a **two-tier security model** for production deployments:

**Private Instance (Full Capabilities):**
- Runs as **root** with `CAP_NET_RAW` + `CAP_NET_ADMIN`
- Full functionality: nmap SYN scans (`-sS`), traceroute, mtr, masscan
- Bound to **localhost only** (`[::1]:8090` or `127.0.0.1:8090`)
- For internal/trusted automation only
- Never expose directly to the internet

**Public Instance (Safe Mode):**
- Runs as **non-root** (`user: 1000:1000`) with **no capabilities**
- Limited to safe tools: nmap TCP scans (`-sT`), dig, curl, whois, SSL scanners
- Suitable for controlled public access with strong authentication
- Lower risk if compromised (cannot create raw sockets)
- Reduced resource limits

Both instances should be behind a **reverse proxy** (Caddy/nginx) with TLS termination.

**Example docker-compose.yml:**
```yaml
services:
  # Internal - full capabilities
  netkit-api:
    image: flengure/netkit-api:latest
    command: --http
    ports:
      - "[::1]:8090:8090"  # localhost only
    cap_add:
      - NET_RAW
      - NET_ADMIN
    env_file: .env

  # Public - restricted
  netkit-api-public:
    image: flengure/netkit-api:latest
    command: --http
    user: "1000:1000"  # non-root
    ports:
      - "[::1]:8091:8090"  # localhost only
    cap_drop:
      - ALL  # no capabilities
    env_file: .env_public
```

**Why root + capabilities is risky:**
- Command injection → arbitrary code execution as root
- `CAP_NET_RAW` → can launch network attacks from your IP
- Container escape → potential host compromise

See [SECURITY.md](SECURITY.md) for detailed security information.

## Installation

```bash
# Docker (recommended)
docker pull flengure/netkit-api:latest

# Or from source
git clone https://github.com/flengure/netkit-api.git
cd netkit-api
docker build -t netkit-api .
```

## Features

- 🔐 **SSH Execution** - Non-interactive command execution via OpenSSH
- 🌐 **DNS Tools** - dig, host, whois lookups
- 🔍 **Network Scanning** - nmap, masscan port scanning
- 🔒 **Security Auditing** - SSL/TLS analysis, vulnerability scanning
- 🌍 **Web Inspection** - curl HTTP/HTTPS inspection
- 📡 **Network Diagnostics** - traceroute, mtr, ping
- 🚀 **Async Execution** - Background jobs for long-running scans
- 🔑 **Authentication** - OIDC, JWT tokens, or API keys
- 🛡️ **Security** - Rate limiting, whitelist/blacklist, input validation
- 🔌 **MCP Integration** - Model Context Protocol for Claude AI

## Quick Start

### MCP Server (Default - for AI Assistants)
The container defaults to MCP stdio server mode:

```bash
# Basic MCP mode (default)
docker run -i flengure/netkit-api:latest

# With full capabilities
docker run -i \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  flengure/netkit-api:latest
```

### HTTP API (Network Access)
Use `--http` flag for HTTP API server mode:

```bash
# No authentication (local/trusted networks only)
docker run -d \
  -p 8090:8090 \
  flengure/netkit-api:latest --http
```

## Authentication

netkit-api supports **three authentication methods** for HTTP API mode. MCP stdio mode (default) does not require authentication.

### No Authentication (Default)

If no auth method is configured, the API accepts all requests:

```bash
docker run -d -p 8090:8090 flengure/netkit-api:latest --http
```

⚠️ **Use only for**:
- Local development
- Trusted internal networks
- Behind a separate authentication layer (reverse proxy, VPN)

### Method 1: API Keys (Simple)

Best for: **Service-to-service communication, simple deployments**

```bash
# Generate secure API keys
API_KEY=$(openssl rand -base64 32)

# Run with API keys
docker run -d \
  -p 8090:8090 \
  -e API_KEYS=$API_KEY \
  flengure/netkit-api:latest --http
```

**Usage:**
```bash
# Option A: X-API-Key header
curl -H "X-API-Key: $API_KEY" http://localhost:8090/exec \
  -d '{"command":"dig google.com +short"}'

# Option B: Authorization header
curl -H "Authorization: ApiKey $API_KEY" http://localhost:8090/exec \
  -d '{"command":"dig google.com +short"}'
```

**Multiple keys:**
```bash
-e API_KEYS=key1,key2,key3
```

### Method 2: JWT Tokens (Shared Secret)

Best for: **Simple token-based auth, custom integrations**

```bash
# Generate secure JWT secret
JWT_SECRET=$(openssl rand -hex 32)

# Run with JWT
docker run -d \
  -p 8090:8090 \
  -e JWT_SECRET=$JWT_SECRET \
  flengure/netkit-api:latest --http
```

**Generate tokens** (using PyJWT):
```python
import jwt
import datetime

payload = {
    'sub': 'user@example.com',
    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
}
token = jwt.encode(payload, 'your-jwt-secret', algorithm='HS256')
```

**Usage:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8090/exec \
  -d '{"command":"dig google.com +short"}'
```

### Method 3: OIDC/OAuth2 (Recommended for Production)

Best for: **Production deployments, enterprise environments, centralized auth**

**Supported providers:**
- ✅ Authentik (recommended open-source)
- ✅ Auth0
- ✅ Keycloak
- ✅ Azure AD / Entra ID
- ✅ Google Identity
- ✅ Okta
- ✅ Any OIDC-compliant provider

```bash
docker run -d \
  -p 8090:8090 \
  -e OIDC_ENABLED=true \
  -e OIDC_ISSUER=https://auth.example.com/application/o/netkit/ \
  -e OIDC_AUDIENCE=netkit-api \
  -e OIDC_REQUIRED_SCOPES=netkit.exec \
  flengure/netkit-api:latest --http
```

**Get token from provider:**
```bash
# Example: Authentik (client_credentials flow)
ACCESS_TOKEN=$(curl -sS -X POST \
  -d "grant_type=client_credentials" \
  -d "client_id=<YOUR_CLIENT_ID>" \
  -d "client_secret=<YOUR_CLIENT_SECRET>" \
  -d "scope=netkit.exec" \
  https://auth.example.com/application/o/token/ | jq -r .access_token)
```

**Usage:**
```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8090/exec \
  -d '{"command":"dig google.com +short"}'
```

**Why OIDC?**
- ✅ No shared secrets (uses public key cryptography)
- ✅ Automatic key rotation support
- ✅ Centralized authentication across services
- ✅ Fine-grained access control with scopes
- ✅ Industry-standard protocol

**Complete setup guide:** [docs/OIDC_SETUP.md](docs/OIDC_SETUP.md)

### Multiple Authentication Methods

You can enable multiple methods simultaneously:

```bash
docker run -d \
  -p 8090:8090 \
  -e OIDC_ENABLED=true \
  -e OIDC_ISSUER=https://auth.example.com/ \
  -e API_KEYS=legacy-key-for-old-clients \
  -e JWT_SECRET=backup-secret \
  flengure/netkit-api:latest --http
```

**Priority order:**
1. OIDC Bearer token (if OIDC enabled)
2. JWT Bearer token (if JWT_SECRET set)
3. API Key (if API_KEYS set)

The API will try each method in order until one succeeds.

### Hardened Production Deployment

For maximum security, run with read-only filesystem:

```bash
docker run -d \
  --read-only \
  --tmpfs /tmp:noexec,nosuid,size=100M \
  --tmpfs /var/run:noexec,nosuid,size=10M \
  -p 8090:8090 \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  --cap-drop=ALL \
  -e API_KEYS=your-api-key \
  flengure/netkit-api:latest --http
```

Or use the provided `docker-compose.yml`:

```bash
docker-compose up -d
```

**Benefits:**
- Immutable filesystem prevents persistence if compromised
- tmpfs provides volatile writable space (lost on restart)
- Minimal capabilities (only NET_RAW/NET_ADMIN)
- No new files can be written to container filesystem

Check available features:
```bash
curl http://localhost:8090/healthz
```

## Available Tools

| Tool | Description | Requires CAP_NET_RAW |
|------|-------------|---------------------|
| ssh | Execute commands on remote hosts | No |
| nmap | Network port scanner | Yes (for SYN scans, OS detection) |
| masscan | Fast port scanner | Yes |
| dig | DNS lookup | No |
| host | Simple DNS lookup | No |
| whois | Domain registry info | No |
| curl | HTTP/HTTPS client | No |
| traceroute | Network path tracing | Yes |
| mtr | Network diagnostics | Yes |
| ping | ICMP ping | No |
| nc | Netcat TCP/UDP tool | No |
| sslscan | SSL/TLS cipher testing | No |
| testssl.sh | Comprehensive SSL/TLS audit | No |
| nikto | Web vulnerability scanner | No |
| whatweb | Web technology identifier | No |

## Usage Examples

### Execute Tool (Sync)

The API supports **three flexible formats** for command execution:

**Format 1: Full command string** (simplest)
```bash
curl -X POST http://localhost:8090/exec \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"command": "dig google.com +short"}'
```

**Format 2: Tool + args array** (explicit)
```bash
curl -X POST http://localhost:8090/exec \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "dig",
    "args": ["google.com", "+short"]
  }'
```

**Format 3: Tool + command string** (backward compatible)
```bash
curl -X POST http://localhost:8090/exec \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "dig",
    "command": "google.com +short"
  }'
```

**More examples:**
```bash
# Nmap scan (full command)
curl -X POST http://localhost:8090/exec \
  -H "X-API-Key: your-api-key" \
  -d '{"command": "nmap -sT -p 80,443 scanme.nmap.org"}'

# Whois lookup (tool + args)
curl -X POST http://localhost:8090/exec \
  -H "X-API-Key: your-api-key" \
  -d '{"tool": "whois", "args": ["google.com"]}'

# SSH command (requires SSH keys)
curl -X POST http://localhost:8090/exec \
  -H "X-API-Key: your-api-key" \
  -d '{
    "tool": "ssh",
    "host": "example.com",
    "user": "ubuntu",
    "command": "uptime"
  }'
```

### Execute Tool (Async)

```bash
# Start async scan (full command format)
JOB_ID=$(curl -X POST http://localhost:8090/exec \
  -H "X-API-Key: your-api-key" \
  -d '{
    "command": "nmap -sT -p 1-1000 scanme.nmap.org",
    "async": true
  }' | jq -r '.job_id')

# Check job status
curl -H "X-API-Key: your-api-key" \
  http://localhost:8090/jobs/$JOB_ID

# List all jobs
curl -H "X-API-Key: your-api-key" \
  http://localhost:8090/jobs
```

### List Available Tools

```bash
curl http://localhost:8090/tools
```

### Get Tool Info

```bash
curl http://localhost:8090/tools/nmap
```

## API Reference

Full API documentation available at `/docs` (Swagger UI) when running in HTTP mode.

### Tool Execution

#### `POST /exec`
Execute any tool synchronously or asynchronously.

**Request formats** (all equivalent):
```json
// Format 1: Full command string
{"command": "dig google.com +short"}

// Format 2: Tool + args array
{"tool": "dig", "args": ["google.com", "+short"]}

// Format 3: Tool + command string
{"tool": "dig", "command": "google.com +short"}
```

**Request parameters:**
- `command` (string, optional): Full command with arguments
- `tool` (string, optional): Tool name (required if using `args`)
- `args` (array, optional): Arguments as array
- `timeout` (integer, optional): Execution timeout in seconds
- `async` (boolean, optional): Execute asynchronously (default: false)
- `host` (string, optional): SSH hostname (ssh tool only)
- `user` (string, optional): SSH username (ssh tool only)

**Response (sync):**
```json
{
  "stdout": "142.250.185.46\n",
  "stderr": "",
  "exit_code": 0,
  "duration_seconds": 0.234,
  "tool": "dig",
  "command": "dig google.com +short"
}
```

**Response (async):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "tool": "nmap"
}
```

**Error codes:**
- `400` - Invalid payload, unknown tool, or invalid arguments
- `401` - Authentication failed (missing or invalid credentials)
- `403` - Authorization failed (valid token but insufficient scopes)
- `429` - Rate limit exceeded
- `503` - Tool unavailable or missing required capabilities
- `504` - Execution timeout

#### `GET /tools`
List all available tools with capability requirements.

**Response:**
```json
{
  "tools": {
    "nmap": {
      "name": "nmap",
      "description": "Network port scanner",
      "available": true,
      "requires_capability": true
    },
    "dig": {
      "name": "dig",
      "description": "DNS lookup",
      "available": true,
      "requires_capability": false
    }
  }
}
```

#### `GET /tools/{tool_name}`
Get detailed information about a specific tool.

**Response:**
```json
{
  "name": "nmap",
  "description": "Network port scanner",
  "available": true,
  "requires_capability": true,
  "max_timeout": 300,
  "min_timeout": 1,
  "default_timeout": 30
}
```

### Async Jobs

#### `GET /jobs/{job_id}`
Get status and result of an async job.

**Response (running):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "tool": "nmap",
  "created_at": "2025-10-04T12:34:56Z"
}
```

**Response (completed):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "tool": "nmap",
  "stdout": "...",
  "stderr": "",
  "exit_code": 0,
  "duration_seconds": 45.2,
  "created_at": "2025-10-04T12:34:56Z",
  "completed_at": "2025-10-04T12:35:41Z"
}
```

**Error codes:**
- `404` - Job not found

#### `GET /jobs`
List all jobs, optionally filtered by status.

**Query parameters:**
- `status` (string, optional): Filter by status (`pending`, `running`, `completed`, `failed`)
- `limit` (integer, optional): Maximum number of results (default: 100)

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "tool": "nmap"
    }
  ],
  "count": 1
}
```

#### `DELETE /jobs/{job_id}`
Cancel and delete a job.

**Response:**
```json
{
  "message": "Job deleted",
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### System

#### `GET /healthz`
Health check endpoint with capability reporting.

**Response:**
```json
{
  "ok": true,
  "version": "2.0.0",
  "service": "netkit-api",
  "capabilities": {
    "has_net_raw": true,
    "has_net_admin": true,
    "is_root": true,
    "limited_tools": []
  }
}
```

#### `GET /stats`
API statistics and metrics.

**Response:**
```json
{
  "rate_limiter": {
    "global_requests": 42,
    "ip_requests": {"127.0.0.1": 10},
    "key_requests": {"key_abc": 5}
  },
  "job_manager": {
    "total_jobs": 15,
    "pending": 2,
    "running": 3,
    "completed": 10
  },
  "tools": {
    "total": 15,
    "available": 15
  }
}
```

## Configuration

### Environment Variables

**Authentication** (optional - HTTP API mode only):
```bash
# Method 1: API Keys (simple)
API_KEYS=key1,key2,key3

# Method 2: JWT (shared secret)
JWT_SECRET=your-secret-key-here

# Method 3: OIDC (recommended for production)
OIDC_ENABLED=true
OIDC_ISSUER=https://auth.example.com/
OIDC_AUDIENCE=netkit-api                  # Optional: validate audience claim
OIDC_REQUIRED_SCOPES=netkit.exec,admin    # Optional: require specific scopes
OIDC_JWKS_URI=https://auth.example.com/jwks  # Optional: auto-discovered if not set

# If no auth method is configured, API accepts all requests (use only on trusted networks)
# You can enable multiple methods - they will be tried in priority order: OIDC → JWT → API Key
```

**Rate Limiting**:
```bash
RATE_LIMIT_GLOBAL=100      # requests/min globally (all users combined)
RATE_LIMIT_PER_IP=20       # requests/min per source IP address
RATE_LIMIT_PER_KEY=50      # requests/min per API key
```

Rate limits are enforced on all `/exec` and `/jobs` endpoints. When exceeded, the API returns `429 Too Many Requests`.

**Recommended settings:**

| Deployment | GLOBAL | PER_IP | PER_KEY | Use Case |
|------------|--------|--------|---------|----------|
| **Development** | 1000 | 100 | 100 | Local testing |
| **Internal** | 500 | 50 | 100 | Trusted internal users |
| **Public (restricted)** | 100 | 10 | 20 | Public with strong auth |
| **Public (open)** | 50 | 5 | N/A | Public without auth (not recommended) |

**OIDC Scope-Based Restrictions (optional):**

Use `OIDC_REQUIRED_SCOPES` to limit access by tool category:
```bash
# Require at least one of these scopes
OIDC_REQUIRED_SCOPES=netkit.exec.web,netkit.exec.scan,netkit.exec.dns,netkit.exec.all

# Tool categories:
# - netkit.exec.web: curl, whatweb, nikto, testssl.sh
# - netkit.exec.scan: nmap, masscan
# - netkit.exec.dns: dig, host, whois
# - netkit.exec.network: traceroute, mtr, ping, nc
# - netkit.exec.ssh: ssh (remote execution)
# - netkit.exec.all: All tools
```

Configure these scopes in your OIDC provider to control per-user access.

**Target Validation**:
```bash
SCAN_WHITELIST=10.0.0.0/8,192.168.0.0/16,*.example.com
SCAN_BLACKLIST=10.0.0.1,192.168.1.1,*.internal.corp
ALLOW_PRIVATE_IPS=false
```

**Jobs**:
```bash
MAX_CONCURRENT_JOBS=100
JOB_CLEANUP_INTERVAL=3600   # seconds
```

**SSH** (for mounted .ssh directory):
```bash
SSH_DIR=/root/.ssh
```

**Logging**:
```bash
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR
```

All logs are written to stdout (12-factor app pattern) for easy container log aggregation.

**Log levels:**
- **ERROR**: Only errors and failures
- **WARNING**: Warnings + errors (default)
- **INFO**: Request logs + warnings + errors
- **DEBUG**: Full command output + execution details + all above

**Secret Redaction:**

The API automatically redacts sensitive information from logs:
- API keys are masked (shows first 8 chars + `...`)
- Command-line passwords are redacted (flags like `-p PASSWORD`, `--password=SECRET`)
- Environment variables containing `SECRET`, `KEY`, or `PASSWORD` are never logged
- JWT tokens are not logged

**Example logs:**
```
2025-10-04 12:34:56 - INFO - Valid API key authentication (key: 12345678...)
2025-10-04 12:34:57 - INFO - Tool execution request: dig from 192.168.1.100
2025-10-04 12:34:57 - INFO - Executing: dig google.com +short (timeout: 30s)
```

### Docker Compose

```yaml
version: '3.8'

services:
  netkit-api:
    image: flengure/netkit-api:latest
    ports:
      - "8090:8090"
    cap_add:
      - NET_RAW
      - NET_ADMIN
    environment:
      - JWT_SECRET=${JWT_SECRET}
      - API_KEYS=${API_KEYS}
      - SCAN_WHITELIST=${SCAN_WHITELIST:-}
      - SCAN_BLACKLIST=${SCAN_BLACKLIST:-}
      - RATE_LIMIT_GLOBAL=100
      - RATE_LIMIT_PER_IP=20
      - RATE_LIMIT_PER_KEY=50
    volumes:
      - ~/.ssh:/root/.ssh:ro
    restart: unless-stopped
```

## MCP Server

netkit-api includes an MCP (Model Context Protocol) server for integration with Claude AI and other AI assistants.

**Ready-to-use configurations:** See [examples/mcp-catalogs](examples/mcp-catalogs/) for pre-configured MCP catalog examples (quick diagnostics, SSL audits, security scans).

### Quick Start - Command Line

```bash
docker run -i \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -v ~/.ssh:/root/.ssh:ro \
  flengure/netkit-api:latest
```

### Claude Desktop Configuration

Add to your Claude Desktop config file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`  
**Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "netkit-api": {
      "type": "stdio",
      "description": "Network diagnostics, scanning, and security toolkit",
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--cap-add=NET_RAW",
        "--cap-add=NET_ADMIN",
        "-v",
        "/Users/YOUR_USERNAME/.ssh:/root/.ssh:ro",
        "-e",
        "SCAN_WHITELIST=10.0.0.0/8,192.168.0.0/16,*.example.com",
        "-e",
        "SCAN_BLACKLIST=*.internal.corp,*.local",
        "flengure/netkit-api:latest"
      ]
    }
  }
}
```

**Note:** The container defaults to MCP stdio mode, so no command arguments are needed. Use `--http` only if you want HTTP API mode instead.

**⚠️ Important Notes:**

1. **Use absolute paths** - Replace `/Users/YOUR_USERNAME/.ssh` with your actual home directory path. Docker does not expand `~` (tilde) when used in JSON config files.
   - macOS/Linux: Use full path like `/Users/john/.ssh` or `/home/john/.ssh`
   - Windows: Use forward slashes like `C:/Users/john/.ssh`

2. **Network capabilities are optional** - The `--cap-add` flags enable advanced scanning features:
   - **With capabilities**: nmap SYN scans, masscan, traceroute, mtr, OS detection
   - **Without capabilities**: All other tools still work (dig, whois, curl, sslscan, testssl.sh, nikto, whatweb, ssh, nc, ping)
   - Remove `"--cap-add=NET_RAW", "--cap-add=NET_ADMIN",` if you only need basic tools

3. **SSH key access is optional** - The `.ssh` volume mount provides:
   - ✅ Access to your SSH private keys (`id_rsa`, `id_ed25519`, etc.)
   - ✅ Access to your `~/.ssh/config` shortcuts and aliases
   - ✅ Access to your `~/.ssh/known_hosts` for host verification
   - ❌ **Does NOT disable the `ssh` tool** - SSH remains available even without the mount, you just won't have access to your local keys and config
   - Remove the volume mount lines if you don't need SSH key-based authentication

4. **Whitelist/Blacklist are inline** - `SCAN_WHITELIST` and `SCAN_BLACKLIST` are comma-separated values in environment variables, not file paths. Adjust the values to match your network security requirements.

**After adding the config:**
1. Pull the Docker image: `docker pull flengure/netkit-api:latest`
2. Restart Claude Desktop completely
3. You'll see "netkit-api" available in your MCP servers

### Minimal Configuration (Basic Tools Only)

If you only need DNS, HTTP, and security testing tools without advanced scanning:

```json
{
  "mcpServers": {
    "netkit-api": {
      "type": "stdio",
      "description": "Network diagnostics and security toolkit",
      "command": "docker",
      "args": [
        "run",
        "-i",
        "flengure/netkit-api:latest"
      ]
    }
  }
}
```

This provides: dig, host, whois, curl, ping, nc, sslscan, testssl.sh, nikto, whatweb

### MCP Tools

All 15 tools are exposed as MCP tools with the same names:
- **SSH**: ssh
- **Network Scanning**: nmap, masscan (requires capabilities)
- **DNS**: dig, host, whois
- **HTTP/Security**: curl, sslscan, testssl.sh, nikto, whatweb
- **Network Diagnostics**: traceroute (requires capabilities), mtr (requires capabilities), ping, nc

### Troubleshooting

**"includes invalid characters for a local volume name"**
- You're using `~` in the JSON config. Replace it with the absolute path to your home directory.
- ❌ Wrong: `"~/.ssh:/root/.ssh:ro"`
- ✅ Correct: `"/Users/john/.ssh:/root/.ssh:ro"`

**"Permission denied" or tools not working**
- Some tools require `--cap-add=NET_RAW` and `--cap-add=NET_ADMIN`
- Check which tools need capabilities in the Available Tools table above
- If using only basic tools (dig, curl, whois), you can remove the capability flags

**"SSH authentication failed" or "Host key verification failed"**
- Ensure your `.ssh` directory is mounted to the correct path: `"-v", "/full/path/to/.ssh:/root/.ssh:ro"`
- Container runs as **root**, so SSH keys must be mounted to `/root/.ssh`, not `/home/runner/.ssh`
- Verify your private keys have correct permissions (600) on the host
- The `ssh` tool will still work without the mount, you just need to provide credentials another way

**"Server disconnected" or MCP not connecting**
- Check Docker is running: `docker ps`
- Pull the image manually: `docker pull flengure/netkit-api:latest`
- Verify JSON syntax in your Claude config (use a JSON validator)
- Check Claude Desktop logs for detailed error messages

## Security

- **Container runs as non-root user** (UID 1000)
- **Network capabilities** are optional (CAP_NET_RAW for privileged scans)
- **Input validation** prevents command injection
- **Rate limiting** on multiple levels
- **Target validation** with whitelist/blacklist support
- **Request size limits** (1MB max)
- **Security headers** on all responses

See [SECURITY.md](SECURITY.md) for detailed security information.

## Development

### Local Development

```bash
# Install dependencies
pip install -r api/requirements.txt

# Run API server
python api/api.py

# Run MCP server
python mcp/server.py
```

### Testing

```bash
pytest tests/
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
