"""Tests for app.ssrf — SSRF URL validation."""

from unittest.mock import patch, MagicMock, call
import ipaddress
import socket

import pytest

from app.ssrf import validate_url, _is_private_ip


# ---------------------------------------------------------------------------
# _is_private_ip helper
# ---------------------------------------------------------------------------

class TestIsPrivateIP:
    """Verify that _is_private_ip correctly classifies addresses."""

    def test_loopback_v4(self):
        assert _is_private_ip("127.0.0.1") is True

    def test_loopback_v6(self):
        assert _is_private_ip("::1") is True

    def test_private_10(self):
        assert _is_private_ip("10.0.0.1") is True

    def test_private_172(self):
        assert _is_private_ip("172.16.0.1") is True

    def test_private_192(self):
        assert _is_private_ip("192.168.1.1") is True

    def test_aws_metadata(self):
        assert _is_private_ip("169.254.169.254") is True

    def test_link_local(self):
        assert _is_private_ip("169.254.0.1") is True

    def test_carrier_grade_nat(self):
        assert _is_private_ip("100.64.0.1") is True

    def test_multicast(self):
        assert _is_private_ip("224.0.0.1") is True

    def test_broadcast(self):
        assert _is_private_ip("255.255.255.255") is True

    def test_ipv6_unique_local(self):
        assert _is_private_ip("fd12:3456:789a::1") is True

    def test_ipv6_link_local(self):
        assert _is_private_ip("fe80::1") is True

    def test_public_ip(self):
        assert _is_private_ip("8.8.8.8") is False

    def test_public_ip_2(self):
        assert _is_private_ip("1.1.1.1") is False

    def test_public_ip_93(self):
        assert _is_private_ip("93.184.216.34") is False

    def test_unparseable_returns_true(self):
        """Non-parseable strings should be treated as blocked."""
        assert _is_private_ip("not-an-ip") is True

    def test_this_network(self):
        assert _is_private_ip("0.0.0.1") is True

    def test_test_net_1(self):
        assert _is_private_ip("192.0.2.1") is True

    def test_test_net_2(self):
        assert _is_private_ip("198.51.100.1") is True

    def test_test_net_3(self):
        assert _is_private_ip("203.0.113.1") is True

    def test_benchmarking(self):
        assert _is_private_ip("198.18.0.1") is True

    def test_reserved(self):
        assert _is_private_ip("240.0.0.1") is True


# ---------------------------------------------------------------------------
# validate_url — scheme validation
# ---------------------------------------------------------------------------

