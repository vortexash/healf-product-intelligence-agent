import pytest

from app.models import AppError
from app.navigation.url_parser import extract_url, parse_and_validate


def test_valid_locale_url():
    p = parse_and_validate("https://healf.com/en-uk/products/lmnt-recharge")
    assert p.handle == "lmnt-recharge"
    assert p.locale == "en-uk"


def test_valid_bare_url():
    p = parse_and_validate("https://healf.com/products/some-handle")
    assert p.handle == "some-handle"
    assert p.locale is None


def test_variant_and_selling_plan_preserved():
    p = parse_and_validate("https://healf.com/en-uk/products/h?variant=123&selling_plan=999")
    assert p.variant_id == "123"
    assert p.selling_plan_id == "999"
    assert "variant=123" in p.normalized_url


def test_www_is_allowed():
    p = parse_and_validate("https://www.healf.com/products/h")
    assert p.handle == "h"


@pytest.mark.parametrize(
    "url,code",
    [
        ("http://healf.com/products/h", "INVALID_URL"),  # not https
        ("https://evil.com/products/h", "UNSUPPORTED_HOST"),
        ("https://healf.com/collections/all", "NOT_A_PRODUCT_URL"),
        ("https://healf.com/en-uk/products/", "NOT_A_PRODUCT_URL"),
        ("https://user:pass@healf.com/products/h", "INVALID_URL"),
        ("https://healf.com:8080/products/h", "INVALID_URL"),
        ("https://127.0.0.1/products/h", "UNSUPPORTED_HOST"),
        ("https://localhost/products/h", "UNSUPPORTED_HOST"),
    ],
)
def test_rejections(url, code):
    with pytest.raises(AppError) as e:
        parse_and_validate(url)
    assert e.value.code == code


def test_too_long_url():
    with pytest.raises(AppError):
        parse_and_validate("https://healf.com/products/" + "x" * 3000)


def test_extract_url_from_message():
    msg = "https://healf.com/en-uk/products/abc\n\nDoes it contain Vitamin D?"
    assert extract_url(msg) == "https://healf.com/en-uk/products/abc"


def test_extract_url_none():
    assert extract_url("just a question, no url") is None
