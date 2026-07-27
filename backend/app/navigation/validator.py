"""SSRF host/IP validation (PRD 13.2). Applied before every request + redirect."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from ..models import AppError
from .url_parser import ALLOWED_HOSTS


def _is_blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # unparseable -> block
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def assert_safe_host(url: str) -> None:
    """Validate a URL's host is an allowed Healf host that resolves to a public IP.

    Raises AppError(PRODUCT_FETCH_BLOCKED) on any SSRF-risky target.
    """
    host = (urlparse(url).hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise AppError("PRODUCT_FETCH_BLOCKED", "This host is not permitted.", 400)

    # Resolve and ensure every resolved address is public. Blocks DNS-rebinding
    # to private ranges even for an allowed hostname.
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise AppError("PRODUCT_FETCH_BLOCKED", "Could not resolve the product host.", 400)
    for info in infos:
        ip = info[4][0]
        if _is_blocked_ip(ip):
            raise AppError("PRODUCT_FETCH_BLOCKED", "Refusing to fetch a non-public address.", 400)