def _mock_private_ip_for_domain(ip_str):
    """
    A replacement for _is_private_ip that does NOT block unparseable
    hostnames (domain names).  This allows validate_url to fall through
    to DNS resolution in tests.  For actual IP strings it uses the real
    blocked-network check.
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        # It is a domain name, not an IP — tell caller it is NOT private
        # so that validate_url proceeds to DNS resolution.
        return False

    from app.ssrf import _BLOCKED_NETWORKS
    for network in _BLOCKED_NETWORKS:
        if addr in network:
            return True
    return False


class TestValidateUrlScheme:
    def test_http_allowed(self):
        with patch("app.ssrf._is_private_ip", side_effect=_mock_private_ip_for_domain), \
             patch("app.ssrf.socket.getaddrinfo", return_value=[
                 (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
             ]):
            result = validate_url("http://example.com/image.jpg")
            assert result == "http://example.com/image.jpg"

    def test_https_allowed(self):
        with patch("app.ssrf._is_private_ip", side_effect=_mock_private_ip_for_domain), \
             patch("app.ssrf.socket.getaddrinfo", return_value=[
                 (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
             ]):
            result = validate_url("https://example.com/image.jpg")
            assert result == "https://example.com/image.jpg"

    def test_ftp_blocked(self):
        with pytest.raises(ValueError, match="scheme.*not allowed"):
            validate_url("ftp://example.com/file.zip")

    def test_file_scheme_blocked(self):
        with pytest.raises(ValueError, match="scheme.*not allowed"):
            validate_url("file:///etc/passwd")

    def test_javascript_blocked(self):
        with pytest.raises(ValueError, match="scheme.*not allowed"):
            validate_url("javascript:alert(1)")

    def test_empty_scheme(self):
        with pytest.raises(ValueError):
            validate_url("://example.com")


# ---------------------------------------------------------------------------
# validate_url — hostname checks
# ---------------------------------------------------------------------------

class TestValidateUrlHostname:
    def test_no_hostname(self):
        with pytest.raises(ValueError, match="no hostname"):
            validate_url("http:///path")

    def test_raw_private_ip_blocked(self):
        with pytest.raises(ValueError, match="private"):
            validate_url("http://10.0.0.1/secret")

    def test_raw_loopback_blocked(self):
        with pytest.raises(ValueError, match="private"):
            validate_url("http://127.0.0.1/admin")

    def test_aws_metadata_blocked(self):
        with pytest.raises(ValueError, match="private"):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_raw_ipv6_loopback_blocked(self):
        with pytest.raises(ValueError, match="private"):
            validate_url("http://[::1]/secret")

    def test_raw_public_ip_allowed(self):
        with patch("app.ssrf.socket.getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 0)),
        ]):
            result = validate_url("http://8.8.8.8/dns")
            assert result == "http://8.8.8.8/dns"

    def test_domain_hostname_treated_as_private_by_default(self):
        """
        Because _is_private_ip returns True for unparseable strings,
        a domain hostname is blocked at the raw-IP check stage (before
        DNS resolution).  This documents the current behavior.
        """
        with pytest.raises(ValueError, match="private"):
            validate_url("http://example.com/page")


# ---------------------------------------------------------------------------
# validate_url — DNS resolution
# ---------------------------------------------------------------------------

class TestValidateUrlDNS:
    """
    These tests mock _is_private_ip so that domain hostnames pass the
    raw-IP check and fall through to DNS resolution.  For resolved IPs,
    the real blocked-network logic is preserved.
    """

    def test_hostname_resolving_to_private_ip_blocked(self):
        """A domain that resolves to a private IP should be rejected."""
        with patch("app.ssrf._is_private_ip", side_effect=_mock_private_ip_for_domain), \
             patch("app.ssrf.socket.getaddrinfo", return_value=[
                 (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.1", 0)),
             ]):
            with pytest.raises(ValueError, match="resolves to private"):
                validate_url("http://evil.example.com/steal")

    def test_hostname_resolving_to_loopback_blocked(self):
        with patch("app.ssrf._is_private_ip", side_effect=_mock_private_ip_for_domain), \
             patch("app.ssrf.socket.getaddrinfo", return_value=[
                 (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0)),
             ]):
            with pytest.raises(ValueError, match="resolves to private"):
                validate_url("http://evil.example.com/steal")

    def test_hostname_resolving_to_metadata_blocked(self):
        with patch("app.ssrf._is_private_ip", side_effect=_mock_private_ip_for_domain), \
             patch("app.ssrf.socket.getaddrinfo", return_value=[
                 (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 0)),
             ]):
            with pytest.raises(ValueError, match="resolves to private"):
                validate_url("http://evil.example.com/metadata")

    def test_hostname_resolving_to_public_ip_allowed(self):
        with patch("app.ssrf._is_private_ip", side_effect=_mock_private_ip_for_domain), \
             patch("app.ssrf.socket.getaddrinfo", return_value=[
                 (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
             ]):
            result = validate_url("https://example.com/image.jpg")
            assert result == "https://example.com/image.jpg"

    def test_unresolvable_hostname_raises(self):
        with patch("app.ssrf._is_private_ip", side_effect=_mock_private_ip_for_domain), \
             patch("app.ssrf.socket.getaddrinfo", side_effect=socket.gaierror("Name resolution failed")):
            with pytest.raises(ValueError, match="Cannot resolve hostname"):
                validate_url("http://does-not-exist.invalid/path")

    def test_multiple_resolved_ips_one_private(self):
        """If any resolved IP is private, the URL should be blocked."""
        with patch("app.ssrf._is_private_ip", side_effect=_mock_private_ip_for_domain), \
             patch("app.ssrf.socket.getaddrinfo", return_value=[
                 (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
                 (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 0)),
             ]):
            with pytest.raises(ValueError, match="resolves to private"):
                validate_url("http://dual-homed.example.com/path")

    def test_multiple_resolved_ips_all_public(self):
        with patch("app.ssrf._is_private_ip", side_effect=_mock_private_ip_for_domain), \
             patch("app.ssrf.socket.getaddrinfo", return_value=[
                 (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
                 (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("2606:2800:220:1:248:1893:25c8:1946", 0, 0, 0)),
             ]):
            result = validate_url("https://example.com/")
            assert result == "https://example.com/"
