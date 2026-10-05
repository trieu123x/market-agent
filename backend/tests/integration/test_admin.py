import uuid
from datetime import date, timedelta

from helpers import admin_headers, chat, new_thread_id, of, register_and_login, resume


async def _me(client, headers) -> dict:
    return (await client.get("/api/v1/auth/me", headers=headers)).json()


async def test_admin_endpoints_require_admin(client):
    user = await register_and_login(client)
    for method, path in [
        ("GET", "/api/v1/admin/users"),
        ("PATCH", f"/api/v1/admin/users/{uuid.uuid4()}/status"),
        ("GET", "/api/v1/admin/pricing"),
        ("PUT", "/api/v1/admin/pricing/gpt-4o"),
        ("GET", "/api/v1/admin/analytics/costs"),
    ]:
        assert (await client.request(method, path, headers=user, json={})).status_code == 403, path
        assert (await client.request(method, path, json={})).status_code == 401, path


async def test_user_status_toggle(client):
    admin = await admin_headers(client)
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    user = await register_and_login(client, email)
    user_id = (await _me(client, user))["id"]
    assert user_id in {u["id"] for u in (await client.get("/api/v1/admin/users", headers=admin)).json()}

    r = await client.patch(f"/api/v1/admin/users/{user_id}/status", headers=admin, json={"is_active": False})
    assert r.status_code == 200
    assert r.json() == {"user_id": user_id, "is_active": False, "message": "User status updated successfully"}
    # Token cũ bị từ chối ngay, đăng nhập lại cũng không được
    assert (await client.get("/api/v1/auth/me", headers=user)).status_code == 403
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 403

    r = await client.patch(f"/api/v1/admin/users/{user_id}/status", headers=admin, json={"is_active": True})
    assert r.status_code == 200 and (await client.get("/api/v1/auth/me", headers=user)).status_code == 200

    admin_id = (await _me(client, admin))["id"]
    r = await client.patch(f"/api/v1/admin/users/{admin_id}/status", headers=admin, json={"is_active": False})
    assert r.status_code == 400
    r = await client.patch(f"/api/v1/admin/users/{uuid.uuid4()}/status", headers=admin, json={"is_active": False})
    assert r.status_code == 404


async def test_pricing_crud_and_single_default(client):
    admin = await admin_headers(client)
    url = "/api/v1/admin/pricing"
    original_default = next(p["model_id"] for p in (await client.get(url, headers=admin)).json() if p["is_default"])
    model = f"gemini-zztest-{uuid.uuid4().hex[:6]}"

    # Model chưa có: thiếu thông tin → 404, sai provider → 400, đủ → 201
    assert (await client.put(f"{url}/{model}", headers=admin, json={"is_system_active": True})).status_code == 404
    body = {"provider": "openai", "input_price_per_1k": "0.001", "output_price_per_1k": "0.002"}
    assert (await client.put(f"{url}/{model}", headers=admin, json=body)).status_code == 400
    r = await client.put(f"{url}/{model}", headers=admin, json={**body, "provider": "google"})
    assert r.status_code == 201
    assert r.json()["input_price_per_1k"] == 0.001 and r.json()["is_default"] is False

    r = await client.put(f"{url}/{model}", headers=admin, json={"output_price_per_1k": "0.003"})
    assert r.status_code == 200 and r.json()["output_price_per_1k"] == 0.003 and r.json()["input_price_per_1k"] == 0.001
    assert (await client.put(f"{url}/{model}", headers=admin, json={"input_price_per_1k": "-1"})).status_code == 422

    try:
        r = await client.put(f"{url}/{model}", headers=admin, json={"is_default": True})
        assert r.status_code == 200
        defaults = [p["model_id"] for p in (await client.get(url, headers=admin)).json() if p["is_default"]]
        assert defaults == [model]
        # Không được tắt model mặc định hay bỏ cờ mặc định trực tiếp
        assert (await client.put(f"{url}/{model}", headers=admin, json={"is_system_active": False})).status_code == 400
        assert (await client.put(f"{url}/{model}", headers=admin, json={"is_default": False})).status_code == 400
    finally:
        r = await client.put(f"{url}/{original_default}", headers=admin, json={"is_default": True})
        assert r.status_code == 200
    defaults = [p["model_id"] for p in (await client.get(url, headers=admin)).json() if p["is_default"]]
    assert defaults == [original_default]

    # Model bị tắt thì không chat được
    assert (await client.put(f"{url}/{model}", headers=admin, json={"is_system_active": False})).status_code == 200
    user = await register_and_login(client)
    r = await client.post("/api/v1/agent/chat/stream", headers=user, json={"message": "hi", "model_id": model})
    assert r.status_code == 400


async def test_cost_analytics_matches_streamed_costs(client, fake_llm):
    admin, user = await admin_headers(client), await register_and_login(client)
    user_id = (await _me(client, user))["id"]
    tid = new_thread_id()
    costs = of(await chat(client, user, tid), "cost_update") + of(await resume(client, user, tid, "APPROVE"), "cost_update")

    r = await client.get("/api/v1/admin/analytics/costs", headers=admin, params={"user_id": user_id})
    assert r.status_code == 200
    report = r.json()
    assert report["total_tokens_consumed"] == sum(c["tokens"] for c in costs)
    assert abs(report["total_cost_usd"] - sum(c["cost_usd"] for c in costs)) < 1e-9
    by_node = {b["node_name"]: b["tokens"] for b in report["breakdown_by_node"]}
    assert set(by_node) == {"generate_outline", "multi_format_generator", "fact_checker"}
    assert by_node["multi_format_generator"] == sum(c["tokens"] for c in costs if c["node"] == "multi_format_generator")
    assert [b["model_id"] for b in report["breakdown_by_model"]] == [costs[0]["model_id"]]
    assert report["breakdown_by_user"] == [
        {"user_id": user_id, "tokens": report["total_tokens_consumed"], "cost_usd": report["total_cost_usd"]}
    ]

    today = date.today()
    params = {"user_id": user_id, "start_date": str(today), "end_date": str(today)}
    assert (await client.get("/api/v1/admin/analytics/costs", headers=admin, params=params)).json() == report
    params = {"user_id": user_id, "end_date": str(today - timedelta(days=1))}
    assert (await client.get("/api/v1/admin/analytics/costs", headers=admin, params=params)).json()[
        "total_tokens_consumed"
    ] == 0
    params = {"user_id": user_id, "model_id": "no-such-model"}
    assert (await client.get("/api/v1/admin/analytics/costs", headers=admin, params=params)).json()[
        "total_cost_usd"
    ] == 0
    params = {"start_date": str(today), "end_date": str(today - timedelta(days=1))}
    assert (await client.get("/api/v1/admin/analytics/costs", headers=admin, params=params)).status_code == 400
