"""
Tool executors for all supported network/system tools.

Each executor inherits from BaseExecutor and implements tool-specific logic.
"""

import os
import logging
from typing import Dict, Any, List
from base_executor import BaseExecutor
from capabilities import require_net_raw

logger = logging.getLogger(__name__)


class SSHExecutor(BaseExecutor):
    """SSH command execution via OpenSSH client"""

    TOOL_NAME = "ssh"
    DESCRIPTION = "Run commands on remote servers"
    REQUIRES_CAP_NET_RAW = False

    # SSH-specific defaults
    EPHEMERAL_DEFAULTS = [
        "-o", "BatchMode=yes",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "StrictHostKeyChecking=no",
        "-o", "CheckHostIP=no",
        "-o", "LogLevel=ERROR",
    ]

    def process_args(self, args: List[str], params: Dict[str, Any]) -> List[str]:
        """
        Build SSH-specific command arguments

        Supports legacy exec_ssh.py parameter format for backward compatibility
        """
        # If using legacy format with host/command params
        if "host" in params and "command" not in params and "args" not in params:
            return self._build_ssh_command_legacy(params)

        # Standard format: ssh [options] user@host command
        # Just pass through the args
        return args

    def _build_ssh_command_legacy(self, params: Dict[str, Any]) -> List[str]:
        """Build SSH command from legacy exec_ssh.py parameters"""
        opts = list(self.EPHEMERAL_DEFAULTS)

        # Port
        port = params.get("port")
        if port:
            opts += ["-p", str(port)]

        # SSH directory for config
        ssh_dir = params.get("ssh_dir", os.getenv("SSH_DIR", "~/.ssh"))
        if ssh_dir:
            ssh_dir = os.path.expanduser(ssh_dir)
            if os.path.isdir(ssh_dir):
                cfg = os.path.join(ssh_dir, "config")
                if os.path.exists(cfg):
                    opts += ["-F", cfg]

        # Host key checking
        strict = params.get("strict_host_key_checking")
        if strict:
            opts += ["-o", f"StrictHostKeyChecking={strict}"]

        # Proxy jump
        proxy_jump = params.get("proxy_jump")
        if proxy_jump:
            opts += ["-J", proxy_jump]

        # TTY allocation
        if params.get("allocate_tty"):
            opts += ["-t"]

        # Extra options
        extra_opts = params.get("extra_opts", [])
        if extra_opts:
            opts += [str(x) for x in extra_opts]

        # Build target
        host = params["host"]
        user = params.get("user")
        target = f"{user}@{host}" if user else host

        # Command
        command = params.get("command", "")

        return opts + [target, "--", command]


class NmapExecutor(BaseExecutor):
    """Nmap network scanner"""

    TOOL_NAME = "nmap"
    DESCRIPTION = "Scan ports and detect services"
    REQUIRES_CAP_NET_RAW = True  # For SYN scans, OS detection

    MAX_TIMEOUT = 1800  # 30 minutes for large scans

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with capability check"""
        # Check for privileged scan types
        args_str = str(params.get("args", [])) + str(params.get("command", ""))

        privileged_flags = ["-sS", "-sA", "-sW", "-sM", "-O", "-sU"]
        needs_cap = any(flag in args_str for flag in privileged_flags)

        if needs_cap:
            require_net_raw()

        return super().execute(params)


class DigExecutor(BaseExecutor):
    """DNS lookup utility"""

    TOOL_NAME = "dig"
    DESCRIPTION = "Query DNS records (A, MX, TXT, etc.)"
    REQUIRES_CAP_NET_RAW = False


class HostExecutor(BaseExecutor):
    """DNS lookup utility (simpler than dig)"""

    TOOL_NAME = "host"
    DESCRIPTION = "Quick DNS lookup"
    REQUIRES_CAP_NET_RAW = False


class WhoisExecutor(BaseExecutor):
    """Domain WHOIS lookup"""

    TOOL_NAME = "whois"
    DESCRIPTION = "Query domain registration info"
    REQUIRES_CAP_NET_RAW = False


class CurlExecutor(BaseExecutor):
    """HTTP/HTTPS client"""

    TOOL_NAME = "curl"
    DESCRIPTION = "Fetch URLs and test HTTP endpoints"
    REQUIRES_CAP_NET_RAW = False


class TracerouteExecutor(BaseExecutor):
    """Network path tracing"""

    TOOL_NAME = "traceroute"
    DESCRIPTION = "Show network path to host"
    REQUIRES_CAP_NET_RAW = True  # For ICMP/UDP raw packets

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with capability check"""
        require_net_raw()
        return super().execute(params)


