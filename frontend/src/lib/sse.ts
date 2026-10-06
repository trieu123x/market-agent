// POST + SSE qua @microsoft/fetch-event-source (EventSource gốc không gửi được header Authorization / body).
import { EventStreamContentType, fetchEventSource } from "@microsoft/fetch-event-source";

import type { AgentEvent } from "@/types/events";
import { API_URL, ApiError, authHeaders, toApiError } from "./api";

interface StreamOptions {
  onEvent: (event: AgentEvent) => void;
  signal: AbortSignal;
}

/** Resolve khi server đóng stream (hoặc khi bị abort). Không tự retry: chat/resume không idempotent. */
export async function postEventStream(path: string, body: unknown, { onEvent, signal }: StreamOptions) {
  await fetchEventSource(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: EventStreamContentType, ...authHeaders() },
    body: JSON.stringify(body),
    signal,
    // Mặc định thư viện đóng stream khi tab bị ẩn rồi gửi lại request khi hiện lại → chạy graph 2 lần
    openWhenHidden: true,
    async onopen(res) {
      if (res.ok && res.headers.get("content-type")?.startsWith(EventStreamContentType)) return;
      throw res.ok ? new ApiError(res.status, "Phản hồi không phải SSE") : await toApiError(res);
    },
    onmessage(msg) {
      if (msg.event) onEvent({ event: msg.event, data: JSON.parse(msg.data) } as AgentEvent);
    },
    onerror(err) {
      throw err instanceof ApiError ? err : new ApiError(0, "Mất kết nối tới server khi đang stream");
    },
  });
}
