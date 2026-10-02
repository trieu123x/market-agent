from app.core.config import get_settings


async def register_and_login(client, email, password="password123"):
    r = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


async def test_register_login_me(client, unique_email):
    token = await register_and_login(client, unique_email)
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == unique_email
    assert body["role"] == "USER"
    assert "hashed_password" not in body


async def test_duplicate_email_conflict(client, unique_email):
    await register_and_login(client, unique_email)
    r = await client.post("/api/v1/auth/register", json={"email": unique_email, "password": "password123"})
    assert r.status_code == 409


async def test_wrong_password_rejected(client, unique_email):
    await register_and_login(client, unique_email)
    r = await client.post("/api/v1/auth/login", json={"email": unique_email, "password": "wrong-password"})
    assert r.status_code == 401


async def test_me_requires_valid_token(client):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


async def test_short_password_validation(client, unique_email):
    r = await client.post("/api/v1/auth/register", json={"email": unique_email, "password": "short"})
    assert r.status_code == 422


async def test_rbac_admin_vs_user(client, unique_email):
    from app.api.deps import require_admin
    from app.main import app

    @app.get("/_admin_probe", dependencies=[__import__("fastapi").Depends(require_admin)])
    async def probe():
        return {"ok": True}

    user_token = await register_and_login(client, unique_email)
    r = await client.get("/_admin_probe", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 403

    s = get_settings()
    r = await client.post("/api/v1/auth/login", json={"email": s.admin_email, "password": s.admin_password})
    assert r.status_code == 200, "chạy scripts/seed.py trước"
    r = await client.get("/_admin_probe", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert r.status_code == 200
