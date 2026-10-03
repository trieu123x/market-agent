"""Anti-SSRF: chỉ cho phép tải URL http(s) công khai.

Mỗi hop (kể cả redirect) đều được resolve DNS và kiểm tra lại toàn bộ IP trả về,
nên redirect sang 127.0.0.1 / 169.254.169.254 / mạng nội bộ đều bị chặn.
Rủi ro còn lại: DNS rebinding giữa lúc kiểm tra và lúc httpx kết nối (TOCTOU) –
chấp nhận ở mức MVP.
"""
import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443, 8080, 8443}
MAX_REDIRECTS = 5
MAX_URL_LENGTH = 500


class UnsafeURLError(ValueError):
    pass


@dataclass
class FetchedContent:
    url: str
    content: bytes
    content_type: str


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def _parse(url: str) -> tuple[str, int]:
    if len(url) > MAX_URL_LENGTH:
        raise UnsafeURLError("URL quá dài")
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Chỉ hỗ trợ http/https")
    if parts.username or parts.password:
        raise UnsafeURLError("URL không được chứa thông tin đăng nhập")
    if not parts.hostname:
        raise UnsafeURLError("URL thiếu hostname")
    try:
        port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    except ValueError:
        raise UnsafeURLError("Port không hợp lệ")
    if port not in ALLOWED_PORTS:
        raise UnsafeURLError(f"Port {port} không được phép")
    return parts.hostname, port


async def validate_url(url: str) -> None:
    """Raise UnsafeURLError nếu URL không an toàn để server tự tải về."""
    host, port = _parse(url)
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        ips = [literal]
    else:
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror:
            raise UnsafeURLError("Không resolve được hostname")
        ips = [ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos]
    if not ips or not all(_is_public_ip(ip) for ip in ips):
        raise UnsafeURLError("URL trỏ tới địa chỉ nội bộ hoặc không công khai")


async def safe_fetch(
    url: str, max_bytes: int, timeout: float, transport: httpx.AsyncBaseTransport | None = None
) -> FetchedContent:
    async with httpx.AsyncClient(follow_redirects=False, timeout=timeout, transport=transport) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await validate_url(url)
            async with client.stream("GET", url, headers={"User-Agent": "MarketAgentBot/0.1"}) as resp:
                if resp.is_redirect:
                    url = urljoin(url, resp.headers["location"])
                    continue
                resp.raise_for_status()
                if int(resp.headers.get("content-length") or 0) > max_bytes:
                    raise UnsafeURLError("Nội dung vượt quá giới hạn dung lượng")
                buf = bytearray()
                async for part in resp.aiter_bytes():
                    buf += part
                    if len(buf) > max_bytes:
                        raise UnsafeURLError("Nội dung vượt quá giới hạn dung lượng")
                return FetchedContent(url=url, content=bytes(buf), content_type=resp.headers.get("content-type", ""))
    raise UnsafeURLError("Quá nhiều redirect")
