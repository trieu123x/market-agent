import asyncio
import uuid

import pymupdf
import pytest

from app.core.config import get_settings


async def _token(client, email, password="password123"):
    r = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _admin(client):
    s = get_settings()
    r = await client.post("/api/v1/auth/login", json={"email": s.admin_email, "password": s.admin_password})
    assert r.status_code == 200, "chạy scripts/seed.py trước"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _new_email() -> str:
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


def _pdf(paragraphs: list[str]) -> bytes:
    doc = pymupdf.open()
    for p in paragraphs:
        doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 770), p, fontsize=10)
    return doc.tobytes()


async def _wait_ready(client, headers, doc_id, timeout=60):
    for _ in range(int(timeout / 0.25)):
        r = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
        assert r.status_code == 200, r.text
        if r.json()["processing_status"] in ("READY", "FAILED"):
            return r.json()
        await asyncio.sleep(0.25)
    pytest.fail("document không READY kịp")


async def _search(client, headers, query, top_k=4):
    r = await client.post("/api/v1/documents/search", headers=headers, json={"query": query, "top_k": top_k})
    assert r.status_code == 200, r.text
    return r.json()["results"]


async def test_pdf_upload_ready_and_private_scope_isolation(client):
    user_a, user_b = await _token(client, _new_email()), await _token(client, _new_email())
    marker = f"zq{uuid.uuid4().hex[:10]}"
    filler = "Coffee brand storytelling for social media campaigns. " * 60
    pdf = _pdf([filler, f"The flagship product {marker} launches in December with a 20 percent discount.", filler])

    r = await client.post(
        "/api/v1/documents/upload", headers=user_a, files={"file": ("brand guide.pdf", pdf, "application/pdf")}
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["file_type"] == "PDF" and body["scope"] == "PRIVATE" and body["file_size_bytes"] == len(pdf)

    doc = await _wait_ready(client, user_a, body["document_id"])
    assert doc["processing_status"] == "READY", doc["error_message"]
    assert doc["chunk_count"] >= 2

    hits = await _search(client, user_a, f"when does {marker} launch")
    assert hits and hits[0]["document_id"] == body["document_id"]
    assert marker in hits[0]["content"]
    assert set(hits[0]["ranks"]) == {"vector", "fts"}
    assert len(await _search(client, user_a, "coffee storytelling", top_k=15)) <= 15

    # User B không thấy tài liệu PRIVATE của user A
    assert all(h["document_id"] != body["document_id"] for h in await _search(client, user_b, marker, top_k=15))
    assert (await client.get(f"/api/v1/documents/{body['document_id']}", headers=user_b)).status_code == 404
    listed = (await client.get("/api/v1/documents", headers=user_b)).json()
    assert body["document_id"] not in {d["id"] for d in listed}


async def test_system_doc_visible_to_all_and_admin_delete(client):
    admin, user = await _admin(client), await _token(client, _new_email())
    marker = f"sys{uuid.uuid4().hex[:10]}"
    r = await client.post(
        "/api/v1/documents/upload",
        headers=admin,
        data={"scope": "SYSTEM"},
        files={"file": ("policy.txt", f"# Chính sách\n\nTừ khóa {marker} là bắt buộc.".encode(), "text/plain")},
    )
    assert r.status_code == 202, r.text
    doc_id = r.json()["document_id"]
    assert (await _wait_ready(client, admin, doc_id))["processing_status"] == "READY"

    hits = await _search(client, user, marker)
    assert hits and hits[0]["document_id"] == doc_id

    assert (await client.delete(f"/api/v1/admin/documents/{doc_id}", headers=user)).status_code == 403
    assert (await client.delete(f"/api/v1/admin/documents/{doc_id}", headers=admin)).status_code == 204
    assert (await client.delete(f"/api/v1/admin/documents/{doc_id}", headers=admin)).status_code == 404
    assert all(h["document_id"] != doc_id for h in await _search(client, user, marker))


async def test_admin_can_delete_users_private_doc(client):
    admin, user = await _admin(client), await _token(client, _new_email())
    r = await client.post("/api/v1/documents/upload", headers=user, files={"file": ("a.txt", b"private note", "text/plain")})
    doc_id = r.json()["document_id"]
    await _wait_ready(client, user, doc_id)
    assert (await client.delete(f"/api/v1/admin/documents/{doc_id}", headers=admin)).status_code == 204
    assert (await client.get(f"/api/v1/documents/{doc_id}", headers=user)).status_code == 404


async def test_upload_validation(client):
    user = await _token(client, _new_email())
    url = "/api/v1/documents/upload"

    r = await client.post(url, headers=user, data={"scope": "SYSTEM"}, files={"file": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 403

    big = b"a" * (get_settings().max_upload_bytes + 1)
    assert (await client.post(url, headers=user, files={"file": ("big.txt", big, "text/plain")})).status_code == 413

    r = await client.post(url, headers=user, files={"file": ("x.exe", b"MZ...", "application/octet-stream")})
    assert r.status_code == 415
    r = await client.post(url, headers=user, files={"file": ("fake.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 415

    assert (await client.post(url, headers=user, data={"scope": "PRIVATE"})).status_code == 400
    r = await client.post(
        url, headers=user, data={"url": "https://example.com"}, files={"file": ("a.txt", b"x", "text/plain")}
    )
    assert r.status_code == 400

    for bad in ["http://127.0.0.1:8080/", "http://169.254.169.254/latest/meta-data/", "file:///etc/passwd"]:
        r = await client.post(url, headers=user, data={"url": bad})
        assert r.status_code == 400, bad

    assert (await client.post(url, files={"file": ("a.txt", b"x", "text/plain")})).status_code == 401
