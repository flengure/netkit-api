# Configuration Guide

netkit-api supports configuration via **config files** and **environment variables**, with automatic merging.

## Configuration Priority

1. **Environment variables** (highest priority)
2. **Config file** (YAML or JSON)
3. **Defaults** (lowest priority)

For **lists** (whitelist/blacklist), config file and environment variables are **merged** (combined).

## Config File Locations

Config files are checked in this order:

1. Path from `CONFIG_FILE` environment variable
2. `/etc/netkit-api/config.yaml`
3. `/etc/netkit-api/config.json`
4. `./config.yaml` (current directory)
5. `./config.json` (current directory)

First file found is used. Supports both YAML and JSON formats.

## Configuration Options

### Authentication

Control access to the HTTP API:

```yaml
# API keys for X-API-Key header authentication
api_keys:
  - key-1
  - key-2

# JWT secret for Bearer token authentication
jwt_secret: your-secret-key-here
```

**Environment variables:**
```bash
API_KEYS=key-1,key-2
JWT_SECRET=your-secret-key-here
```

**Note:** If neither is set, authentication is **disabled** (use only for local/trusted networks).

### Rate Limiting

Prevent abuse with request rate limits:

```yaml
rate_limit_global: 100      # requests/min globally
rate_limit_per_ip: 20       # requests/min per IP
rate_limit_per_key: 50      # requests/min per API key
```

**Environment variables:**
```bash
RATE_LIMIT_GLOBAL=100
RATE_LIMIT_PER_IP=20
RATE_LIMIT_PER_KEY=50
```

### Target Validation

Control which **destinations** can be scanned:

```yaml
# Whitelist: only these targets allowed (if set)
# Supports: IPs, CIDR ranges, domains, wildcards
scan_whitelist:
  - 10.0.0.0/8              # Private network range
  - 192.168.0.0/16          # Another range
  - scanme.nmap.org         # Specific domain
  - "*.example.com"         # Wildcard domain

# Blacklist: these targets blocked (overrides whitelist)
scan_blacklist:
  - 10.0.0.1                # Specific IP
  - 192.168.1.1             # Router
  - "*.internal.corp"       # Internal domains
  - "*.local"               # Local domains

# Allow RFC1918 private IPs (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
allow_private_ips: false
```

**Environment variables:**
```bash
SCAN_WHITELIST="10.0.0.0/8,192.168.0.0/16,*.example.com"
SCAN_BLACKLIST="10.0.0.1,*.internal.corp"
ALLOW_PRIVATE_IPS=false
```

**Merging behavior:**
```bash
# File contains: 10.0.0.0/8, *.example.com
# Env contains: scanme.nmap.org
# Result: 10.0.0.0/8, *.example.com, scanme.nmap.org
```

**Validation priority:**
1. Blacklist check (highest - blocks even if whitelisted)
2. Private IP check (if `allow_private_ips=false`)
3. Whitelist check (if configured, target must match)
4. Allow all (if no whitelist configured)

**Note:** Currently validates **destination targets only** (scan targets, not source IPs).

### Job Management

Control async job execution:

```yaml
max_concurrent_jobs: 100
job_cleanup_interval: 3600  # seconds
```

**Environment variables:**
```bash
MAX_CONCURRENT_JOBS=100
JOB_CLEANUP_INTERVAL=3600
```

### SSH

Path to SSH configuration directory:

```yaml
ssh_dir: ~/.ssh
```

**Environment variables:**
```bash
SSH_DIR=~/.ssh
```

### API Server

HTTP server port:

```yaml
api_port: 8090
```

**Environment variables:**
```bash
API_PORT=8090
```

## Docker Usage

### Mount Config File

Mount a config file into the container:

```bash
docker run -d \
  -p 8090:8090 \
  -v /path/to/config.yaml:/etc/netkit-api/config.yaml:ro \
  flengure/netkit-api:latest
```

### Environment Variables Only

```bash
docker run -d \
  -p 8090:8090 \
  -e API_KEYS=key1,key2 \
  -e SCAN_WHITELIST="10.0.0.0/8,*.example.com" \
  flengure/netkit-api:latest
```

### Combined (Merged)

Config file + environment variables are merged:

```bash
docker run -d \
  -p 8090:8090 \
  -v /path/to/config.yaml:/etc/netkit-api/config.yaml:ro \
  -e SCAN_WHITELIST="scanme.nmap.org" \
  flengure/netkit-api:latest
```

In this example, `scan_whitelist` from file and env are **combined**.

## Docker Compose

```yaml
version: '3.8'

services:
  netkit-api:
    image: flengure/netkit-api:latest
    ports:
      - "8090:8090"
    volumes:
      - ./config.yaml:/etc/netkit-api/config.yaml:ro
      - ~/.ssh:/home/runner/.ssh:ro
    environment:
      # Override or extend config file settings
      - SCAN_WHITELIST=${SCAN_WHITELIST:-}
      - API_KEYS=${API_KEYS}
    cap_add:
      - NET_RAW
      - NET_ADMIN
```

## MCP Server

For MCP (Model Context Protocol) usage with config file:

```json
{
  "mcpServers": {
    "netkit-api": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--cap-add=NET_RAW",
        "--cap-add=NET_ADMIN",
        "-v", "/path/to/config.yaml:/etc/netkit-api/config.yaml:ro",
        "flengure/netkit-api:latest",
        "python", "/app/mcp/server.py"
      ]
    }
  }
}
```

Or with environment variables:

```json
{
  "mcpServers": {
    "netkit-api": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "SCAN_WHITELIST=10.0.0.0/8,*.example.com",
        "-e", "SCAN_BLACKLIST=*.internal.corp",
        "flengure/netkit-api:latest",
        "python", "/app/mcp/server.py"
      ]
    }
  }
}
```

## Example Config Files

See:
- `config.example.yaml` - YAML format with comments
- `config.example.json` - JSON format

Copy and customize for your deployment:

```bash
cp config.example.yaml /etc/netkit-api/config.yaml
# Edit /etc/netkit-api/config.yaml
```

## Security Best Practices

1. **Use config files for long whitelist/blacklist entries** (easier to manage than env vars)
2. **Use env vars for secrets** (JWT_SECRET, API_KEYS) to avoid committing to version control
3. **Mount config files read-only** (`:ro`) in Docker
4. **Set restrictive permissions** on config files containing API keys:
   ```bash
   chmod 600 /etc/netkit-api/config.yaml
   ```
5. **Use whitelist mode** for production (set `scan_whitelist` to explicitly allowed targets)
6. **Disable private IPs** unless needed (`allow_private_ips: false`)
7. **Always use blacklist** for known internal/sensitive ranges

## Troubleshooting

Check which config file is loaded:

```bash
docker logs <container_id> 2>&1 | grep "Loading config"
```

Output will show:
- `No config file found, using environment variables only`
- `Loading config from: /etc/netkit-api/config.yaml`

Verify merged whitelist/blacklist:

```bash
docker logs <container_id> 2>&1 | grep "merged file"
```

Output shows merge details:
```
scan_whitelist: merged file (3 items) + env (1 items) = 4 items
```
