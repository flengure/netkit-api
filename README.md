# netkit-api

**Remote operations toolkit**

FastAPI-based HTTP/MCP API for network diagnostics, scanning, and security auditing.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Features

- 🔐 **SSH Execution** - Non-interactive command execution via OpenSSH
- 🌐 **DNS Tools** - dig, host, whois lookups
- 🔍 **Network Scanning** - nmap, masscan port scanning
- 🔒 **Security Auditing** - SSL/TLS analysis, vulnerability scanning
- 🌍 **Web Inspection** - curl HTTP/HTTPS inspection
- 📡 **Network Diagnostics** - traceroute, mtr, ping
- 🚀 **Async Execution** - Background jobs for long-running scans
- 🔑 **Authentication** - JWT tokens + API keys
- 🛡️ **Security** - Rate limiting, whitelist/blacklist, input validation
- 🔌 **MCP Integration** - Model Context Protocol for Claude AI

## Quick Start

### Full Features (Recommended)
Includes all tools with privileged network operations:

```bash
docker run -d \
  -p 8090:8090 \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -e JWT_SECRET=your-secret-key \
  -e API_KEYS=api-key-1,api-key-2 \
  -v ~/.ssh:/home/runner/.ssh:ro \
  flengure/netkit-api:latest
```

### Limited Features (More Secure)
SSH, DNS, and web tools only (no privileged scanning):

```bash
docker run -d \
  -p 8090:8090 \
  -e JWT_SECRET=your-secret-key \
  flengure/netkit-api:latest
```

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
- `GET /stats` - API statistics (auth required)

## Configuration

### Environment Variables

**Authentication**:
```bash
JWT_SECRET=your-secret-key-here
API_KEYS=key1,key2,key3
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

netkit-api includes an MCP (Model Context Protocol) server for integration with Claude AI.

### Run as MCP Server

```bash
docker run -i \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -v ~/.ssh:/home/runner/.ssh:ro \
  flengure/netkit-api:latest \
  python /app/mcp/server.py
```

### MCP Tools

All tools are exposed as MCP tools with the same names (ssh, nmap, dig, curl, etc.)

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
