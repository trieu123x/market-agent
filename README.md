# Marketing Agent

Agent AI lên chiến dịch truyền thông đa kênh có người duyệt (human-in-the-loop):

```
brief → guardrail → RAG → dàn ý → [HITL 1: duyệt / sửa / từ chối]
      → bản thảo Facebook · Instagram · Threads → fact-check ⇄ tự sửa (≤ 2 vòng)
      → [HITL 2: duyệt / sửa] → lưu bản cuối + log chi phí
```

- **Backend** (`backend/`): FastAPI, LangGraph (checkpoint Postgres), SSE, pgvector RAG, Taskiq worker.
- **Frontend** (`frontend/`): Next.js 16, chat stream qua `@microsoft/fetch-event-source`, modal duyệt dàn ý, màn duyệt bản thảo 3 tab + báo cáo fact-check, thanh chi phí realtime, trang tài liệu RAG, Admin (người dùng, bảng giá, chi phí).
- Spec: [docs/spec_marketing_agent.md](docs/spec_marketing_agent.md) · Kế hoạch: [docs/PLAN_5_DAYS.md](docs/PLAN_5_DAYS.md)

## Cổng mặc định

Chọn lệch cổng chuẩn để không đụng các stack khác trên máy.

| Dịch vụ    | Host port | Ghi chú                          |
|------------|-----------|----------------------------------|
| Frontend   | 3010      | http://localhost:3010            |
| Backend    | 8010      | http://localhost:8010/docs       |
| Postgres   | 5434      | pgvector/pgvector:pg16           |
| Redis      | 6380      | broker Taskiq + rate limit       |

## Chạy nhanh bằng Docker

Cần Docker và ít nhất một API key LLM (mặc định dùng Gemini – `GOOGLE_API_KEY`, key này cũng dùng cho embedding).

```bash
cp backend/.env.example backend/.env
# sửa backend/.env: GOOGLE_API_KEY=..., JWT_SECRET=<chuỗi ngẫu nhiên dài>

docker compose -f infra/docker-compose.yml --profile full up -d --build
```

Container `api` tự chạy `alembic upgrade head` và `scripts/seed.py` (admin mặc định + bảng giá model) trước khi khởi động.

Mở http://localhost:3010, đăng nhập admin `admin@example.com` / `admin12345` (đổi qua `ADMIN_EMAIL` / `ADMIN_PASSWORD` trước lần seed đầu) hoặc đăng ký tài khoản mới.

Không có profile `full`, compose chỉ chạy Postgres + Redis (dùng cho chế độ dev bên dưới).

## Chạy dev (không Docker cho app)

**1. Hạ tầng**

```bash
docker compose -f infra/docker-compose.yml up -d     # Postgres + Redis
```

