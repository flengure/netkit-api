# MCP Server Setup Guide

This guide shows how to integrate netkit-api's MCP server with various AI assistants and IDEs.

## What is MCP?

Model Context Protocol (MCP) allows AI assistants to use netkit-api's 15 network tools directly. The AI can:
- Run DNS queries (dig, host, whois)
- Scan ports (nmap, masscan)
- Test connectivity (ping, traceroute, mtr)
- Fetch URLs (curl)
- Audit SSL/TLS (sslscan, testssl)
- And more!

---

## Claude Desktop

### Setup

1. **Find your config file:**
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux:** `~/.config/Claude/claude_desktop_config.json`

2. **Add netkit-api MCP server:**

```json
{
  "mcpServers": {
    "netkit-api": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--cap-add=NET_RAW",
        "--cap-add=NET_ADMIN",
        "flengure/netkit-api:latest",
        "python",
        "/app/mcp/server.py"
      ]
    }
  }
}
```

3. **Restart Claude Desktop**

### Usage

Just ask Claude to use network tools:
- "Check DNS records for google.com"
- "Scan ports 80 and 443 on example.com"
- "Test SSL configuration of github.com"

---

## Cline (VS Code Extension)

### Setup

1. **Install Cline extension** in VS Code

2. **Open Cline settings** (gear icon in Cline panel)

3. **Add MCP server** in the MCP Servers section:

```json
{
  "mcpServers": {
    "netkit-api": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--cap-add=NET_RAW",
        "--cap-add=NET_ADMIN",
        "flengure/netkit-api:latest",
        "python",
        "/app/mcp/server.py"
      ]
    }
  }
}
```

4. **Reload VS Code**

### Usage

In Cline chat:
- "Use netkit to check if api.example.com is up"
- "Scan common ports on my server"
- "Get SSL certificate info for my website"

---

## Cursor

### Setup

1. **Open Cursor settings:** `Cmd/Ctrl + ,`

2. **Search for "MCP"** or go to Extensions → MCP Settings

3. **Add server configuration:**

```json
{
  "mcp": {
    "servers": {
      "netkit-api": {
        "command": "docker",
        "args": [
          "run",
          "-i",
          "--rm",
          "--cap-add=NET_RAW",
          "--cap-add=NET_ADMIN",
          "flengure/netkit-api:latest",
          "python",
          "/app/mcp/server.py"
        ]
      }
    }
  }
}
```

4. **Restart Cursor**

### Usage

Ask Cursor's AI:
- "Check what DNS servers example.com uses"
- "Test if port 443 is open on my server"
- "Analyze the SSL configuration"

---

## Zed

### Setup

1. **Open Zed settings:**
   - macOS: `Cmd + ,`
   - Linux/Windows: `Ctrl + ,`

2. **Edit `settings.json`:**

```json
{
  "context_servers": {
    "netkit-api": {
      "command": {
        "path": "docker",
        "args": [
          "run",
          "-i",
          "--rm",
          "--cap-add=NET_RAW",
          "--cap-add=NET_ADMIN",
          "flengure/netkit-api:latest",
          "python",
          "/app/mcp/server.py"
        ]
      }
    }
  }
}
```

3. **Restart Zed**

### Usage

In Zed's assistant panel:
- "What's the MX record for this domain?"
- "Scan the server for open ports"
- "Check SSL certificate expiration"

---

## Alternative: Local Installation (No Docker)

If you prefer not to use Docker:

### Prerequisites
```bash
git clone https://github.com/flengure/netkit-api.git
cd netkit-api
pip install -r api/requirements.txt
```

### Configuration

Use this command instead in your MCP config:

```json
{
  "command": "python",
  "args": ["/path/to/netkit-api/mcp/server.py"]
}
```

**Note:** Local installation requires the tools to be installed on your system:
```bash
# macOS
brew install nmap masscan bind whois curl

# Debian/Ubuntu
apt install nmap masscan dnsutils whois curl netcat-openbsd sslscan

# Fedora/RHEL
dnf install nmap masscan bind-utils whois curl nmap sslscan
```

---

## Environment Variables

Add environment variables to the Docker command:

```json
{
  "command": "docker",
  "args": [
    "run",
    "-i",
    "--rm",
    "--cap-add=NET_RAW",
    "-e", "SCAN_WHITELIST=10.0.0.0/8,*.example.com",
    "-e", "SCAN_BLACKLIST=192.168.1.1",
    "-e", "ALLOW_PRIVATE_IPS=false",
    "flengure/netkit-api:latest",
    "python",
    "/app/mcp/server.py"
  ]
}
```

**Available options:**
- `SCAN_WHITELIST` - Comma-separated IPs/ranges to allow
- `SCAN_BLACKLIST` - Comma-separated IPs/ranges to block
- `ALLOW_PRIVATE_IPS` - Allow scanning private IPs (default: false)

---

## Troubleshooting

### MCP server not showing up
1. Check the config file syntax (valid JSON)
2. Restart the application completely
3. Check logs in the application

### Permission errors
Add capabilities to Docker command:
```bash
--cap-add=NET_RAW --cap-add=NET_ADMIN
```

### Tools not available
Run health check:
```bash
docker run --rm flengure/netkit-api:latest python -c "
from executors import get_tool_registry
registry = get_tool_registry()
for name, tool in registry.items():
    print(f'{name}: {tool.is_available()}')
"
```

### Docker not found
Ensure Docker is installed and running:
```bash
docker --version
```

---

## Available Tools

Once configured, the AI assistant can use these tools:

| Tool | Description |
|------|-------------|
| **ssh** | Run commands on remote servers |
| **nmap** | Scan ports and detect services |
| **masscan** | Fast mass port scanner |
| **dig** | Query DNS records (A, MX, TXT, etc.) |
| **host** | Quick DNS lookup |
| **whois** | Query domain registration info |
| **ping** | Test host connectivity |
| **traceroute** | Show network path to host |
| **mtr** | Live network diagnostics |
| **nc** | Connect to TCP/UDP ports |
| **curl** | Fetch URLs and test HTTP endpoints |
| **sslscan** | Test SSL/TLS cipher suites |
| **testssl** | Comprehensive TLS security audit |
| **nikto** | Scan web servers for vulnerabilities |
| **whatweb** | Detect web technologies |

---

## Security Considerations

- **Network capabilities:** Tools requiring `CAP_NET_RAW` need privileged access
- **Target validation:** Use `SCAN_WHITELIST` to restrict scan targets
- **Private IPs:** Disabled by default, enable with `ALLOW_PRIVATE_IPS=true`
- **Container isolation:** Docker provides process and network isolation

---

## Examples

### Check website availability
**Prompt:** "Is example.com up?"
**Tool used:** ping

### Audit SSL certificate
**Prompt:** "Check SSL certificate for api.example.com"
**Tool used:** testssl

### Find mail servers
**Prompt:** "What are the MX records for gmail.com?"
**Tool used:** dig

### Port scan
**Prompt:** "Scan ports 80, 443, 8080 on scanme.nmap.org"
**Tool used:** nmap

---

## Additional Resources

- **GitHub:** https://github.com/flengure/netkit-api
- **Docker Hub:** https://hub.docker.com/r/flengure/netkit-api
- **HTTP API Docs:** http://localhost:8090/docs (when running the API server)
- **MCP Protocol:** https://modelcontextprotocol.io

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review tool availability with the health check
3. Open an issue on GitHub: https://github.com/flengure/netkit-api/issues
