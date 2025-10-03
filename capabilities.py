"""
Runtime capability detection for privileged network operations.

Checks for Linux capabilities like CAP_NET_RAW which are required
for certain network tools (nmap SYN scans, raw sockets, etc.)
"""

import subprocess
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def has_net_raw() -> bool:
    """
    Check if CAP_NET_RAW capability is available

    Tests by attempting a SYN scan with nmap to localhost.
    If it fails with "requires root privileges", we don't have the capability.

    Returns:
        True if CAP_NET_RAW is available, False otherwise
    """
    try:
        # Quick SYN scan test to localhost
        result = subprocess.run(
            ["nmap", "-sS", "-p", "80", "--host-timeout", "1s", "127.0.0.1"],
            capture_output=True,
            timeout=3,
            text=True
        )

        # Check if error mentions root/privileges
        error_output = result.stderr.lower()
        lacks_cap = (
            "requires root privileges" in error_output or
            "you requested a scan type which requires root" in error_output or
            "permission denied" in error_output
        )

        has_cap = not lacks_cap

        if has_cap:
            logger.info("CAP_NET_RAW detected - privileged network operations enabled")
        else:
            logger.warning(
                "CAP_NET_RAW not available - privileged operations will fail. "
                "Run container with: --cap-add=NET_RAW --cap-add=NET_ADMIN"
            )

        return has_cap

    except FileNotFoundError:
        logger.warning("nmap not found - cannot check CAP_NET_RAW")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("CAP_NET_RAW check timed out")
        return False
    except Exception as e:
        logger.warning(f"CAP_NET_RAW check failed: {e}")
        return False


@lru_cache(maxsize=1)
def get_capabilities_info() -> dict:
    """
    Get detailed capability information for health checks

    Returns:
        Dictionary with capability status
    """
    net_raw = has_net_raw()

    return {
        "net_raw": net_raw,
        "net_admin": net_raw,  # Usually granted together
        "features": {
            "ssh": True,  # Always available
            "dns_tools": True,  # dig, host, whois don't need special caps
            "web_tools": True,  # curl, httpie don't need special caps
            "nmap_syn_scan": net_raw,
            "nmap_connect_scan": True,  # TCP connect doesn't need root
            "nmap_os_detection": net_raw,
            "traceroute": net_raw,
            "raw_sockets": net_raw
        }
    }


def require_net_raw():
    """
    Raise error if CAP_NET_RAW not available

    Raises:
        PermissionError: If CAP_NET_RAW is not available
    """
    if not has_net_raw():
        raise PermissionError(
            "This operation requires CAP_NET_RAW capability. "
            "Run container with: --cap-add=NET_RAW --cap-add=NET_ADMIN"
        )
