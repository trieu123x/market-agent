import httpx
import pytest

from app.guardrails.anti_ssrf import UnsafeURLError, safe_fetch, validate_url

PUBLIC_IP = "93.184.215.14"


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://example.com/",
        "http://127.0.0.1/",
        "http://localhost/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://0.0.0.0/",
        f"http://{PUBLIC_IP}:22/",
        f"http://user:pass@{PUBLIC_IP}/",
        "http:///nohost",
    ],
)
async def test_rejects_unsafe_urls(url):
    with pytest.raises(UnsafeURLError):
        await validate_url(url)


async def test_accepts_public_ip():
    await validate_url(f"https://{PUBLIC_IP}/page")


async def test_redirect_to_internal_is_blocked():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1:8080/admin"})

    with pytest.raises(UnsafeURLError):
        await safe_fetch(f"http://{PUBLIC_IP}/", 1024, 5, transport=httpx.MockTransport(handler))


async def test_fetch_enforces_size_limit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 2048, headers={"content-type": "text/plain"})

    with pytest.raises(UnsafeURLError):
        await safe_fetch(f"http://{PUBLIC_IP}/", 1024, 5, transport=httpx.MockTransport(handler))


async def test_fetch_ok():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<p>hi</p>", headers={"content-type": "text/html"})

    got = await safe_fetch(f"http://{PUBLIC_IP}/", 1024, 5, transport=httpx.MockTransport(handler))
    assert got.content == b"<p>hi</p>"
    assert got.content_type == "text/html"
