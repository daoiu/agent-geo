"""v0.4 SSRF 守卫：URL 校验拒绝内部 IP（spec §9）。

模式控制（环境变量）：
- `GEO_ENV=development` → 放行 loopback（localhost / 127.0.0.1 / ::1）
- `SSRF_ALLOW_PRIVATE_IPS=1` → 放行 RFC 1918 私有网段（10.x / 172.16-31.x / 192.168.x）
- `SSRF_ALLOW_MULTICAST=1` → 放行 multicast 地址
- 默认（无上述环境变量）= production 严格模式，拒绝所有上述范围

约束：
- 仅允许 http / https scheme
- 'localhost' 字面量在 production 模式被拒
- IP 字面量校验范围根据模式
- 域名 → IP 解析不在此层做（Crawler 调之前再做 DNS 校验是 v0.4.x）
"""
from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset({"http", "https"})


def _is_development_mode() -> bool:
    """True 表示当前是开发模式（放行 loopback）。"""
    return os.environ.get("GEO_ENV", "").lower() == "development"


def _allow_private_ips() -> bool:
    return os.environ.get("SSRF_ALLOW_PRIVATE_IPS", "").lower() in {"1", "true", "yes"}


def _allow_multicast() -> bool:
    return os.environ.get("SSRF_ALLOW_MULTICAST", "").lower() in {"1", "true", "yes"}


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True 表示该 IP 在当前模式下应被阻止。"""
    # loopback：dev 模式放行，prod 模式阻止
    if ip.is_loopback:
        return not _is_development_mode()
    # link-local（169.254.x / fe80::）总是阻止（AWS metadata 等敏感场景）
    if ip.is_link_local:
        return True
    # unspecified（0.0.0.0 / ::）总是阻止
    if ip.is_unspecified:
        return True
    # multicast：默认阻止，显式开关可放行
    if ip.is_multicast:
        return not _allow_multicast()
    # private（RFC 1918）：默认阻止，显式开关可放行
    if ip.is_private:
        return not _allow_private_ips()
    # reserved
    if ip.is_reserved:
        return True
    return False


def validate_url_for_ssrf(url: str) -> None:
    """校验 URL 不构成 SSRF 风险（按环境变量策略）。

    Raises:
        ValueError: URL 不合法、scheme 不允许、host 是内部 IP/localhost（按当前模式）。
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValueError(f"invalid URL: {e}") from e

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"URL scheme {parsed.scheme!r} not allowed; "
            f"expected one of {sorted(_ALLOWED_SCHEMES)}"
        )

    host = parsed.hostname
    if not host:
        raise ValueError("URL has no host")

    # 1. 'localhost' 字面量（dev 模式放行，prod 模式拒绝）
    if host.lower() == "localhost":
        if not _is_development_mode():
            raise ValueError(f"SSRF blocked: {host!r} is a local hostname")
        return

    # 2. IP 字面量校验
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # 是域名，本层不做 DNS 解析（Crawler 之前会再做）
        return

    if _is_blocked_ip(ip):
        mode = "development" if _is_development_mode() else "production"
        raise ValueError(
            f"SSRF blocked: {host!r} is an internal IP address "
            f"(mode={mode})"
        )