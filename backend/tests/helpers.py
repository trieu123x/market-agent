import json
import uuid

from app.core.config import get_settings


async def register_and_login(client, email=None, password="password123") -> dict:
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def admin_headers(client) -> dict:
    s = get_settings()
    r = await client.post("/api/v1/auth/login", json={"email": s.admin_email, "password": s.admin_password})
    assert r.status_code == 200, "chạy scripts/seed.py trước"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def new_thread_id() -> str:
    return f"test-{uuid.uuid4().hex[:12]}"


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


async def post_sse(client, path, headers, payload) -> list[tuple[str, dict]]:
    r = await client.post(path, headers={**headers, "Accept": "text/event-stream"}, json=payload)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    return parse_sse(r.text)


async def chat(client, headers, thread_id, message="Lên chiến dịch đa kênh cho giải pháp FinTech mới", **extra):
    payload = {"thread_id": thread_id, "message": message, **extra}
    return await post_sse(client, "/api/v1/agent/chat/stream", headers, payload)


async def resume(client, headers, thread_id, action, stage="OUTLINE_APPROVAL", **extra):
    payload = {"thread_id": thread_id, "stage": stage, "action": action, **extra}
    return await post_sse(client, "/api/v1/agent/chat/resume", headers, payload)


def of(events, kind) -> list[dict]:
    return [d for e, d in events if e == kind]


def steps(events) -> list[str]:
    return [d["step"] for d in of(events, "status")]