**2. Backend** (Python ≥ 3.11; OCR ảnh trong PDF cần `tesseract-ocr` + `tesseract-ocr-vie`, có thể tắt bằng `OCR_ENABLED=false`)

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env              # điền API key
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload --port 8010
```

Worker xử lý tài liệu upload (terminal khác):

```bash
cd backend && . .venv/bin/activate
taskiq worker app.workers.broker:broker app.workers.tasks
```

Không muốn chạy worker/Redis: đặt `TASK_BROKER=memory` (ingest chạy ngay trong process API) và `RATE_LIMIT_BACKEND=memory`.

**3. Frontend** (Node ≥ 20)

```bash
cd frontend
cp .env.example .env.local        # NEXT_PUBLIC_API_URL=http://localhost:8010
npm install
npm run dev                       # http://localhost:3010
```

Frontend gọi thẳng backend từ trình duyệt, nên origin của frontend phải nằm trong `CORS_ORIGINS` của backend (mặc định `["http://localhost:3010"]`).

## Demo luồng chính

1. **Tài liệu** → tải lên PDF/DOCX/TXT/MD hoặc URL (≤ 10MB). Mỗi tài liệu hiện pipeline Parse → Chunk → Embed → Lưu DB với thanh tiến độ từng bước và cảnh báo khi kẹt (chưa có worker nhận task, mất heartbeat worker, bước không tiến triển).
2. **Chiến dịch** → chọn model, gõ brief (vd. *"Ra mắt ứng dụng PayNow giúp kế toán SME đối soát hóa đơn, mục tiêu 500 lead tháng 11"*).
3. Dàn ý stream dần → modal **Duyệt dàn ý**: *Duyệt*, *Sửa trực tiếp* (Markdown) hoặc *Từ chối* kèm lý do (agent tra cứu lại và đề xuất dàn ý mới).
4. Ba bản thảo stream song song → fact-check (tự sửa tối đa 2 vòng) → màn **Duyệt bản thảo**: 3 tab Facebook / Instagram / Threads, sửa trực tiếp từng kênh, đối chiếu danh sách pass/fail của fact-check rồi *chốt*.
5. Thanh **Token / Chi phí** góc trên cộng dồn theo từng lần gọi LLM. Tải lại trang (`/chat?thread=…`) vẫn khôi phục lịch sử, bước đang chờ duyệt và tổng chi phí.
6. **Admin → Chi phí**: tổng token/USD theo model, node, người dùng, lọc theo ngày / user / model. **Bảng giá model**: sửa đơn giá, bật/tắt, đặt mặc định, thêm model. **Người dùng**: khóa / mở khóa (token cũ bị từ chối ngay).

## Test

```bash
docker compose -f infra/docker-compose.yml up -d
cd backend && . .venv/bin/activate
alembic upgrade head && python -m scripts.seed   # test dùng admin seed
pytest -q
```

Test dùng LLM và embedding giả (không gọi API ngoài), chạy trên DB dev và tự dọn dữ liệu test sau khi xong. Luồng chính hai lần HITL + cost audit: `tests/integration/test_agent.py::test_full_flow_two_hitl_with_cost_audit`.

Frontend: `npm run typecheck` và `npm run build`.

## API chính

| Method | Path | Mô tả |
|---|---|---|
| POST | `/api/v1/auth/register`, `/auth/login`, `/auth/refresh` · GET `/auth/me` | Đăng ký / JWT / đổi token mới / thông tin user |
| POST | `/api/v1/agent/chat/stream` | Bắt đầu lượt chat (SSE) |
| POST | `/api/v1/agent/chat/resume` | Gửi quyết định HITL (SSE) |
| GET | `/api/v1/agent/models` | Model đang bật (+ đã có API key chưa) |
| GET | `/api/v1/agent/threads` · `/threads/{id}/messages` · `/threads/{id}/state` | Lịch sử, HITL đang chờ, tổng chi phí thread |
| POST/GET | `/api/v1/documents/upload` · `/documents` | Tài liệu RAG |
| GET/PATCH/PUT/DELETE | `/api/v1/admin/...` | Users, pricing, analytics/costs, xóa tài liệu |

Event SSE: `status`, `token`, `cost_update`, `hitl_interrupt`, `error`, `complete` – mỗi lượt kết thúc bằng đúng một trong `hitl_interrupt` / `error` / `complete`. Chi tiết: [backend/app/agent/streaming.py](backend/app/agent/streaming.py).

## Lưu ý khi deploy

- **SSE qua reverse proxy**: tắt buffering (`proxy_buffering off;` với nginx). Backend đã gửi `X-Accel-Buffering: no`.
- `NEXT_PUBLIC_API_URL` được nhúng lúc build frontend: đổi URL backend thì build lại image `web` (build arg).
- Chỉ model có trong `model_pricing`, đang bật và provider đã có API key mới chọn được trên UI. Nếu dòng giá bị mất giữa chừng, chi phí ghi 0 và thanh chi phí báo *thiếu bảng giá*.
- Kích thước embedding (1536) phải khớp model embedding đã chọn.
