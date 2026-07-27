import httpx
import pytest
import respx

from app.models import AppError
from app.navigation import healf_client


@pytest.fixture(autouse=True)
def allow_host(monkeypatch):
    # Skip real DNS; we only test HTTP behaviour here.
    monkeypatch.setattr("app.navigation.healf_client.assert_safe_host", lambda url: None)


@respx.mock
async def test_fetch_ok():
    respx.get("https://healf.com/products/x").mock(
        return_value=httpx.Response(200, html="<html>ok</html>")
    )
    res = await healf_client.fetch("https://healf.com/products/x")
    assert res.status == 200
    assert "ok" in res.text


@respx.mock
async def test_404_raises_not_found():
    respx.get("https://healf.com/products/x").mock(return_value=httpx.Response(404))
    with pytest.raises(AppError) as e:
        await healf_client.fetch("https://healf.com/products/x")
    assert e.value.code == "PRODUCT_NOT_FOUND"


@respx.mock
async def test_redirect_followed_and_revalidated():
    respx.get("https://healf.com/products/x").mock(
        return_value=httpx.Response(301, headers={"location": "https://healf.com/products/y"})
    )
    respx.get("https://healf.com/products/y").mock(return_value=httpx.Response(200, html="final"))
    res = await healf_client.fetch("https://healf.com/products/x")
    assert "final" in res.text


@respx.mock
async def test_timeout_raises():
    respx.get("https://healf.com/products/x").mock(side_effect=httpx.ConnectTimeout("slow"))
    with pytest.raises(AppError) as e:
        await healf_client.fetch("https://healf.com/products/x")
    assert e.value.code == "PRODUCT_FETCH_TIMEOUT"
