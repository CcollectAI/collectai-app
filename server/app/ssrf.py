"""
SSRF protection for URL validation.

Blocks requests to private/internal IP ranges to prevent
Server-Side Request Forgery attacks via intake URL imports.

Usage:
    from app.ssrf import validate_url

    validate_url("https://example.com/image.jpg")  # OK
    validate_url("http://169.254.169.254/")  # raises ValueError
    validate_url("http://10.0.0.1/secret")   # raises ValueError
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Private and special-use IP ranges that should never be accessed via SSRF
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),        # "This" network
    ipaddress.ip_network("10.0.0.0/8"),        # Private
    ipaddress.ip_network("100.64.0.0/10"),     # Carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local (AWS metadata!)
    ipaddress.ip_network("172.16.0.0/12"),     # Private
    ipaddress.ip_network("192.0.0.0/24"),      # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),      # TEST-NET-1
    ipaddress.ip_network("192.168.0.0/16"),    # Private
    ipaddress.ip_network("198.18.0.0/15"),     # Benchmarking
    ipaddress.ip_network("198.51.100.0/24"),   # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),    # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved
    ipaddress.ip_network("255.255.255.255/32"),# Broadcast
    # IPv6
    ipaddress.ip_network("::1/128"),           # Loopback
    ipaddress.ip_network("fc00::/7"),          # Unique local
    ipaddress.ip_network("fe80::/10"),         # Link-local
]

_ALLOWED_SCHEMES = {"http", "https"}


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address falls within blocked ranges."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # If we can't parse it, block it

    for network in _BLOCKED_NETWORKS:
        if addr in network:
            return True
    return False


def validate_url(url: str) -> str:
    """
    Validate a URL for SSRF safety.

    Checks:
    1. Scheme must be http or https
    2. Hostname must not resolve to a private/internal IP
    3. No IP-address hostnames pointing to private ranges

    Returns the validated URL on success.
    Raises ValueError on blocked URLs.
    """
    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"URL scheme '{parsed.scheme}' not allowed; use http or https")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    # Check if hostname is a raw IP
    try:
        if _is_private_ip(hostname):
            raise ValueError("URL points to a private/internal IP address")
    except ValueError as e:
        if "private" in str(e).lower() or "internal" in str(e).lower():
            raise
        # hostname is not an IP — resolve it
        pass

    # DNS resolution check
    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in resolved:
            ip_str = sockaddr[0]
            if _is_private_ip(ip_str):
                raise ValueError(
                    f"URL hostname '{hostname}' resolves to private IP {ip_str}"
                )
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname '{hostname}'")

    return url