class MtrExecutor(BaseExecutor):
    """Network diagnostic tool (combines ping + traceroute)"""

    TOOL_NAME = "mtr"
    DESCRIPTION = "Live network diagnostics (traceroute + ping)"
    REQUIRES_CAP_NET_RAW = True  # For ICMP packets

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with capability check"""
        require_net_raw()
        return super().execute(params)


class NetcatExecutor(BaseExecutor):
    """Netcat - TCP/UDP network tool"""

    TOOL_NAME = "nc"
    DESCRIPTION = "Connect to TCP/UDP ports"
    REQUIRES_CAP_NET_RAW = False


class SSLScanExecutor(BaseExecutor):
    """SSL/TLS scanner"""

    TOOL_NAME = "sslscan"
    DESCRIPTION = "Test SSL/TLS cipher suites"
    REQUIRES_CAP_NET_RAW = False


class TestSSLExecutor(BaseExecutor):
    """testssl.sh - comprehensive SSL/TLS tester"""

    TOOL_NAME = "testssl.sh"
    DESCRIPTION = "Comprehensive TLS security audit"
    REQUIRES_CAP_NET_RAW = False

    MAX_TIMEOUT = 600  # Tests can take a while


class NiktoExecutor(BaseExecutor):
    """Nikto web server scanner"""

    TOOL_NAME = "nikto"
    DESCRIPTION = "Scan web servers for vulnerabilities"
    REQUIRES_CAP_NET_RAW = False

    MAX_TIMEOUT = 1800  # 30 minutes for thorough scans


class WhatWebExecutor(BaseExecutor):
    """WhatWeb - web technology identifier"""

    TOOL_NAME = "whatweb"
    DESCRIPTION = "Detect web technologies"
    REQUIRES_CAP_NET_RAW = False


class MasscanExecutor(BaseExecutor):
    """Masscan - fast port scanner"""

    TOOL_NAME = "masscan"
    DESCRIPTION = "Fast mass port scanner"
    REQUIRES_CAP_NET_RAW = True  # Requires raw sockets

    MAX_TIMEOUT = 1800  # 30 minutes

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with capability check"""
        require_net_raw()
        return super().execute(params)


class PingExecutor(BaseExecutor):
    """ICMP ping"""

    TOOL_NAME = "ping"
    DESCRIPTION = "Test host connectivity"
    REQUIRES_CAP_NET_RAW = False  # Modern ping uses ICMP sockets (no raw needed)

    def process_args(self, args: List[str], params: Dict[str, Any]) -> List[str]:
        """Add reasonable defaults to ping"""
        # If no count specified, add -c 4 to prevent infinite ping
        args_str = " ".join(args)
        if "-c" not in args_str and "--count" not in args_str:
            args = ["-c", "4"] + args

        return args


# Tool registry - maps tool names to executor instances
def get_tool_registry(target_validator=None) -> Dict[str, BaseExecutor]:
    """
    Get registry of all available tools

    Args:
        target_validator: Optional TargetValidator for scan operations

    Returns:
        Dictionary mapping tool names to executor instances
    """
    return {
        "ssh": SSHExecutor(target_validator),
        "nmap": NmapExecutor(target_validator),
        "dig": DigExecutor(target_validator),
        "host": HostExecutor(target_validator),
        "whois": WhoisExecutor(target_validator),
        "curl": CurlExecutor(target_validator),
        "traceroute": TracerouteExecutor(target_validator),
        "mtr": MtrExecutor(target_validator),
        "nc": NetcatExecutor(target_validator),
        "sslscan": SSLScanExecutor(target_validator),
        "testssl": TestSSLExecutor(target_validator),
        "nikto": NiktoExecutor(target_validator),
        "whatweb": WhatWebExecutor(target_validator),
        "masscan": MasscanExecutor(target_validator),
        "ping": PingExecutor(target_validator),
    }
