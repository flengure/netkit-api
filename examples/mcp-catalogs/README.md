# MCP Catalog Manifests

This directory contains example MCP catalog manifests that create high-level composite tools using netkit-api.

## What Are MCP Catalogs?

MCP catalogs allow you to define custom tools that orchestrate multiple netkit-api calls into single high-level operations. They're defined in YAML and placed in `~/.mcp/catalogs/`.

## Installation

1. Copy manifests to your MCP catalogs directory:
   ```bash
   cp examples/mcp-catalogs/*.yaml ~/.mcp/catalogs/
   ```

2. Set your netkit-api credentials:
   ```bash
   export NETKIT_URL="https://netkit.tomage.net"
   export NETKIT_TOKEN="your-access-token-here"
   ```

3. Restart Claude Desktop to load the catalogs

## Available Catalogs

### 1. Security Audits (`security_audits.yaml`)
Complex security assessment workflows:
- **exposure_audit** - External port exposure analysis (IPv4/IPv6)
- **service_fingerprint_vulns** - Service version detection + CVE lookup
- **edge_stack_audit** - Hybrid external/internal firewall analysis

### 2. Quick Diagnostics (`quick_diagnostics.yaml`)
Common troubleshooting workflows:
- **dns_full_check** - Complete DNS analysis (A, AAAA, MX, TXT, NS)
- **web_health_check** - HTTP/HTTPS connectivity + SSL analysis
- **network_path_check** - Traceroute + MTR combined analysis

### 3. SSL/TLS Audits (`ssl_audits.yaml`)
Certificate and cipher testing:
- **ssl_comprehensive_audit** - Full SSL/TLS security assessment
- **ssl_certificate_check** - Certificate validity and chain analysis
- **ssl_cipher_strength** - Cipher suite strength testing

### 4. Domain Intelligence (`domain_intel.yaml`)
Domain reconnaissance:
- **domain_full_recon** - WHOIS + DNS + subdomain enumeration
- **mx_security_check** - Mail server security analysis
- **dns_security_audit** - DNSSEC + SPF + DMARC validation

### 5. Service Discovery (`service_discovery.yaml`)
Host and service enumeration:
- **host_full_scan** - Complete host discovery and port scan
- **web_stack_identify** - Web technology fingerprinting
- **service_version_audit** - Detailed service version enumeration

## Usage Examples

### Using in Claude Desktop

Once installed, these tools appear as regular MCP tools:

```
User: Run an exposure audit on example.com

Claude: I'll use the exposure_audit tool to scan example.com...
```

### Direct Testing

Test manifests before installation:

```bash
# Set credentials
export NETKIT_TOKEN=$(curl -sS -X POST \
  -d "grant_type=client_credentials" \
  -d "client_id=..." \
  -d "client_secret=..." \
  https://auth.example.com/token/ | jq -r .access_token)

# Test a manifest
bash -c "$(cat quick_diagnostics.yaml | yq -r '.dns_full_check.args[]')"
```

## Security Considerations

### Authentication

All manifests require authentication. Set one of:

**Option A: Bearer Token (OIDC)**
```bash
export NETKIT_TOKEN="eyJ..."  # Access token from OIDC provider
```

**Option B: API Key**
```bash
export NETKIT_API_KEY="your-api-key"
```

Manifests use `$NETKIT_TOKEN` by default. Edit to use `$NETKIT_API_KEY` if needed.

### Input Validation

⚠️ **Shell Injection Risk**: These manifests execute shell scripts with user input. Best practices:

1. **Validate inputs** - Use schema validation
2. **Escape variables** - Use `jq -R` for shell escaping
3. **Limit scope** - Restrict to trusted networks via `SCAN_WHITELIST`
4. **Review before use** - Audit shell scripts in manifests

### Network Restrictions

Configure netkit-api target validation:

```yaml
# In netkit-api docker-compose.yml
environment:
  - SCAN_WHITELIST=10.0.0.0/8,192.168.0.0/16,*.example.com
  - SCAN_BLACKLIST=*.internal.corp,169.254.0.0/16
```

## Customization

### Modify Manifests

Edit YAML files to:
- Change default ports
- Adjust scan timing (--min-rate)
- Add/remove scan types
- Customize output format

Example:
```yaml
# Change default TCP port range
tcp_ports:
  type: string
  description: "TCP ports to scan"
  default: "1-1000"  # Was: 1-65535
```

### Add Your Own

Create custom manifests:

```yaml
my_custom_tool:
  type: stdio
  description: "Your tool description"
  command: "bash"
  args:
    - "-c"
    - |
      #!/bin/bash
      NETKIT_TOKEN="${NETKIT_TOKEN:?required}"

      curl -sS -X POST https://netkit.tomage.net/exec \
        -H "Authorization: Bearer $NETKIT_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"command":"dig {{host}} +short"}'
  input_schema:
    type: object
    properties:
      host: {type: string}
    required: [host]
```

## Troubleshooting

### "NETKIT_TOKEN required"
Set environment variable:
```bash
export NETKIT_TOKEN="your-token"
```

### "Authentication failed"
Check token expiration:
```bash
echo $NETKIT_TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | jq .exp
```

### "Tool not found"
Verify manifest is in correct location:
```bash
ls ~/.mcp/catalogs/*.yaml
```

Restart Claude Desktop after adding manifests.

### "Command timeout"
Increase timeout in manifest:
```yaml
timeout: 300  # 5 minutes
```

Or adjust netkit-api global timeout.

## Performance Tips

1. **Use specific port ranges** - Avoid full 1-65535 scans
2. **Adjust --min-rate** - Lower for accuracy, higher for speed
3. **Enable caching** - Store results for repeated queries
4. **Parallel execution** - Use async mode for multiple hosts

## Contributing

Have a useful manifest? Submit a PR with:
- Clear description
- Usage examples
- Input/output schema
- Security considerations

## References

- [netkit-api Documentation](../../README.md)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [OIDC Setup Guide](../../docs/OIDC_SETUP.md)
