# netkit-api

**Remote operations toolkit**

FastAPI-based HTTP/MCP API for network diagnostics, scanning, and security auditing.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Docker Pulls](https://img.shields.io/docker/pulls/flengure/netkit-api)](https://hub.docker.com/r/flengure/netkit-api)

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
- 🔑 **Authentication** - Optional JWT tokens + API keys
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
# Basic HTTP API
docker run -d \
  -p 8090:8090 \
  flengure/netkit-api:latest --http

# With authentication and capabilities
docker run -d \
  -p 8090:8090 \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -e API_KEYS=api-key-1,api-key-2 \
  -v ~/.ssh:/home/runner/.ssh:ro \
  flengure/netkit-api:latest --http

# With JWT auth
docker run -d \
  -p 8090:8090 \
  -e JWT_SECRET=your-secret-key \
  flengure/netkit-api:latest --http
```

**Note:** Authentication is **optional** in HTTP mode. If neither `JWT_SECRET` nor `API_KEYS` are set, the API accepts all requests (use only for local/trusted networks).

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

## API Endpoints

### Tool Execution
- `POST /exec` - Execute any tool (unified endpoint)
- `GET /tools` - List all available tools
- `GET /tools/<name>` - Get info about specific tool

### Async Jobs
- `GET /jobs/<id>` - Get job status/result
- `DELETE /jobs/<id>` - Delete job
- `GET /jobs?status=running` - List jobs

### System
- `GET /healthz` - Health check with capabilities
- `GET /stats` - API statistics

## Configuration

### Environment Variables

**Authentication** (optional):
```bash
# Enable authentication by setting one or both:
JWT_SECRET=your-secret-key-here  # Enable JWT authentication
API_KEYS=key1,key2,key3          # Enable API key authentication

# If neither is set, authentication is disabled (local/trusted networks only)
```

**Rate Limiting**:
```bash
RATE_LIMIT_GLOBAL=100      # requests/min globally
RATE_LIMIT_PER_IP=20       # requests/min per IP
RATE_LIMIT_PER_KEY=50      # requests/min per API key
```

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
SSH_DIR=/home/runner/.ssh
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
      - ~/.ssh:/home/runner/.ssh:ro
    restart: unless-stopped
```

## MCP Server

netkit-api includes an MCP (Model Context Protocol) server for integration with Claude AI and other AI assistants.

### Quick Start - Command Line

```bash
docker run -i \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -v ~/.ssh:/home/runner/.ssh:ro \
  flengure/netkit-api:latest \
  python /app/mcp/server.py
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
        "/Users/YOUR_USERNAME/.ssh:/home/runner/.ssh:ro",
        "-e",
        "SSH_DIR=/home/runner/.ssh",
        "-e",
        "SCAN_WHITELIST=10.0.0.0/8,192.168.0.0/16,*.example.com",
        "-e",
        "SCAN_BLACKLIST=*.internal.corp,*.local",
        "flengure/netkit-api:latest",
        "python",
        "/app/mcp/server.py"
      ]
    }
  }
}
```

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
        "flengure/netkit-api:latest",
        "python",
        "/app/mcp/server.py"
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
- ❌ Wrong: `"~/.ssh:/home/runner/.ssh:ro"`
- ✅ Correct: `"/Users/john/.ssh:/home/runner/.ssh:ro"`

**"Permission denied" or tools not working**
- Some tools require `--cap-add=NET_RAW` and `--cap-add=NET_ADMIN`
- Check which tools need capabilities in the Available Tools table above
- If using only basic tools (dig, curl, whois), you can remove the capability flags

**"SSH authentication failed" or "Host key verification failed"**
- Ensure your `.ssh` directory is mounted: `"-v", "/full/path/to/.ssh:/home/runner/.ssh:ro"`
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
