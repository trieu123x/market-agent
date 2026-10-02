# Kế hoạch 5 ngày – Marketing Agent MVP

Mục tiêu cuối ngày 5: chạy được end-to-end luồng chat → outline → HITL 1 → drafts → fact-check → HITL 2 → log cost, có upload tài liệu RAG và Admin cơ bản. Spec gốc: [spec_marketing_agent.md](spec_marketing_agent.md).

Nguyên tắc cắt phạm vi: làm đường chạy chính (happy path) trước; OCR, reranker, semantic injection classifier, rate limit nâng cao để ở mức stub/đơn giản, bổ sung nếu còn thời gian.

## Ngày 1 – Nền tảng & Database
- `infra/docker-compose.yml`: Postgres (pgvector) + Redis.
- `backend`: pyproject, config (pydantic-settings), FastAPI app skeleton, logging.
- SQLAlchemy models + Alembic migration cho 7 bảng (users, model_pricing, documents, document_chunks, chat_threads, thread_messages, llm_cost_logs) + index HNSW/GIN.
- Auth: đăng ký/đăng nhập, JWT, RBAC (USER/ADMIN), `deps.py`.
- `scripts/seed.py`: admin mặc định + bảng giá model.
- **Done khi:** `docker compose up`, migrate chạy, login lấy được JWT, test auth pass.

## Ngày 2 – RAG Ingestion & Retrieval
- `POST /documents/upload` (≤10MB, trả 202) + Anti-SSRF cho URL.
- Worker (Taskiq + Redis): parse PDF (PyMuPDF), DOCX, TXT, URL → Markdown → chunk (800/150) → embed batch → lưu pgvector, cập nhật `processing_status`.
- Retriever: hybrid vector + FTS, RRF, lọc scope SYSTEM/PRIVATE. Reranker: stub, trả top 4 theo RRF.
- Admin `DELETE /admin/documents/{id}`.
- **Done khi:** upload 1 PDF → READY → query trả đúng top chunks, user B không thấy tài liệu PRIVATE của user A.

## Ngày 3 – LangGraph core + SSE + HITL 1
- `AgentState`, `llm_factory` (OpenAI/Anthropic/Gemini theo `model_id`), `AsyncPostgresSaver`.
- Node: input_guardrail (regex + PII, rate limit 30 req/min), intent_rag, generate_outline, hitl_outline (interrupt: approve/edit/reject).
- `POST /agent/chat/stream` và `/chat/resume` với `astream_events` → SSE (`status`, `token`, `hitl_interrupt`, `error`, `complete`).
- Lưu `chat_threads` / `thread_messages`.
- **Done khi:** curl gửi chat → nhận stream outline → dừng ở `hitl_interrupt` → resume APPROVE chạy tiếp được; reject quay lại intent_rag.

## Ngày 4 – Generator, Fact-checker, HITL 2, Cost audit
- Node: multi_format_generator (LinkedIn/X/Facebook), fact_checker_critic, refine_generator (retry < 2), hitl_drafts, finalize_log.
- Output guardrail: secret scanner + anti-cliché filter; context isolation (thẻ `external_context`).
- Cost auditor: ghi `llm_cost_logs` theo node, tính USD từ `model_pricing`, phát event `cost_update`.
- Admin API: users status, pricing GET/PUT, analytics/costs.
- **Done khi:** chạy trọn luồng 2 lần HITL, có log cost đúng theo node/model, Admin xem được báo cáo chi phí.

## Ngày 5 – Frontend, tích hợp, hoàn thiện
- Next.js: login, trang chat dùng `@microsoft/fetch-event-source` (`useAgentStream`), thanh cost realtime.
- `OutlineApprovalModal` (Approve/Edit/Reject), `DraftsApprovalView` (3 tab + fact-check report).
- Admin portal tối giản: users, pricing, costs.
- Test tích hợp luồng chính, Dockerfile cho backend/frontend, README hướng dẫn chạy.
- Buffer: reranker thật, OCR, semantic injection classifier nếu còn thời gian.
- **Done khi:** demo được toàn bộ luồng từ UI; README chạy lại từ đầu thành công.

## Rủi ro cần để ý
- Resume sau `interrupt()` phải dùng cùng `thread_id` và checkpointer Postgres – test sớm vào ngày 3.
- SSE bị buffer bởi proxy/nginx – tắt buffering khi deploy.
- Dimension embedding (1536) phải khớp với model embedding đã chọn.
- Cost bằng 0 nếu `model_id` không có trong `model_pricing` – cần fallback/báo lỗi rõ.
