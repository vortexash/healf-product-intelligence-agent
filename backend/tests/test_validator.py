import pytest

from app.models import AppError
from app.navigation.validator import _is_blocked_ip, assert_safe_host


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "192.168.1.5", "169.254.1.1", "::1", "0.0.0.0", "224.0.0.1"])
def test_private_ips_blocked(ip):
    assert _is_blocked_ip(ip) is True


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34"])
def test_public_ips_allowed(ip):
    assert _is_blocked_ip(ip) is False


def test_non_healf_host_blocked():
    with pytest.raises(AppError) as e:
        assert_safe_host("https://example.com/products/x")
    assert e.value.code == "PRODUCT_FETCH_BLOCKED"
