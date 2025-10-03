"""
Target validation for network scanning operations.

Supports whitelist and blacklist with:
- IP addresses (IPv4/IPv6)
- CIDR ranges
- Domain names
- Wildcard patterns (*.example.com)
"""

import ipaddress
import re
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class TargetValidator:
    """
    Validates scan targets against whitelist/blacklist rules
    """

    def __init__(
        self,
        whitelist: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None,
        allow_private: bool = False
    ):
        """
        Initialize target validator

        Args:
            whitelist: List of allowed targets (CIDR, domains, wildcards)
                      If None or empty, all targets allowed (except blacklisted)
            blacklist: List of forbidden targets (takes precedence over whitelist)
            allow_private: Allow RFC1918 private IP addresses
        """
        self.whitelist = whitelist or []
        self.blacklist = blacklist or []
        self.allow_private = allow_private

        # Parse CIDR ranges for faster lookup
        self.whitelist_networks = self._parse_networks(self.whitelist)
        self.blacklist_networks = self._parse_networks(self.blacklist)

        logger.info(
            f"Target validator initialized: "
            f"whitelist={len(self.whitelist)}, "
            f"blacklist={len(self.blacklist)}, "
            f"allow_private={allow_private}"
        )

    def _parse_networks(self, targets: List[str]) -> List:
        """
        Parse CIDR notation into network objects

        Args:
            targets: List of target specifications

        Returns:
            List of ipaddress network objects
        """
        networks = []
        for target in targets:
            try:
                # Try to parse as IP network (handles both single IPs and CIDR)
                networks.append(ipaddress.ip_network(target, strict=False))
            except ValueError:
                # Not an IP/CIDR - must be domain/wildcard
                pass
        return networks

    def _is_private_ip(self, ip_str: str) -> bool:
        """
        Check if IP is private (RFC1918, RFC4193, etc.)

        Args:
            ip_str: IP address string

        Returns:
            True if private IP
        """
        try:
            ip = ipaddress.ip_address(ip_str)
            return ip.is_private
        except ValueError:
            return False

    def _is_ip_address(self, target: str) -> bool:
        """Check if target is a valid IP address"""
        try:
            ipaddress.ip_address(target)
            return True
        except ValueError:
            return False

    def _matches_wildcard(self, target: str, pattern: str) -> bool:
        """
        Match domain against wildcard pattern

        Args:
            target: Target domain name
            pattern: Wildcard pattern (e.g., *.example.com)

        Returns:
            True if matches
        """
        # Convert wildcard to regex
        regex = pattern.replace(".", r"\.").replace("*", ".*")
        return bool(re.match(f"^{regex}$", target, re.IGNORECASE))

    def _check_ip_in_networks(
        self,
        ip_str: str,
        networks: List
    ) -> Optional[ipaddress.IPv4Network]:
        """
        Check if IP is in any of the networks

        Args:
            ip_str: IP address string
            networks: List of network objects

        Returns:
            Matching network or None
        """
        try:
            ip = ipaddress.ip_address(ip_str)
            for network in networks:
                if ip in network:
                    return network
        except ValueError:
            pass
        return None

    def validate(self, target: str) -> Tuple[bool, Optional[str]]:
        """
        Validate target against all rules

        Args:
            target: Target to validate (IP, domain, etc.)

        Returns:
            (allowed: bool, reason: Optional[str])
                - (True, None) if allowed
                - (False, "reason") if blocked
        """
        target = target.strip()

        if not target:
            return False, "Target cannot be empty"

        # Check if target is an IP address
        is_ip = self._is_ip_address(target)

        # 1. Check blacklist first (takes precedence)
        if is_ip:
            # Check IP blacklist
            match = self._check_ip_in_networks(target, self.blacklist_networks)
            if match:
                logger.warning(f"Target {target} blocked by blacklist: {match}")
                return False, f"Target {target} is blacklisted (matches {match})"

        # Check domain/wildcard blacklist
        for blacklist_item in self.blacklist:
            if self._matches_wildcard(target, blacklist_item):
                logger.warning(f"Target {target} blocked by blacklist: {blacklist_item}")
                return False, f"Target {target} is blacklisted (matches {blacklist_item})"

        # 2. Check private IP restriction
        if is_ip and not self.allow_private and self._is_private_ip(target):
            logger.warning(f"Private IP rejected: {target}")
            return False, f"Private IP addresses not allowed: {target}"

        # 3. Check whitelist (if configured)
        if self.whitelist:
            # If whitelist exists, target MUST match something in it

            if is_ip:
                # Check IP whitelist
                match = self._check_ip_in_networks(target, self.whitelist_networks)
                if match:
                    logger.debug(f"Target {target} allowed by whitelist: {match}")
                    return True, None

            # Check domain/wildcard whitelist
            for whitelist_item in self.whitelist:
                if self._matches_wildcard(target, whitelist_item):
                    logger.debug(f"Target {target} allowed by whitelist: {whitelist_item}")
                    return True, None

            # Not in whitelist
            logger.warning(f"Target {target} not in whitelist")
            return False, f"Target {target} not in whitelist"

        # 4. No whitelist configured = allow all (except blacklisted/private)
        logger.debug(f"Target {target} allowed (no whitelist configured)")
        return True, None

    def validate_multiple(self, targets: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Validate multiple targets

        Args:
            targets: List of targets to validate

        Returns:
            (all_allowed: bool, first_error: Optional[str])
        """
        for target in targets:
            allowed, reason = self.validate(target)
            if not allowed:
                return False, reason
        return True, None
