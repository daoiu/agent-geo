"""Tests for SSRF URL validator (v0.4 spec §9)."""
from __future__ import annotations

import pytest

from app.domain.security.ssrf import validate_url_for_ssrf


# 默认模式（production）：无 GEO_ENV 环境变量
# 测试间需要重置环境变量以避免污染


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """清空 SSRF 相关环境变量，确保测试用 production 默认。"""
    monkeypatch.delenv("GEO_ENV", raising=False)
    monkeypatch.delenv("SSRF_ALLOW_PRIVATE_IPS", raising=False)
    monkeypatch.delenv("SSRF_ALLOW_MULTICAST", raising=False)


# ---------------------------------------------------------------------------
# Production 模式（默认）
# ---------------------------------------------------------------------------


def test_accepts_public_https_url() -> None:
    """公网域名 https URL 通过校验。"""
    validate_url_for_ssrf("https://www.mi.com")  # 不抛


def test_accepts_public_ip() -> None:
    """公网 IP 字面量通过校验。"""
    validate_url_for_ssrf("https://8.8.8.8")  # Google DNS, 不抛


def test_blocks_loopback_ipv4() -> None:
    """127.0.0.1 拒绝。"""
    with pytest.raises(ValueError, match="[Ss]SRF"):
        validate_url_for_ssrf("http://127.0.0.1/admin")


def test_blocks_private_10_x() -> None:
    """10.x 私有网段拒绝。"""
    with pytest.raises(ValueError, match="[Ss]SRF"):
        validate_url_for_ssrf("http://10.0.0.1/internal")


def test_blocks_private_172_16() -> None:
    """172.16.x 私有网段拒绝。"""
    with pytest.raises(ValueError, match="[Ss]SRF"):
        validate_url_for_ssrf("http://172.16.5.5/internal")


def test_blocks_private_192_168() -> None:
    """192.168.x 私有网段拒绝。"""
    with pytest.raises(ValueError, match="[Ss]SRF"):
        validate_url_for_ssrf("http://192.168.1.1/router")


def test_blocks_link_local_169_254() -> None:
    """169.254.x link-local 拒绝（即使开发模式也阻止，AWS metadata 风险）。"""
    with pytest.raises(ValueError, match="[Ss]SRF"):
        validate_url_for_ssrf("http://169.254.169.254/latest/meta-data/")


def test_blocks_loopback_ipv6() -> None:
    """::1 loopback IPv6 拒绝。"""
    with pytest.raises(ValueError, match="[Ss]SRF"):
        validate_url_for_ssrf("http://[::1]/admin")


def test_blocks_link_local_ipv6() -> None:
    """fe80:: link-local IPv6 拒绝。"""
    with pytest.raises(ValueError, match="[Ss]SRF"):
        validate_url_for_ssrf("http://[fe80::1]/admin")


def test_blocks_multicast() -> None:
    """224.0.0.0 multicast 拒绝。"""
    with pytest.raises(ValueError, match="[Ss]SRF"):
        validate_url_for_ssrf("http://224.0.0.1/")


def test_blocks_localhost_hostname() -> None:
    """'localhost' 字面量拒绝。"""
    with pytest.raises(ValueError, match="[Ss]SRF"):
        validate_url_for_ssrf("http://localhost/")


def test_blocks_invalid_scheme() -> None:
    """非 http/https scheme 拒绝。"""
    with pytest.raises(ValueError, match="scheme"):
        validate_url_for_ssrf("file:///etc/passwd")


def test_blocks_invalid_scheme_ftp() -> None:
    """ftp scheme 拒绝。"""
    with pytest.raises(ValueError, match="scheme"):
        validate_url_for_ssrf("ftp://example.com/")


def test_blocks_malformed_url() -> None:
    """格式错误的 URL 拒绝。"""
    with pytest.raises(ValueError):
        validate_url_for_ssrf("not a url")


def test_accepts_http_public() -> None:
    """http + 公网域名通过。"""
    validate_url_for_ssrf("http://example.com/")  # 不抛


def test_accepts_url_with_port() -> None:
    """带端口的 URL 正确解析 host。"""
    validate_url_for_ssrf("https://example.com:8443/path")  # 不抛


def test_accepts_subdomain() -> None:
    """子域名也通过（域名解析不在此层做）。"""
    validate_url_for_ssrf("https://api.mi.com/v1")  # 不抛


# ---------------------------------------------------------------------------
# Development 模式（GEO_ENV=development 放行 loopback）
# ---------------------------------------------------------------------------


def test_dev_mode_allows_loopback_ipv4(monkeypatch: pytest.MonkeyPatch) -> None:
    """开发模式放行 127.0.0.1。"""
    monkeypatch.setenv("GEO_ENV", "development")
    validate_url_for_ssrf("http://127.0.0.1:3000/")  # 不抛


def test_dev_mode_allows_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    """开发模式放行 localhost 主机名。"""
    monkeypatch.setenv("GEO_ENV", "development")
    validate_url_for_ssrf("http://localhost:8000/")  # 不抛


def test_dev_mode_still_blocks_private_ips(monkeypatch: pytest.MonkeyPatch) -> None:
    """开发模式不自动放行 10.x / 192.168.x（避免安全漂移）。"""
    monkeypatch.setenv("GEO_ENV", "development")
    with pytest.raises(ValueError, match="[Ss]SRF"):
        validate_url_for_ssrf("http://192.168.1.1/")


def test_dev_mode_still_blocks_link_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """开发模式仍阻止 link-local（169.254.x，AWS metadata 风险）。"""
    monkeypatch.setenv("GEO_ENV", "development")
    with pytest.raises(ValueError, match="[Ss]SRF"):
        validate_url_for_ssrf("http://169.254.169.254/latest/")


# ---------------------------------------------------------------------------
# 显式环境变量覆盖
# ---------------------------------------------------------------------------


def test_allow_private_ips_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """SSRF_ALLOW_PRIVATE_IPS=1 放行 10.x / 192.168.x。"""
    monkeypatch.setenv("SSRF_ALLOW_PRIVATE_IPS", "1")
    validate_url_for_ssrf("http://10.0.0.1/internal")  # 不抛
    validate_url_for_ssrf("http://192.168.1.1/")  # 不抛


def test_allow_multicast_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """SSRF_ALLOW_MULTICAST=1 放行 multicast。"""
    monkeypatch.setenv("SSRF_ALLOW_MULTICAST", "1")
    validate_url_for_ssrf("http://224.0.0.1/")  # 不抛


def test_no_env_override_still_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认值（不是 '1' / 'true' / 'yes'）仍阻止。"""
    monkeypatch.setenv("SSRF_ALLOW_PRIVATE_IPS", "true")  # 'true' 也算放行
    validate_url_for_ssrf("http://10.0.0.1/")  # 不抛
    monkeypatch.setenv("SSRF_ALLOW_PRIVATE_IPS", "0")  # '0' 不放行
    with pytest.raises(ValueError, match="[Ss]SRF"):
        validate_url_for_ssrf("http://10.0.0.1/")