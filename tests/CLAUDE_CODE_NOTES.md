# Claude Code Notes - README Updates

**Date**: October 3, 2025  
**Updated by**: Claude (via user request)

## Summary of Changes

Updated the MCP Server section of README.md with comprehensive Claude Desktop configuration guidance based on real-world testing and user feedback.

## Key Changes Made

### 1. Added Claude Desktop Configuration Section
- Complete JSON configuration example for macOS, Windows, and Linux
- Step-by-step setup instructions
- Post-installation checklist

### 2. Critical Path Issue: Docker Tilde Expansion
**Problem Discovered**: Docker does not expand `~` (tilde) in volume mount paths when specified in JSON configuration files.

**Error Encountered**:
```
docker: Error response from daemon: create ~/.ssh: "~/.ssh" includes invalid characters for a local volume name
```

**Solution**: Use absolute paths instead of `~`
- ❌ Wrong: `"~/.ssh:/home/runner/.ssh:ro"`
- ✅ Correct: `"/Users/john/.ssh:/home/runner/.ssh:ro"`

This is documented in the README with warnings and examples for all platforms.

### 3. Clarified Optional Dependencies

**Network Capabilities (`--cap-add`)**:
- Documented which tools require `NET_RAW` and `NET_ADMIN` capabilities
- Explained that capabilities are optional - many tools work without them
- Added "Minimal Configuration" example without capability flags
- Tools that work WITHOUT capabilities: dig, host, whois, curl, ping, nc, sslscan, testssl.sh, nikto, whatweb, ssh
- Tools that NEED capabilities: nmap (SYN scans, OS detection), masscan, traceroute, mtr

**SSH Volume Mount**:
- Clarified what the `.ssh` mount actually provides (keys, config, known_hosts)
- **Important correction**: Removing the mount does NOT disable the `ssh` tool
  - The `ssh` tool is baked into the container and always available
  - The mount only provides access to local SSH keys and configuration
  - Without the mount, SSH still works with password auth or inline credentials

### 4. Environment Variable Clarifications

**SCAN_WHITELIST / SCAN_BLACKLIST**:
- These are comma-separated values in environment variables
- NOT file paths to external whitelist/blacklist files
- Example: `SCAN_WHITELIST=10.0.0.0/8,192.168.0.0/16,*.example.com`

**SSH_DIR**:
- Points to the SSH directory inside the container
- Default: `/home/runner/.ssh`
- Only relevant when mounting host `.ssh` directory

**CONFIG_DIR**:
- NOT currently implemented in the codebase
- Was incorrectly assumed to exist during initial analysis
- File-based whitelist/blacklist is not currently supported

### 5. Added Comprehensive Troubleshooting Section

Common issues documented:
1. Tilde expansion error (absolute path requirement)
2. Permission denied errors (capability requirements)
3. SSH authentication failures (volume mount issues)
4. MCP connection failures (Docker/JSON syntax)

Each issue includes:
- Error symptom
- Root cause
- Solution with examples

### 6. Enhanced MCP Tools Documentation
- Listed all 15 tools with categories
- Marked which tools require capabilities
- Clarified tool availability with/without configuration options

## Testing Notes

This update was validated through:
1. Real Claude Desktop integration test
2. Docker volume mount error reproduction and fix
3. Configuration syntax validation

## What Claude Code Should Know

When working with this codebase:

1. **Docker volume paths in configs must be absolute** - This is a Docker limitation, not a netkit-api limitation
2. **Capabilities are feature flags** - The container works without them, just with reduced functionality
3. **SSH tool ≠ SSH mount** - The tool is always present; the mount only affects key access
4. **No file-based config yet** - SCAN_WHITELIST/BLACKLIST are environment variables only
5. **MCP mode uses stdio** - Different from HTTP API mode which uses port 8090

## Future Improvement Suggestions

1. Consider adding file-based whitelist/blacklist support via CONFIG_DIR
2. Create an automated installer script that handles absolute path resolution
3. Add example configs for common use cases (pentesting, monitoring, basic DNS)
4. Document rate limiting behavior in MCP mode (if different from API mode)

## CRITICAL BUG FIX - Dockerfile ENTRYPOINT Issue

**Date**: October 3, 2025

### Problem
The MCP server was timing out and the HTTP API (port 8090) was starting instead of the MCP stdio server.

**Root Cause**: `Dockerfile` used `ENTRYPOINT` instead of `CMD`:
```dockerfile
ENTRYPOINT ["python", "/app/api/api.py"]  # ❌ WRONG
```

When running:
```bash
docker run ... flengure/netkit-api:latest python /app/mcp/server.py
```

Docker actually executed:
```bash
python /app/api/api.py python /app/mcp/server.py  # ENTRYPOINT + CMD
```

This caused `api.py` to run with broken arguments, starting the HTTP API instead of the MCP server.

### Symptoms
- MCP server times out after 60 seconds
- Logs show "Starting netkit-api v2.0 on port 8090"
- Uvicorn starts but never responds to MCP initialize request
- Error: "McpError: MCP error -32001: Request timed out"

### Solution
Changed `Dockerfile` from `ENTRYPOINT` to `CMD`:
```dockerfile
CMD ["python", "/app/api/api.py"]  # ✅ CORRECT
```

**Difference**:
- `ENTRYPOINT`: Arguments are **appended** to the entrypoint
- `CMD`: Arguments **replace** the CMD entirely

Now when running:
```bash
docker run ... flengure/netkit-api:latest python /app/mcp/server.py
```

Docker correctly executes:
```bash
python /app/mcp/server.py  # CMD replaced
```

### Files Modified
- `Dockerfile` - Line 86: Changed `ENTRYPOINT` to `CMD`

### Impact
**Users must rebuild/pull the updated image**:
```bash
# If using Docker Hub:
docker pull flengure/netkit-api:latest

# If building locally:
cd ~/Documents/projects/netkit-api
docker build -t flengure/netkit-api:latest .
```

---

## Related Files Modified
- `README.md` - Major updates to MCP Server section
- `Dockerfile` - Fixed ENTRYPOINT→CMD issue
- `CLAUDE_CODE_NOTES.md` - This file

## Links to Key Sections
- Claude Desktop Configuration: Lines ~306-350 in README.md
- Troubleshooting: Lines ~404-424 in README.md
- Important Notes: Lines ~352-373 in README.md
- Dockerfile Fix: Line 86 in Dockerfile
